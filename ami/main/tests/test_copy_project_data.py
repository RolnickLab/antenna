"""
Tests for the copy_project_data management command.

The command reads a separate database through its own read-only connection. These tests point
that connection at the test database itself, so the source and the target are the same database.
That exercises the full path (read-only snapshot, COPY into staging tables, new ids, rewritten
foreign keys) and the reuse of shared rows: every taxon, algorithm and pipeline already exists in
the target, so the copy must reuse them rather than duplicate them. TransactionTestCase is needed
because the read-only connection only sees committed rows.
"""

import os
from io import StringIO
from unittest.mock import patch

import psycopg
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.test import TransactionTestCase

from ami.main.management.commands.copy_project_data import SOURCE_URL_ENV, connect_source
from ami.main.models import (
    Classification,
    Deployment,
    Detection,
    Event,
    Identification,
    Occurrence,
    Project,
    SourceImage,
    SourceImageCollection,
    TaxaList,
    Taxon,
    TaxonRank,
)
from ami.ml.models import Algorithm, AlgorithmCategoryMap, Pipeline
from ami.ml.models.algorithm import AlgorithmTaskType
from ami.tests.fixtures.main import (
    create_captures,
    create_deployment,
    create_occurrences,
    create_taxa,
    setup_test_project,
)
from ami.users.roles import ProjectManager


def test_database_url() -> str:
    settings = connection.settings_dict
    return psycopg.conninfo.make_conninfo(
        dbname=settings["NAME"],
        user=settings["USER"],
        password=settings["PASSWORD"],
        host=settings["HOST"],
        port=settings["PORT"] or None,
    )


def per_deployment_counts(deployment_ids) -> dict[str, int]:
    return {
        "events": Event.objects.filter(deployment_id__in=deployment_ids).count(),
        "captures": SourceImage.objects.filter(deployment_id__in=deployment_ids).count(),
        "detections": Detection.objects.filter(source_image__deployment_id__in=deployment_ids).count(),
        "classifications": Classification.objects.filter(
            detection__source_image__deployment_id__in=deployment_ids
        ).count(),
        "occurrences": Occurrence.objects.filter(deployment_id__in=deployment_ids).count(),
    }


class TestCopyProjectData(TransactionTestCase):
    def setUp(self):
        self.project, self.kept = setup_test_project(reuse=False)
        self.left_out = create_deployment(self.project, self.kept.data_source, name="Left out")
        self.taxa_list = create_taxa(self.project)
        create_captures(self.kept, num_nights=2, images_per_night=2)
        create_captures(self.left_out, num_nights=1, images_per_night=2)
        create_occurrences(self.kept, num=4)
        create_occurrences(self.left_out, num=2)

        species = list(Taxon.objects.filter(projects=self.project, rank=TaxonRank.SPECIES.name).order_by("name"))
        data = [{"index": i, "label": taxon.name} for i, taxon in enumerate(species)]
        category_map = AlgorithmCategoryMap.objects.create(
            data=data, labels=[item["label"] for item in data], version="v1"
        )
        self.algorithm = Algorithm.objects.create(
            name="Species classifier",
            key="copy-test-species-classifier",
            task_type=AlgorithmTaskType.CLASSIFICATION.value,
            category_map=category_map,
        )
        pipeline = Pipeline.objects.create(name="Copy test pipeline", slug="copy-test-pipeline")
        pipeline.algorithms.add(self.algorithm)
        pipeline.projects.add(self.project)
        self.logits = [2.0, 1.0, 0.5][: len(species)]
        self.scores = [0.6, 0.3, 0.1][: len(species)]
        Classification.objects.filter(detection__source_image__project=self.project).update(
            algorithm=self.algorithm,
            category_map=category_map,
            logits=self.logits,
            scores=self.scores,
            terminal=True,
        )
        occurrence = Occurrence.objects.filter(deployment=self.kept).first()
        Identification.objects.create(occurrence=occurrence, taxon=occurrence.determination, user=self.project.owner)
        self.all_deployment_ids = list(self.project.deployments.values_list("pk", flat=True))
        self.source_counts = per_deployment_counts(self.all_deployment_ids)

    def copy(self, *args, execute=True):
        out = StringIO()
        flags = ["--execute"] if execute else []
        with patch.dict(os.environ, {SOURCE_URL_ENV: test_database_url()}):
            call_command("copy_project_data", "--project", str(self.project.pk), *args, *flags, stdout=out)
        return out.getvalue()

    def copied_project(self) -> Project:
        return Project.objects.exclude(pk=self.project.pk).get(name=self.project.name)

    def test_copies_chosen_deployments_with_scores(self):
        taxa_before, algorithms_before = Taxon.objects.count(), Algorithm.objects.count()
        pipelines_before = Pipeline.objects.count()

        self.copy("--exclude-deployments", str(self.left_out.pk))

        copy = self.copied_project()
        expected = self.project.deployments.exclude(pk=self.left_out.pk)
        copied_deployments = copy.deployments.all()
        self.assertEqual(
            sorted(copied_deployments.values_list("name", flat=True)), sorted(expected.values_list("name", flat=True))
        )
        self.assertFalse(set(copied_deployments.values_list("pk", flat=True)) & set(self.all_deployment_ids))
        self.assertEqual(
            per_deployment_counts(copied_deployments.values_list("pk", flat=True)),
            per_deployment_counts(expected.values_list("pk", flat=True)),
        )

        # Scores and logits travel with each classification, and keep their algorithm.
        copied = Classification.objects.filter(detection__source_image__project=copy)
        self.assertTrue(copied.exists())
        for classification in copied:
            self.assertEqual(classification.logits, self.logits)
            self.assertEqual(classification.scores, self.scores)
            self.assertEqual(classification.algorithm_id, self.algorithm.pk)
            self.assertEqual(classification.detection.source_image.deployment.project_id, copy.pk)

        # Shared rows are reused by their natural keys, not duplicated.
        self.assertEqual(Taxon.objects.count(), taxa_before)
        self.assertEqual(Algorithm.objects.count(), algorithms_before)
        self.assertEqual(Pipeline.objects.count(), pipelines_before)
        self.assertTrue(copy.pipelines.filter(slug="copy-test-pipeline").exists())

        # Occurrences point at copied events and deployments, and keep their determinations.
        for occurrence in Occurrence.objects.filter(project=copy):
            self.assertEqual(occurrence.deployment.project_id, copy.pk)
            self.assertEqual(occurrence.event.project_id, copy.pk)
            self.assertIsNotNone(occurrence.determination_id)

        # The identification is copied; without --with-users its user is not.
        identification = Identification.objects.get(occurrence__project=copy)
        self.assertIsNone(identification.user_id)
        self.assertIsNone(copy.owner_id)
        # The raw insert skips the project's post_save signal, so the command creates the role groups.
        self.assertTrue(Group.objects.filter(name=ProjectManager.get_group_name(copy)).exists())

        # Capture sets only hold copied captures, and the project's taxa list comes along.
        copied_images = set(SourceImage.objects.filter(project=copy).values_list("pk", flat=True))
        member_ids = set(SourceImageCollection.objects.filter(project=copy).values_list("images", flat=True))
        member_ids.discard(None)
        self.assertTrue(member_ids)
        self.assertLessEqual(member_ids, copied_images)
        copied_list = TaxaList.objects.exclude(pk=self.taxa_list.pk).get(projects=copy)
        self.assertEqual(set(copied_list.taxa.all()), set(self.taxa_list.taxa.all()))

        # The source is unchanged.
        self.assertEqual(per_deployment_counts(self.all_deployment_ids), self.source_counts)
        self.assertEqual(
            sorted(self.project.deployments.values_list("pk", flat=True)), sorted(self.all_deployment_ids)
        )

    def test_class_masking_runs_on_the_copy(self):
        """The copy carries what class masking needs: a capture set, a taxa list, logits and the algorithm."""
        self.copy("--deployments", str(self.kept.pk))
        copy = self.copied_project()
        collection = SourceImageCollection.objects.filter(project=copy, images__isnull=False).distinct().first()
        copied_list = TaxaList.objects.exclude(pk=self.taxa_list.pk).get(projects=copy)
        call_command(
            "run_class_masking",
            "--collection-id",
            str(collection.pk),
            "--taxa-list-id",
            str(copied_list.pk),
            "--algorithm-id",
            str(self.algorithm.pk),
            stdout=StringIO(),
        )
        masked = Classification.objects.filter(
            detection__source_image__project=copy, applied_to__isnull=False, terminal=True
        )
        self.assertTrue(masked.exists())
        self.assertFalse(
            Classification.objects.filter(detection__source_image__project=self.project, applied_to__isnull=False)
        )

    def test_with_users_reuses_accounts_and_copies_membership(self):
        self.copy("--deployments", str(self.kept.pk), "--with-users")
        copy = self.copied_project()
        self.assertEqual(copy.owner_id, self.project.owner_id)
        self.assertEqual(Identification.objects.get(occurrence__project=copy).user_id, self.project.owner_id)
        self.assertEqual(
            set(copy.members.values_list("pk", flat=True)), set(self.project.members.values_list("pk", flat=True))
        )
        self.assertTrue(ProjectManager.has_role(self.project.owner, copy))

    def test_dry_run_writes_nothing(self):
        projects_before = Project.objects.count()
        output = self.copy(execute=False)
        self.assertEqual(Project.objects.count(), projects_before)
        self.assertIn("Dry run", output)
        self.assertIn("with logits", output)

    def test_rejects_deployments_from_another_project(self):
        other_project, other_deployment = setup_test_project(reuse=False)
        with self.assertRaises(CommandError):
            self.copy("--deployments", str(other_deployment.pk))

    def test_requires_source_url(self):
        with patch.dict(os.environ, {}, clear=True), self.assertRaises(CommandError):
            call_command("copy_project_data", "--project", str(self.project.pk), stdout=StringIO())

    def test_source_connection_refuses_writes(self):
        source = connect_source(test_database_url())
        try:
            with self.assertRaises(psycopg.errors.ReadOnlySqlTransaction):
                source.execute(
                    "UPDATE main_project SET name = name WHERE id = %s", [self.project.pk]  # nosec: test only
                )
        finally:
            source.close()
        self.assertTrue(Deployment.objects.filter(pk=self.kept.pk).exists())
