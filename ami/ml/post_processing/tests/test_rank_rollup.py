"""Domain and admin-wiring tests for the rank roll-up post-processing task.

Rank roll-up walks each detection's classification distribution from the finest
rank upward and promotes the prediction to the first rank whose summed
probability clears that rank's threshold, writing a new terminal classification
at that rank (linked back via ``applied_to``). These tests cover the schema
contract, the admin trigger, and a roll-up from species to genus end to end.
"""
import datetime
import pathlib
import uuid

import pydantic
from django.contrib import admin as django_admin
from django.test import TestCase
from django.urls import reverse

from ami.jobs.models import Job
from ami.main.models import (
    Classification,
    Detection,
    Occurrence,
    SourceImage,
    SourceImageCollection,
    Taxon,
    TaxonRank,
    group_images_into_events,
)
from ami.ml.models import Algorithm, AlgorithmCategoryMap
from ami.ml.models.algorithm import AlgorithmTaskType
from ami.ml.post_processing.rank_rollup import RankRollupConfig, RankRollupTask
from ami.ml.post_processing.tests.test_class_masking_admin import _PostProcessingAdminCase
from ami.tests.fixtures.main import create_taxa, setup_test_project


class TestRankRollupConfig(TestCase):
    def test_defaults_applied(self):
        config = RankRollupConfig(source_image_collection_id=1)
        self.assertEqual(config.thresholds["SPECIES"], 0.8)
        self.assertEqual(config.rollup_order, ["SPECIES", "GENUS", "FAMILY"])

    def test_threshold_out_of_range_is_invalid(self):
        with self.assertRaises(pydantic.ValidationError):
            RankRollupConfig(source_image_collection_id=1, thresholds={"SPECIES": 1.5})

    def test_threshold_and_order_are_uppercased(self):
        config = RankRollupConfig(
            source_image_collection_id=1, thresholds={"species": 0.7}, rollup_order=["species", "genus"]
        )
        self.assertIn("SPECIES", config.thresholds)
        self.assertEqual(config.rollup_order, ["SPECIES", "GENUS"])


class TestRankRollupDomain(TestCase):
    """A low-confidence species prediction rolls up to its genus."""

    def setUp(self):
        self.project, self.deployment = setup_test_project()
        create_taxa(project=self.project)
        self._create_images(self.deployment)
        group_images_into_events(deployment=self.deployment)

        self.collection = SourceImageCollection.objects.create(
            name="Rank rollup collection",
            project=self.project,
            method="manual",
            kwargs={"image_ids": list(self.deployment.captures.values_list("pk", flat=True))},
        )
        self.collection.populate_sample()

        self.species_taxon = Taxon.objects.filter(rank=TaxonRank.SPECIES.name).first()
        self.genus_taxon = self.species_taxon.parent if self.species_taxon else None
        self.assertIsNotNone(self.species_taxon)
        self.assertIsNotNone(self.genus_taxon)
        self.algorithm = self._create_classifier()

    def _create_images(self, deployment, num_images=5, width=640, height=480):
        base_time = datetime.datetime.now(datetime.timezone.utc)
        for i in range(num_images):
            SourceImage.objects.create(
                deployment=deployment,
                project=deployment.project,
                timestamp=base_time + datetime.timedelta(minutes=i * 5),
                path=pathlib.Path("test") / f"{uuid.uuid4().hex[:8]}_{i}.jpg",
                width=width,
                height=height,
            )
        deployment.save(update_calculated_fields=True, regroup_async=False)

    def _create_classifier(self) -> Algorithm:
        species_taxa = list(self.project.taxa.filter(rank=TaxonRank.SPECIES.name).order_by("name")[:3])
        assert species_taxa, "No species taxa found in project; run create_taxa() first."
        data = [{"index": i, "label": taxon.name} for i, taxon in enumerate(species_taxa)]
        category_map = AlgorithmCategoryMap.objects.create(
            data=data,
            labels=[item["label"] for item in data],
            version="v1.0",
            description="Species-level category map for testing",
        )
        return Algorithm.objects.create(
            name="Test Species Classifier",
            task_type=AlgorithmTaskType.CLASSIFICATION.value,
            category_map=category_map,
        )

    def _detection_with_occurrence(self) -> tuple[Detection, Occurrence]:
        det = Detection.objects.create(source_image=self.collection.images.first(), bbox=[0, 0, 200, 200])
        occ = Occurrence.objects.create(project=self.project, event=self.deployment.events.first())
        occ.detections.add(det)
        return det, occ

    def test_rank_rollup_creates_genus_terminal_classification(self):
        now = datetime.datetime.now(datetime.timezone.utc)
        originals = []
        for _ in range(3):
            det, _occ = self._detection_with_occurrence()
            originals.append(
                Classification.objects.create(
                    detection=det,
                    taxon=self.species_taxon,
                    score=0.5,
                    scores=[0.5, 0.2, 0.1],
                    terminal=True,
                    timestamp=now,
                    algorithm=self.algorithm,
                )
            )

        RankRollupTask(
            source_image_collection_id=self.collection.pk,
            thresholds={"SPECIES": 0.8, "GENUS": 0.6, "FAMILY": 0.4},
        ).run()

        for original in originals:
            original.refresh_from_db(fields=["terminal"])
            self.assertFalse(original.terminal)
            rolled = Classification.objects.filter(detection=original.detection, terminal=True).first()
            self.assertIsNotNone(rolled)
            self.assertEqual(rolled.taxon, self.genus_taxon)
            self.assertEqual(rolled.applied_to, original)


class TestRankRollupAdmin(_PostProcessingAdminCase):
    def test_valid_post_creates_rank_rollup_job_with_defaults(self):
        url = reverse("admin:main_sourceimagecollection_changelist")
        response = self.client.post(
            url,
            data={
                "action": "run_rank_rollup",
                django_admin.helpers.ACTION_CHECKBOX_NAME: [str(self.collection.pk)],
                "confirm": "yes",
            },
        )
        self.assertEqual(response.status_code, 302)
        job = Job.objects.get(project=self.project, job_type_key="post_processing")
        self.assertEqual(job.params["task"], "rank_rollup")
        self.assertEqual(job.params["config"]["source_image_collection_id"], self.collection.pk)
        self.assertEqual(job.params["config"]["thresholds"]["SPECIES"], 0.8)
