"""
Tests for the move_project_data management command.
"""

import datetime
import uuid
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.test import TestCase

from ami.jobs.models import Job
from ami.main.models import (
    Classification,
    Deployment,
    Detection,
    Device,
    Event,
    Identification,
    Occurrence,
    Project,
    S3StorageSource,
    Site,
    SourceImage,
    SourceImageCollection,
    TaxaList,
    Taxon,
    TaxonRank,
    group_images_into_events,
)
from ami.ml.models.pipeline import Pipeline
from ami.ml.models.project_pipeline_config import ProjectPipelineConfig
from ami.users.models import User


def _uid():
    return uuid.uuid4().hex[:8]


def _create_user(email=None):
    return User.objects.create_user(email=email or f"test-{_uid()}@example.com", password="testpass")


def _create_project(owner, name=None):
    """Create a project with create_defaults=False to avoid side effects."""
    return Project.objects.create(name=name or f"Project {_uid()}", owner=owner, create_defaults=False)


def _create_s3_source(project, name=None):
    return S3StorageSource.objects.create(
        project=project,
        name=name or f"S3 Source {_uid()}",
        bucket="test-bucket",
        endpoint_url="http://minio:9000",
        access_key="test",
        secret_key="test",
    )


def _create_device(project, name=None):
    return Device.objects.create(project=project, name=name or f"Device {_uid()}")


def _create_site(project, name=None):
    return Site.objects.create(project=project, name=name or f"Site {_uid()}")


def _create_deployment(project, s3_source=None, device=None, site=None, name=None):
    return Deployment.objects.create(
        project=project,
        name=name or f"Deployment {_uid()}",
        data_source=s3_source,
        device=device,
        research_site=site,
    )


def _create_captures(deployment, count=3):
    """Create source images and group into events."""
    images = []
    base_time = datetime.datetime(2024, 6, 15, 22, 0)
    for i in range(count):
        img = SourceImage.objects.create(
            deployment=deployment,
            project=deployment.project,
            timestamp=base_time + datetime.timedelta(minutes=i * 10),
            path=f"test/{_uid()}_{i}.jpg",
        )
        images.append(img)
    group_images_into_events(deployment)
    # Refresh to get event assignments
    for img in images:
        img.refresh_from_db()
    return images


def _create_taxa(project):
    """Create a small taxonomy tree and link to project."""
    order = Taxon.objects.create(name=f"Lepidoptera-{_uid()}", rank=TaxonRank.ORDER.name)
    species = Taxon.objects.create(name=f"Vanessa atalanta-{_uid()}", rank=TaxonRank.SPECIES.name, parent=order)
    project.taxa.add(order, species)
    return [order, species]


def _create_occurrences(deployment, taxa, images):
    """Create occurrences with detections and classifications."""
    occurrences = []
    for i, img in enumerate(images):
        occ = Occurrence.objects.create(
            event=img.event,
            deployment=deployment,
            project=deployment.project,
            determination=taxa[i % len(taxa)],
            determination_score=0.9,
        )
        det = Detection.objects.create(
            source_image=img,
            timestamp=img.timestamp,
            bbox=[0.1, 0.1, 0.2, 0.2],
            occurrence=occ,
        )
        Classification.objects.create(
            detection=det,
            taxon=taxa[i % len(taxa)],
            score=0.85,
            timestamp=img.timestamp,
        )
        occurrences.append(occ)
    return occurrences


def _create_identification(occurrence, user, taxon):
    return Identification.objects.create(occurrence=occurrence, user=user, taxon=taxon)


def _create_pipeline(name=None):
    return Pipeline.objects.create(name=name or f"Pipeline {_uid()}")


def _run_command(*args, **kwargs):
    """Call move_project_data and return (stdout, stderr)."""
    out = StringIO()
    err = StringIO()
    call_command("move_project_data", *args, stdout=out, stderr=err, **kwargs)
    return out.getvalue(), err.getvalue()


class MoveProjectDataSetupMixin:
    """Common setup for move_project_data tests."""

    def _setup_source(self, num_images=3, with_occurrences=True, with_identifications=False):
        """
        Create a source project with one deployment, images, taxa, and optionally
        occurrences/identifications.
        """
        self.owner = _create_user()
        self.source_project = _create_project(self.owner, "Source Project")
        self.s3_source = _create_s3_source(self.source_project)
        self.device = _create_device(self.source_project)
        self.site = _create_site(self.source_project)
        self.deployment = _create_deployment(
            self.source_project, s3_source=self.s3_source, device=self.device, site=self.site, name="Dep A"
        )
        self.images = _create_captures(self.deployment, count=num_images)
        self.taxa = _create_taxa(self.source_project)

        self.occurrences = []
        if with_occurrences:
            self.occurrences = _create_occurrences(self.deployment, self.taxa, self.images)

        self.identifications = []
        if with_identifications:
            self.identifier_user = _create_user(email="identifier@example.com")
            for occ in self.occurrences:
                ident = _create_identification(occ, self.identifier_user, self.taxa[0])
                self.identifications.append(ident)

    def _base_args(self):
        return ["--source-project", str(self.source_project.pk), "--deployment-ids", str(self.deployment.pk)]


class TestMoveToExistingProject(MoveProjectDataSetupMixin, TestCase):
    """Test moving deployments to an existing target project."""

    def setUp(self):
        self._setup_source(num_images=3, with_occurrences=True)
        self.target_project = _create_project(self.owner, "Target Project")

    def test_basic_move(self):
        """All data is moved to the target project and removed from source."""
        dep_id = self.deployment.pk
        pre_source_occs = Occurrence.objects.filter(project=self.source_project).count()

        _run_command(*self._base_args(), "--target-project", str(self.target_project.pk), "--execute")

        # Deployment now in target
        self.deployment.refresh_from_db()
        self.assertEqual(self.deployment.project_id, self.target_project.pk)

        # All images moved
        self.assertEqual(SourceImage.objects.filter(deployment_id=dep_id, project=self.target_project).count(), 3)
        self.assertEqual(SourceImage.objects.filter(deployment_id=dep_id, project=self.source_project).count(), 0)

        # All occurrences moved
        self.assertEqual(
            Occurrence.objects.filter(deployment_id=dep_id, project=self.target_project).count(), pre_source_occs
        )
        self.assertEqual(Occurrence.objects.filter(deployment_id=dep_id, project=self.source_project).count(), 0)

        # Events moved
        self.assertEqual(Event.objects.filter(deployment_id=dep_id, project=self.target_project).count(), 1)
        self.assertEqual(Event.objects.filter(deployment_id=dep_id, project=self.source_project).count(), 0)

        # Detections still accessible via deployment
        self.assertEqual(Detection.objects.filter(source_image__deployment_id=dep_id).count(), 3)
        # And via project
        self.assertEqual(Detection.objects.filter(source_image__project=self.target_project).count(), 3)

        # Classifications still accessible
        self.assertEqual(Classification.objects.filter(detection__source_image__deployment_id=dep_id).count(), 3)

        # Source project should be empty
        self.assertEqual(SourceImage.objects.filter(project=self.source_project).count(), 0)

    def test_taxa_linked_to_target(self):
        """Taxa referenced by moved occurrences are linked to target project."""
        _run_command(*self._base_args(), "--target-project", str(self.target_project.pk), "--execute")

        target_taxa_ids = set(self.target_project.taxa.values_list("pk", flat=True))
        for taxon in self.taxa:
            self.assertIn(taxon.pk, target_taxa_ids)

    def test_conservation_counts(self):
        """Source + target row counts equal the original totals after move."""
        pre_total_imgs = SourceImage.objects.filter(project=self.source_project).count()
        pre_total_occs = Occurrence.objects.filter(project=self.source_project).count()

        _run_command(*self._base_args(), "--target-project", str(self.target_project.pk), "--execute")

        post_source_imgs = SourceImage.objects.filter(project=self.source_project).count()
        post_target_imgs = SourceImage.objects.filter(project=self.target_project).count()
        self.assertEqual(post_source_imgs + post_target_imgs, pre_total_imgs)

        post_source_occs = Occurrence.objects.filter(project=self.source_project).count()
        post_target_occs = Occurrence.objects.filter(project=self.target_project).count()
        self.assertEqual(post_source_occs + post_target_occs, pre_total_occs)

    def test_jobs_moved(self):
        """Jobs associated with moved deployments are moved."""
        pipeline = _create_pipeline()
        Job.objects.create(project=self.source_project, deployment=self.deployment, pipeline=pipeline)

        _run_command(*self._base_args(), "--target-project", str(self.target_project.pk), "--execute")

        self.assertEqual(Job.objects.filter(deployment=self.deployment, project=self.target_project).count(), 1)
        self.assertEqual(Job.objects.filter(deployment=self.deployment, project=self.source_project).count(), 0)


class TestDryRun(MoveProjectDataSetupMixin, TestCase):
    """Dry run must not modify any data."""

    def setUp(self):
        self._setup_source(num_images=3, with_occurrences=True)
        self.target_project = _create_project(self.owner, "Target Project")

    def test_dry_run_no_changes(self):
        """Without --execute, nothing is modified."""
        pre_img_count = SourceImage.objects.filter(project=self.source_project).count()
        pre_occ_count = Occurrence.objects.filter(project=self.source_project).count()

        out, _ = _run_command(*self._base_args(), "--target-project", str(self.target_project.pk))

        self.assertIn("DRY RUN", out)

        # Nothing changed
        self.deployment.refresh_from_db()
        self.assertEqual(self.deployment.project_id, self.source_project.pk)
        self.assertEqual(SourceImage.objects.filter(project=self.source_project).count(), pre_img_count)
        self.assertEqual(Occurrence.objects.filter(project=self.source_project).count(), pre_occ_count)
        self.assertEqual(SourceImage.objects.filter(project=self.target_project).count(), 0)


class TestCreateProject(MoveProjectDataSetupMixin, TestCase):
    """Test --create-project flag."""

    def setUp(self):
        self._setup_source(num_images=2, with_occurrences=False)

    @patch("ami.main.models.ProjectManager.create_related_defaults")
    def test_create_new_target(self, mock_defaults):
        """--create-project creates a new project and moves data into it."""
        new_name = f"New Project {_uid()}"

        _run_command(*self._base_args(), "--create-project", new_name, "--execute")

        target = Project.objects.get(name=new_name)
        self.deployment.refresh_from_db()
        self.assertEqual(self.deployment.project_id, target.pk)
        self.assertEqual(target.owner_id, self.owner.pk)
        self.assertEqual(SourceImage.objects.filter(project=target).count(), 2)
        mock_defaults.assert_called_once()

    @patch("ami.main.models.ProjectManager.create_related_defaults")
    def test_create_project_copies_members(self, mock_defaults):
        """Members from source are added to created target."""
        member = _create_user()
        self.source_project.members.add(member)

        new_name = f"New Project {_uid()}"
        _run_command(*self._base_args(), "--create-project", new_name, "--execute")

        target = Project.objects.get(name=new_name)
        self.assertIn(member, target.members.all())


class TestErrorHandling(MoveProjectDataSetupMixin, TestCase):
    """Test argument validation and error conditions."""

    def setUp(self):
        self._setup_source(num_images=1, with_occurrences=False)

    def test_source_project_not_found(self):
        with self.assertRaises(CommandError, msg="Source project 99999 does not exist"):
            _run_command("--source-project", "99999", "--deployment-ids", "1", "--target-project", "1")

    def test_target_project_not_found(self):
        with self.assertRaises(CommandError, msg="does not exist"):
            _run_command(*self._base_args(), "--target-project", "99999")

    def test_deployment_not_found(self):
        with self.assertRaises(CommandError, msg="not found"):
            _run_command(
                "--source-project", str(self.source_project.pk), "--deployment-ids", "99999", "--target-project", "1"
            )

    def test_deployment_wrong_project(self):
        other_project = _create_project(self.owner, "Other")
        other_dep = _create_deployment(other_project, name="Other Dep")

        with self.assertRaises(CommandError, msg="not in source project"):
            _run_command(
                "--source-project",
                str(self.source_project.pk),
                "--deployment-ids",
                str(other_dep.pk),
                "--target-project",
                str(other_project.pk),
            )

    def test_both_target_and_create(self):
        target = _create_project(self.owner, "Target")
        with self.assertRaises(CommandError, msg="not both"):
            _run_command(
                *self._base_args(), "--target-project", str(target.pk), "--create-project", "New Project", "--execute"
            )

    def test_neither_target_nor_create(self):
        with self.assertRaises(CommandError, msg="Must specify"):
            _run_command(*self._base_args())


class TestSharedResourceCloning(MoveProjectDataSetupMixin, TestCase):
    """Test clone-vs-reassign logic for Device, Site, and S3StorageSource."""

    def setUp(self):
        self._setup_source(num_images=2, with_occurrences=False)
        self.target_project = _create_project(self.owner, "Target Project")

    def test_exclusive_device_reassigned(self):
        """When only the moved deployment uses a device, it's reassigned (not cloned)."""
        original_device_pk = self.device.pk
        _run_command(*self._base_args(), "--target-project", str(self.target_project.pk), "--execute")

        self.device.refresh_from_db()
        self.assertEqual(self.device.pk, original_device_pk)  # Same PK, not cloned
        self.assertEqual(self.device.project_id, self.target_project.pk)

    def test_shared_device_cloned(self):
        """When another deployment in source also uses the device, it's cloned."""
        # Create a second deployment that shares the same device
        _create_deployment(self.source_project, device=self.device, name="Dep B (stays)")
        original_device_pk = self.device.pk

        _run_command(*self._base_args(), "--target-project", str(self.target_project.pk), "--execute")

        # Original device still belongs to source project
        original_device = Device.objects.get(pk=original_device_pk)
        self.assertEqual(original_device.project_id, self.source_project.pk)

        # Moved deployment now points to a NEW device (cloned)
        self.deployment.refresh_from_db()
        self.assertNotEqual(self.deployment.device_id, original_device_pk)
        cloned_device = Device.objects.get(pk=self.deployment.device_id)
        self.assertEqual(cloned_device.project_id, self.target_project.pk)
        self.assertEqual(cloned_device.name, original_device.name)

    def test_exclusive_site_reassigned(self):
        """When only the moved deployment uses a site, it's reassigned."""
        original_site_pk = self.site.pk
        _run_command(*self._base_args(), "--target-project", str(self.target_project.pk), "--execute")

        self.site.refresh_from_db()
        self.assertEqual(self.site.pk, original_site_pk)
        self.assertEqual(self.site.project_id, self.target_project.pk)

    def test_shared_site_cloned(self):
        """When another deployment in source also uses the site, it's cloned."""
        _create_deployment(self.source_project, site=self.site, name="Dep B (stays)")
        original_site_pk = self.site.pk

        _run_command(*self._base_args(), "--target-project", str(self.target_project.pk), "--execute")

        original_site = Site.objects.get(pk=original_site_pk)
        self.assertEqual(original_site.project_id, self.source_project.pk)

        self.deployment.refresh_from_db()
        self.assertNotEqual(self.deployment.research_site_id, original_site_pk)
        cloned_site = Site.objects.get(pk=self.deployment.research_site_id)
        self.assertEqual(cloned_site.project_id, self.target_project.pk)
        self.assertEqual(cloned_site.name, original_site.name)

    def test_exclusive_s3_source_reassigned(self):
        """When only the moved deployment uses an S3 source, it's reassigned."""
        original_s3_pk = self.s3_source.pk
        _run_command(*self._base_args(), "--target-project", str(self.target_project.pk), "--execute")

        self.s3_source.refresh_from_db()
        self.assertEqual(self.s3_source.pk, original_s3_pk)
        self.assertEqual(self.s3_source.project_id, self.target_project.pk)

    def test_shared_s3_source_cloned(self):
        """When another deployment in source also uses the S3 source, it's cloned."""
        _create_deployment(self.source_project, s3_source=self.s3_source, name="Dep B (stays)")
        original_s3_pk = self.s3_source.pk

        _run_command(*self._base_args(), "--target-project", str(self.target_project.pk), "--execute")

        original_s3 = S3StorageSource.objects.get(pk=original_s3_pk)
        self.assertEqual(original_s3.project_id, self.source_project.pk)

        self.deployment.refresh_from_db()
        self.assertNotEqual(self.deployment.data_source_id, original_s3_pk)
        cloned_s3 = S3StorageSource.objects.get(pk=self.deployment.data_source_id)
        self.assertEqual(cloned_s3.project_id, self.target_project.pk)

    def test_device_owned_by_other_project_unchanged(self):
        """A device owned by a different project is left untouched."""
        other_project = _create_project(self.owner, "Other")
        external_device = _create_device(other_project, name="External Device")
        self.deployment.device = external_device
        self.deployment.save(update_calculated_fields=False, regroup_async=False)

        _run_command(*self._base_args(), "--target-project", str(self.target_project.pk), "--execute")

        external_device.refresh_from_db()
        self.assertEqual(external_device.project_id, other_project.pk)  # Unchanged
        self.deployment.refresh_from_db()
        self.assertEqual(self.deployment.device_id, external_device.pk)  # Still references it


class TestCollectionHandling(MoveProjectDataSetupMixin, TestCase):
    """Test collection split/reassign logic."""

    def setUp(self):
        self._setup_source(num_images=3, with_occurrences=False)
        self.target_project = _create_project(self.owner, "Target Project")

        # Create a second deployment that stays in source
        self.dep_b = _create_deployment(self.source_project, name="Dep B (stays)")
        self.images_b = _create_captures(self.dep_b, count=2)

    def test_exclusive_collection_reassigned(self):
        """Collection with only moved images is reassigned to target."""
        coll = SourceImageCollection.objects.create(name="Exclusive Coll", project=self.source_project)
        coll.images.set(self.images)

        _run_command(*self._base_args(), "--target-project", str(self.target_project.pk), "--execute")

        coll.refresh_from_db()
        self.assertEqual(coll.project_id, self.target_project.pk)
        self.assertEqual(coll.images.count(), 3)

    def test_mixed_collection_split(self):
        """Collection with images from both deployments is split."""
        coll = SourceImageCollection.objects.create(
            name="Mixed Coll",
            project=self.source_project,
            method="random",
            kwargs={"seed": 42},
        )
        coll.images.set(list(self.images) + list(self.images_b))
        original_total = coll.images.count()

        _run_command(*self._base_args(), "--target-project", str(self.target_project.pk), "--execute")

        # Source collection now has only dep_b images
        coll.refresh_from_db()
        self.assertEqual(coll.project_id, self.source_project.pk)
        self.assertEqual(coll.images.count(), len(self.images_b))

        # New collection created in target with moved images
        target_coll = SourceImageCollection.objects.filter(project=self.target_project, name="Mixed Coll").first()
        self.assertIsNotNone(target_coll)
        self.assertEqual(target_coll.images.count(), len(self.images))
        # Preserves method and kwargs
        self.assertEqual(target_coll.method, "random")
        self.assertEqual(target_coll.kwargs, {"seed": 42})

        # Conservation: total images across both collections unchanged
        self.assertEqual(coll.images.count() + target_coll.images.count(), original_total)

    def test_no_clone_collections_flag(self):
        """--no-clone-collections removes images from source but doesn't create target collection."""
        coll = SourceImageCollection.objects.create(name="Mixed Coll", project=self.source_project)
        coll.images.set(list(self.images) + list(self.images_b))

        _run_command(
            *self._base_args(),
            "--target-project",
            str(self.target_project.pk),
            "--no-clone-collections",
            "--execute",
        )

        coll.refresh_from_db()
        self.assertEqual(coll.images.count(), len(self.images_b))
        # No collection created in target
        self.assertFalse(SourceImageCollection.objects.filter(project=self.target_project, name="Mixed Coll").exists())


class TestPipelineConfigCloning(MoveProjectDataSetupMixin, TestCase):
    """Test pipeline config clone logic."""

    def setUp(self):
        self._setup_source(num_images=1, with_occurrences=False)
        self.target_project = _create_project(self.owner, "Target Project")
        self.pipeline = _create_pipeline("Test Pipeline")
        ProjectPipelineConfig.objects.create(
            project=self.source_project,
            pipeline=self.pipeline,
            enabled=False,
            config={"batch_size": 32},
        )

    def test_pipeline_config_cloned(self):
        """Pipeline configs are cloned to target preserving enabled and config."""
        _run_command(*self._base_args(), "--target-project", str(self.target_project.pk), "--execute")

        target_config = ProjectPipelineConfig.objects.get(project=self.target_project, pipeline=self.pipeline)
        self.assertFalse(target_config.enabled)
        self.assertEqual(target_config.config, {"batch_size": 32})

    def test_existing_pipeline_config_not_duplicated(self):
        """If target already has a config for the same pipeline, it's not overwritten."""
        ProjectPipelineConfig.objects.create(
            project=self.target_project,
            pipeline=self.pipeline,
            enabled=True,
            config={"batch_size": 64},
        )

        _run_command(*self._base_args(), "--target-project", str(self.target_project.pk), "--execute")

        target_config = ProjectPipelineConfig.objects.get(project=self.target_project, pipeline=self.pipeline)
        # Original target config preserved, not overwritten
        self.assertTrue(target_config.enabled)
        self.assertEqual(target_config.config, {"batch_size": 64})

    def test_no_clone_pipelines_flag(self):
        """--no-clone-pipelines skips pipeline config cloning."""
        _run_command(
            *self._base_args(),
            "--target-project",
            str(self.target_project.pk),
            "--no-clone-pipelines",
            "--execute",
        )

        self.assertFalse(ProjectPipelineConfig.objects.filter(project=self.target_project).exists())


class TestProcessingServiceLinking(MoveProjectDataSetupMixin, TestCase):
    """Test that ProcessingServices are linked to target project."""

    def setUp(self):
        self._setup_source(num_images=1, with_occurrences=False)
        self.target_project = _create_project(self.owner, "Target Project")

    def _create_processing_service_raw(self, name, project_ids):
        """Create a ProcessingService without triggering get_status() via the custom manager."""
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO ml_processingservice (name, description, endpoint_url, created_at, updated_at)"
                " VALUES (%s, '', 'http://test:2000', NOW(), NOW()) RETURNING id",
                [name],
            )
            ps_id = cursor.fetchone()[0]
            for pid in project_ids:
                cursor.execute(
                    "INSERT INTO ml_processingservice_projects (processingservice_id, project_id) VALUES (%s, %s)",
                    [ps_id, pid],
                )
        return ps_id

    def test_processing_services_linked(self):
        """Processing services from source are linked to target."""
        ps_id = self._create_processing_service_raw("Test PS", [self.source_project.pk])

        _run_command(*self._base_args(), "--target-project", str(self.target_project.pk), "--execute")

        # Check via raw SQL since ORM has column issues
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(*) FROM ml_processingservice_projects WHERE processingservice_id=%s AND project_id=%s",
                [ps_id, self.target_project.pk],
            )
            count = cursor.fetchone()[0]
        self.assertEqual(count, 1)

    def test_already_linked_service_not_duplicated(self):
        """If target already has the processing service linked, no duplicate is created."""
        ps_id = self._create_processing_service_raw("Test PS", [self.source_project.pk, self.target_project.pk])

        _run_command(*self._base_args(), "--target-project", str(self.target_project.pk), "--execute")

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(*) FROM ml_processingservice_projects WHERE processingservice_id=%s AND project_id=%s",
                [ps_id, self.target_project.pk],
            )
            count = cursor.fetchone()[0]
        self.assertEqual(count, 1)  # Not duplicated


class TestIdentifierRolePreservation(MoveProjectDataSetupMixin, TestCase):
    """Test that identifier users are added to target project with correct roles."""

    def setUp(self):
        self._setup_source(num_images=2, with_occurrences=True, with_identifications=True)
        self.target_project = _create_project(self.owner, "Target Project")

    def test_identifiers_added_to_target(self):
        """Users who made identifications on moved data are added to target project."""
        _run_command(*self._base_args(), "--target-project", str(self.target_project.pk), "--execute")

        target_member_ids = set(self.target_project.members.values_list("pk", flat=True))
        self.assertIn(self.identifier_user.pk, target_member_ids)

    def test_identifier_already_member_not_duplicated(self):
        """If the identifier is already a member of target, they're not re-added."""
        self.target_project.members.add(self.identifier_user)
        pre_count = self.target_project.members.count()

        _run_command(*self._base_args(), "--target-project", str(self.target_project.pk), "--execute")

        self.assertEqual(self.target_project.members.count(), pre_count)


class TestTaxaListLinking(MoveProjectDataSetupMixin, TestCase):
    """Test TaxaList linking to target project."""

    def setUp(self):
        self._setup_source(num_images=1, with_occurrences=True)
        self.target_project = _create_project(self.owner, "Target Project")

    def test_taxa_lists_linked(self):
        """TaxaLists from source are linked to target project."""
        taxa_list = TaxaList.objects.create(name="Test List")
        taxa_list.projects.add(self.source_project)
        taxa_list.taxa.set(self.taxa)

        _run_command(*self._base_args(), "--target-project", str(self.target_project.pk), "--execute")

        self.assertIn(self.target_project, taxa_list.projects.all())


class TestDefaultFilterCopying(MoveProjectDataSetupMixin, TestCase):
    """Test copying of default filter config."""

    def setUp(self):
        self._setup_source(num_images=1, with_occurrences=True)
        self.target_project = _create_project(self.owner, "Target Project")

    def test_score_threshold_copied(self):
        """Source project's score threshold is copied to target."""
        self.source_project.default_filters_score_threshold = 0.75
        self.source_project.save()

        _run_command(*self._base_args(), "--target-project", str(self.target_project.pk), "--execute")

        self.target_project.refresh_from_db()
        self.assertEqual(self.target_project.default_filters_score_threshold, 0.75)

    def test_include_exclude_taxa_copied(self):
        """Source project's include/exclude taxa lists are copied."""
        self.source_project.default_filters_include_taxa.add(self.taxa[0])
        self.source_project.default_filters_exclude_taxa.add(self.taxa[1])

        _run_command(*self._base_args(), "--target-project", str(self.target_project.pk), "--execute")

        self.target_project.refresh_from_db()
        self.assertIn(self.taxa[0], self.target_project.default_filters_include_taxa.all())
        self.assertIn(self.taxa[1], self.target_project.default_filters_exclude_taxa.all())


class TestEdgeCases(MoveProjectDataSetupMixin, TestCase):
    """Edge cases and boundary conditions."""

    def setUp(self):
        self.owner = _create_user()
        self.source_project = _create_project(self.owner, "Source Project")

    def test_move_deployment_with_no_images(self):
        """Moving an empty deployment should succeed."""
        dep = _create_deployment(self.source_project, name="Empty Dep")
        target = _create_project(self.owner, "Target")

        _run_command(
            "--source-project",
            str(self.source_project.pk),
            "--deployment-ids",
            str(dep.pk),
            "--target-project",
            str(target.pk),
            "--execute",
        )

        dep.refresh_from_db()
        self.assertEqual(dep.project_id, target.pk)

    def test_move_all_deployments_from_source(self):
        """Moving all deployments leaves source project empty."""
        dep1 = _create_deployment(self.source_project, name="Dep 1")
        dep2 = _create_deployment(self.source_project, name="Dep 2")
        _create_captures(dep1, count=2)
        _create_captures(dep2, count=2)
        target = _create_project(self.owner, "Target")

        _run_command(
            "--source-project",
            str(self.source_project.pk),
            "--deployment-ids",
            f"{dep1.pk},{dep2.pk}",
            "--target-project",
            str(target.pk),
            "--execute",
        )

        self.assertEqual(Deployment.objects.filter(project=self.source_project).count(), 0)
        self.assertEqual(SourceImage.objects.filter(project=self.source_project).count(), 0)
        self.assertEqual(Deployment.objects.filter(project=target).count(), 2)

    def test_move_multiple_deployments(self):
        """Multiple comma-separated deployment IDs work."""
        dep1 = _create_deployment(self.source_project, name="Dep 1")
        dep2 = _create_deployment(self.source_project, name="Dep 2")
        _create_captures(dep1, count=2)
        _create_captures(dep2, count=3)
        target = _create_project(self.owner, "Target")

        _run_command(
            "--source-project",
            str(self.source_project.pk),
            "--deployment-ids",
            f"{dep1.pk},{dep2.pk}",
            "--target-project",
            str(target.pk),
            "--execute",
        )

        self.assertEqual(SourceImage.objects.filter(project=target).count(), 5)

    def test_target_already_has_taxa(self):
        """Moving to a project that already has taxa doesn't create duplicates."""
        dep = _create_deployment(self.source_project, name="Dep A")
        imgs = _create_captures(dep, count=2)
        taxa = _create_taxa(self.source_project)
        # Create occurrences referencing both taxa (2 images, 2 taxa → both used as determinations)
        _create_occurrences(dep, taxa, imgs)

        target = _create_project(self.owner, "Target")
        target.taxa.add(taxa[0])  # Pre-existing

        _run_command(
            "--source-project",
            str(self.source_project.pk),
            "--deployment-ids",
            str(dep.pk),
            "--target-project",
            str(target.pk),
            "--execute",
        )

        # taxa[0] should appear only once (no duplicate from .add())
        self.assertEqual(target.taxa.filter(pk=taxa[0].pk).count(), 1)
        # taxa[1] should also be linked (referenced by second occurrence's determination)
        self.assertIn(taxa[1], target.taxa.all())
