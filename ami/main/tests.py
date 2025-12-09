import datetime
import logging
import typing
from io import BytesIO

from django.contrib.auth.models import AnonymousUser
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection, models
from django.test import TestCase, override_settings
from guardian.shortcuts import assign_perm, get_perms, remove_perm
from PIL import Image
from rest_framework import status
from rest_framework.test import APIRequestFactory, APITestCase
from rich import print

from ami.exports.models import DataExport
from ami.jobs.models import VALID_JOB_TYPES, Job
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
    SourceImageUpload,
    Tag,
    TaxaList,
    Taxon,
    TaxonRank,
    group_images_into_events,
)
from ami.ml.models.pipeline import Pipeline
from ami.ml.models.processing_service import ProcessingService
from ami.ml.models.project_pipeline_config import ProjectPipelineConfig
from ami.tests.fixtures.main import create_captures, create_occurrences, create_taxa, setup_test_project
from ami.tests.fixtures.storage import populate_bucket
from ami.users.models import User
from ami.users.roles import BasicMember, Identifier, ProjectManager

logger = logging.getLogger(__name__)


class TestProjectSetup(TestCase):
    def test_project_creation(self):
        project = Project.objects.create(name="New Project with Defaults", create_defaults=True)
        self.assertIsInstance(project, Project)

    def test_default_related_models(self):
        """Test that the default related models are created correctly when a project is created."""
        project = Project.objects.create(name="New Project with Defaults", create_defaults=True)

        # Check that the project has a default deployment
        self.assertGreaterEqual(project.deployments.count(), 1)
        deployment = project.deployments.first()
        self.assertIsInstance(deployment, Deployment)

        # Check that the deployment has a default site
        self.assertGreaterEqual(project.sites.count(), 1)
        site = project.sites.first()
        self.assertIsInstance(site, Site)

        # Check that the deployment has a default device
        self.assertGreaterEqual(project.devices.count(), 1)
        device = project.devices.first()
        self.assertIsInstance(device, Device)

        # Check that the project has a default source image collection
        self.assertGreaterEqual(project.sourceimage_collections.count(), 1)
        collection = project.sourceimage_collections.first()
        self.assertIsInstance(collection, SourceImageCollection)

    # Disable this test for now, as it requires a more complex setup
    def no_test_default_permissions(self):
        pass

    @override_settings(
        DEFAULT_PROCESSING_SERVICE_NAME="Default Processing Service",
        DEFAULT_PROCESSING_SERVICE_ENDPOINT="http://ml_backend:2009/",
    )
    def test_processing_service_if_configured(self):
        """
        Test that the default processing service is created if the environment variables are set.
        """
        from ami.ml.models.processing_service import get_or_create_default_processing_service

        project = Project.objects.create(name="Test Project for Processing Service", create_defaults=False)

        service = get_or_create_default_processing_service(project=project, register_pipelines=False)
        self.assertIsNotNone(service, "Default processing service should be created if environment variables are set.")
        assert service is not None  # For type checking
        self.assertIsNotNone(service.endpoint_url)
        self.assertIsNotNone(service.name)
        self.assertGreaterEqual(project.processing_services.count(), 1)

    @override_settings(
        DEFAULT_PROCESSING_SERVICE_NAME=None,
        DEFAULT_PROCESSING_SERVICE_ENDPOINT=None,
    )
    def test_processing_service_if_not_configured(self):
        """
        Test that the default processing service is not created if the environment variables are not set.
        """
        from ami.ml.models.processing_service import get_or_create_default_processing_service

        project = Project.objects.create(name="Test Project for Processing Service", create_defaults=False)

        service = get_or_create_default_processing_service(project=project)
        self.assertIsNone(
            service, "Default processing service should not be created if environment variables are not set."
        )

    @override_settings(
        DEFAULT_PROCESSING_SERVICE_NAME="Default Processing Service",
        DEFAULT_PROCESSING_SERVICE_ENDPOINT="http://ml_backend:2000/",
        DEFAULT_PIPELINES_ENABLED=[],  # All pipelines DISABLED by default
    )
    def test_processing_service_with_disabled_pipelines(self):
        """
        Test that the default processing service is created with all pipelines disabled
        if DEFAULT_PIPELINES_ENABLED is any empty list.
        """
        project = Project.objects.create(name="Test Project for Processing Service", create_defaults=True)
        processing_service = project.processing_services.first()
        assert processing_service is not None
        # There should be at least two pipelines created by default
        self.assertGreaterEqual(processing_service.pipelines.count(), 2)
        # All pipelines should be disabled by default
        project_pipeline_configs = ProjectPipelineConfig.objects.filter(project=project)
        for config in project_pipeline_configs:
            self.assertFalse(
                config.enabled,
                f"Pipeline {config.pipeline.name} should be disabled for project {project.name}.",
            )

    @override_settings(
        DEFAULT_PROCESSING_SERVICE_NAME="Default Processing Service",
        DEFAULT_PROCESSING_SERVICE_ENDPOINT="http://ml_backend:2000/",
        DEFAULT_PIPELINES_ENABLED=None,  # All pipelines ENABLED by default
    )
    def test_processing_service_with_enabled_pipelines(self):
        """
        Test that the default processing service is created with all pipelines enabled
        if the DEFAULT_PIPELINES_ENABLED setting is None (or missing).
        """
        project = Project.objects.create(name="Test Project for Processing Service", create_defaults=True)
        processing_service = project.processing_services.first()
        assert processing_service is not None
        # There should be at least two pipelines created by default
        self.assertGreaterEqual(processing_service.pipelines.count(), 2)
        # All pipelines should be enabled by default
        project_pipeline_configs = ProjectPipelineConfig.objects.filter(project=project)
        for config in project_pipeline_configs:
            self.assertTrue(
                config.enabled,
                f"Pipeline {config.pipeline.name} should be enabled for project {project.name}.",
            )

    @override_settings(
        DEFAULT_PROCESSING_SERVICE_NAME="Default Processing Service",
        DEFAULT_PROCESSING_SERVICE_ENDPOINT="http://ml_backend:2000/",  # should have at least two pipelines
        DEFAULT_PIPELINES_ENABLED=["constant"],
    )
    def test_existing_processing_service_new_project(self):
        """
        Create a new project, enable all pipelines.
        Create a 2nd project, ensure that the same processing service is used and only the enabled pipelines are
        registered.
        """
        enabled_pipelines = ["constant"]

        project_one = Project.objects.create(name="Test Project One", create_defaults=True)

        # Enable all pipelines for the first project
        ProjectPipelineConfig.objects.filter(project=project_one).update(enabled=True)

        project_two = Project.objects.create(name="Test Project Two", create_defaults=True)

        project_one_processing_service = project_one.processing_services.first()
        project_two_processing_service = project_two.processing_services.first()

        assert project_one_processing_service is not None
        assert project_two_processing_service is not None

        # Ensure only the same processing service instance is used (and they are not None)
        self.assertEqual(
            project_one_processing_service,
            project_two_processing_service,
            "Both projects should use the same processing service instance.",
        )

        # Ensure that only the enabled pipelines are enabled for the second project
        project_two_pipeline_configs = ProjectPipelineConfig.objects.filter(project=project_two)
        self.assertGreaterEqual(project_two_pipeline_configs.count(), 2, "Project should have at least two pipelines.")
        for config in project_two_pipeline_configs:
            if config.pipeline.slug in enabled_pipelines:
                self.assertTrue(
                    config.enabled,
                    f"Pipeline {config.pipeline.name} should be enabled for project {project_two.name}.",
                )
            else:
                self.assertFalse(
                    config.enabled,
                    f"Pipeline {config.pipeline.name} should not be enabled for project {project_two.name}.",
                )


class TestImageGrouping(TestCase):
    def setUp(self) -> None:
        print(f"Currently active database: {connection.settings_dict}")
        self.project, self.deployment = setup_test_project()
        return super().setUp()

    def test_grouping(self):
        num_nights = 3
        images_per_night = 3

        create_captures(
            deployment=self.deployment,
            num_nights=num_nights,
            images_per_night=images_per_night,
            interval_minutes=10,
        )

        events = group_images_into_events(
            deployment=self.deployment,
            max_time_gap=datetime.timedelta(hours=2),
        )

        assert len(events) == num_nights
        for event in events:
            assert event.captures.count() == images_per_night

    def test_pruning_empty_events(self):
        from ami.main.models import delete_empty_events

        captures = create_captures(deployment=self.deployment)
        events = Event.objects.filter(captures__in=captures).distinct()

        for event in events:
            event.captures.all().delete()

        delete_empty_events(deployment=self.deployment)

        remaining_events = Event.objects.filter(pk__in=[event.pk for event in events])

        assert remaining_events.count() == 0

    def test_setting_image_dimensions(self):
        from ami.main.models import set_dimensions_for_collection

        image_width, image_height = 100, 100

        captures = create_captures(deployment=self.deployment)
        events = Event.objects.filter(captures__in=captures).distinct()

        for event in events:
            first_image = event.captures.first()
            assert first_image is not None
            first_image.width, first_image.height = image_width, image_height
            first_image.save()
            set_dimensions_for_collection(event=event)

            for capture in event.captures.all():
                # print(capture.path, capture.width, capture.height)
                assert (capture.width == image_width) and (capture.height == image_height)


# This test is disabled because it requires certain data to be present in the database
# and data in a configured S3 bucket. Will require Minio or something like it to be running.
# from unittest import TestCase as UnitTestCase
# class TestExistingDatabase(UnitTestCase):
#     def test_sync_source_images(self):
#         from django.db import models
#
#         from ami.main.models import Deployment
#         from ami.tasks import sync_source_images
#
#         deployment = Deployment.objects.get(
#             name="Test",
#         )
#         sync_source_images(deployment.pk)
#
#         # Get deployment with the most captures
#         deployment = (
#             Deployment.objects.annotate(captures_count=models.Count("captures")).order_by("-captures_count").first()
#         )
#         if deployment:
#             sync_source_images(deployment.pk)


class TestEvents(TestCase):
    def setUp(self) -> None:
        project, deployment = setup_test_project()
        create_captures(deployment=deployment, num_nights=2, images_per_night=5)
        self.project = project
        self.deployment = deployment
        return super().setUp()

    def test_event_calculated_fields(self):
        event, event_2 = self.deployment.events.all()

        # Test initial calculated fields
        event.update_calculated_fields(save=True)
        event.refresh_from_db()

        self.assertEqual(event.captures_count, 5)
        self.assertIsNotNone(event.detections_count)
        self.assertIsNotNone(event.occurrences_count)

        initial_update_date = event.calculated_fields_updated_at
        self.assertIsNotNone(initial_update_date)

        # Add more captures and test that the calculated fields are updated
        for capture in event_2.captures.all():
            event.captures.add(capture)  # type: ignore

        event.update_calculated_fields(save=True)
        event.refresh_from_db()

        self.assertEqual(event.captures_count, event.get_captures_count())
        self.assertEqual(event.captures_count, 10)
        self.assertGreater(event.calculated_fields_updated_at, initial_update_date)  # type: ignore

    def test_event_calculated_fields_batch(self):
        from ami.main.models import update_calculated_fields_for_events

        last_updated_timestamps = []
        for event in self.deployment.events.all().order_by("pk"):
            self.assertEqual(event.captures_count, event.get_captures_count())
            self.assertEqual(event.detections_count, event.get_detections_count())
            self.assertEqual(event.occurrences_count, event.get_occurrences_count())
            self.assertIsNotNone(event.calculated_fields_updated_at)
            last_updated_timestamps.append(event.calculated_fields_updated_at)

        # Delete all detections for all source images and test that the calculated fields are updated
        from ami.main.models import Detection

        Detection.objects.all().delete()

        update_calculated_fields_for_events(last_updated=datetime.datetime(3000, 1, 1, 0, 0, 0))

        for event, last_updated in zip(self.deployment.events.all().order_by("pk"), last_updated_timestamps):
            self.assertEqual(event.captures_count, event.get_captures_count())
            self.assertEqual(event.detections_count, event.get_detections_count())
            self.assertEqual(event.occurrences_count, event.get_occurrences_count())
            self.assertGreater(event.calculated_fields_updated_at, last_updated)

        # Delete all captures and test that the calculated fields are updated
        self.deployment.captures.all().delete()

        update_calculated_fields_for_events(last_updated=datetime.datetime(3000, 1, 1, 0, 0, 0))

        for event, last_updated in zip(self.deployment.events.all().order_by("pk"), last_updated_timestamps):
            self.assertEqual(event.captures_count, event.get_captures_count())
            self.assertEqual(event.detections_count, event.get_detections_count())
            self.assertEqual(event.occurrences_count, event.get_occurrences_count())
            self.assertGreater(event.calculated_fields_updated_at, last_updated)  # type: ignore


class TestDuplicateFieldsOnChildren(TestCase):
    def setUp(self) -> None:
        from ami.main.models import Deployment, Project

        self.project_one = Project.objects.create(name="Test Project One")
        self.project_two = Project.objects.create(name="Test Project Two")
        self.deployment = Deployment.objects.create(name="Test Deployment", project=self.project_one)

        create_captures(deployment=self.deployment)
        self.deployment.save(regroup_async=False)  # Ensure events are grouped immediately
        create_taxa(project=self.project_one)
        create_taxa(project=self.project_two)
        create_occurrences(deployment=self.deployment, num=1)

        return super().setUp()

    def test_initial_project(self):
        assert self.deployment.project == self.project_one
        assert self.deployment.captures.first().project == self.project_one
        assert self.deployment.events.first().project == self.project_one
        assert self.deployment.occurrences.first().project == self.project_one
        assert self.deployment.occurrences.first().detections.first().source_image.project == self.project_one

    def test_change_project(self):
        self.deployment.project = self.project_two
        self.deployment.save()

        self.deployment.refresh_from_db()

        assert self.deployment.project == self.project_two
        assert self.deployment.captures.first().project == self.project_two
        assert self.deployment.events.first().project == self.project_two
        assert self.deployment.occurrences.first().project == self.project_two

    def test_delete_project(self):
        self.project_one.delete()

        self.deployment.refresh_from_db()

        assert self.deployment.project is None
        assert self.deployment.captures.first().project is None
        assert self.deployment.events.first().project is None
        assert self.deployment.occurrences.first().project is None


class TestSourceImageCollections(TestCase):
    def setUp(self) -> None:
        from ami.main.models import Deployment, Project

        self.project_one = Project.objects.create(name="Test Project One")
        self.deployment = Deployment.objects.create(name="Test Deployment", project=self.project_one)

        create_captures(deployment=self.deployment, num_nights=2, images_per_night=10, interval_minutes=1)

        return super().setUp()

    def test_random_sample(self):
        from ami.main.models import SourceImageCollection

        sample_size = 10

        collection = SourceImageCollection.objects.create(
            name="Test Random Source Image Collection",
            project=self.project_one,
            method="random",
            kwargs={"size": sample_size},
        )
        collection.save()
        collection.populate_sample()

        assert collection.images.count() == sample_size

    def test_manual_sample(self):
        from ami.main.models import SourceImageCollection

        images = self.deployment.captures.all()

        collection = SourceImageCollection.objects.create(
            name="Test Manual Source Image Collection",
            project=self.project_one,
            method="manual",
            kwargs={"image_ids": [image.pk for image in images]},
        )
        collection.save()
        collection.populate_sample()

        assert collection.images.count() == len(images)
        for image in images:
            assert image in collection.images.all()

    def test_interval_sample(self):
        # Ensure that the images are 5 at least minutes apart and less than 6 minutes apart within each event
        # This depends on the test setUp creating images with a 1 minute interval

        from ami.main.models import SourceImageCollection

        minute_interval = 10

        collection = SourceImageCollection.objects.create(
            name="Test Interval Source Image Collection",
            project=self.project_one,
            method="interval",
            kwargs={"minute_interval": minute_interval},
        )
        collection.save()
        collection.populate_sample()

        events = collection.images.values_list("event", flat=True).distinct()
        for event in events:
            last_image = None
            for image in collection.images.filter(event=event):
                if last_image:
                    interval = image.timestamp - last_image.timestamp
                    assert interval >= datetime.timedelta(minutes=minute_interval)
                    assert interval < datetime.timedelta(minutes=minute_interval + 1)
                last_image = image

    def test_interval_with_excluded_events(self):
        from ami.main.models import SourceImageCollection

        minute_interval = 5
        events = self.deployment.events.all()
        excluded_event = events.first()
        assert excluded_event is not None

        collection = SourceImageCollection.objects.create(
            name="Test Interval With Excluded Events",
            project=self.project_one,
            method="interval",
            kwargs={"minute_interval": minute_interval, "exclude_events": [excluded_event.pk]},
        )
        collection.save()
        collection.populate_sample()

        # Ensure that no images from the excluded event are in the collection
        for image in collection.images.all():
            assert image.event != excluded_event

    def test_extra_arguments(self):
        # Assert that a value error is raised when trying to call a sampling method with extra arguments
        from ami.main.models import SourceImageCollection

        collection = SourceImageCollection.objects.create(
            name="Test Extra Arguments Collection",
            project=self.project_one,
            method="interval",
            kwargs={"birthday": True, "cake": "chocolate"},
        )
        collection.save()

        with self.assertRaises(TypeError):
            collection.populate_sample()

    def test_last_and_random(self):
        from ami.main.models import SourceImageCollection

        collection = SourceImageCollection.objects.create(
            name="Test Last and Random Collection",
            project=self.project_one,
            method="last_and_random_from_each_event",
            kwargs={"num_each": 2},
        )
        collection.save()
        collection.populate_sample()

        collection_images = collection.images.all()

        # 2 nights, last image from each, 2 additional random images from each
        self.assertEqual(collection_images.count(), 6)

        for event in self.project_one.events.all():
            last_capture = event.captures.last()
            assert last_capture
            # ensure last_capture is in the collection
            self.assertIn(last_capture, collection_images)
            # ensure there are 2 other random images from each event
            self.assertEqual(collection_images.filter(event=event).exclude(pk=last_capture.pk).count(), 2)

    def test_random_from_each_event(self):
        from ami.main.models import SourceImageCollection

        collection = SourceImageCollection.objects.create(
            name="Test Random From Each Event Collection",
            project=self.project_one,
            method="random_from_each_event",
            kwargs={"num_each": 2},
        )
        collection.save()
        collection.populate_sample()

        collection_images = collection.images.all()

        # 2 nights, 2 random images from each
        assert collection_images.count() == 4

        # Test that there are 2 images from each event
        for event in self.project_one.events.all():
            assert collection_images.filter(event=event).count() == 2

    def test_common_combined_deployment_ids(self):
        """Test that common_combined sampling method correctly filters by deployment_ids"""
        from ami.main.models import Deployment, SourceImageCollection

        # Create two additional deployments
        deployment_two = Deployment.objects.create(name="Test Deployment Two", project=self.project_one)
        deployment_three = Deployment.objects.create(name="Test Deployment Three", project=self.project_one)

        # Create captures for each deployment
        create_captures(deployment=deployment_two, num_nights=2, images_per_night=10, interval_minutes=1)
        create_captures(deployment=deployment_three, num_nights=2, images_per_night=10, interval_minutes=1)

        # Verify that we have images from the deployments
        assert deployment_two.captures.count() > 0
        assert deployment_three.captures.count() > 0

        # Create collection using only deployment_two and deployment_three
        collection = SourceImageCollection.objects.create(
            name="Test Common Combined Deployment IDs",
            project=self.project_one,
            method="common_combined",
            kwargs={
                "deployment_ids": [deployment_two.pk, deployment_three.pk],
                "shuffle": True,
                "max_num": 100,
            },
        )
        collection.save()
        collection.populate_sample()

        collection_images = collection.images.all()

        # Verify images only come from specified deployments
        self.assertEqual(
            collection_images.filter(deployment__in=[deployment_two, deployment_three]).count(),
            collection_images.count(),
        )
        self.assertEqual(collection_images.filter(deployment=self.deployment).count(), 0)

        # Verify we got images from both specified deployments
        self.assertGreater(collection_images.filter(deployment=deployment_two).count(), 0)
        self.assertGreater(collection_images.filter(deployment=deployment_three).count(), 0)

    def test_interval_sample_multiple_deployments(self):
        """
        Ensure interval sampling applies independently per deployment (station).

        Create two deployments with captures spaced 1 minute apart for a few hours,
        then sample with `minute_interval=60` and verify the total sampled count equals
        the sum of per-deployment hourly samples.
        """
        from ami.main.models import SourceImage, SourceImageCollection, sample_captures_by_interval

        # Create a new project and two deployments
        project = Project.objects.create(name="Multi Dep Project", create_defaults=False)
        dep1 = Deployment.objects.create(name="Dep One", project=project)
        dep2 = Deployment.objects.create(name="Dep Two", project=project)

        # Create captures: 3 hours worth of captures at 1-minute intervals (~180 images)
        images_per_night = 180
        create_captures(deployment=dep1, num_nights=1, images_per_night=images_per_night, interval_minutes=1)
        create_captures(deployment=dep2, num_nights=1, images_per_night=images_per_night, interval_minutes=1)

        collection = SourceImageCollection.objects.create(
            name="Test Multi-Dep Interval",
            project=project,
            method="interval",
            kwargs={"minute_interval": 60},
        )
        collection.save()
        collection.populate_sample()

        sampled_count = collection.images.count()

        # Compute expected by sampling each deployment separately
        expected = 0
        for dep in [dep1, dep2]:
            qs = SourceImage.objects.filter(deployment=dep).exclude(timestamp=None).order_by("timestamp")
            expected += len(list(sample_captures_by_interval(60, qs)))

        self.assertEqual(sampled_count, expected)


class TestTaxonomy(TestCase):
    def setUp(self) -> None:
        project, deployment = setup_test_project()
        create_taxa(project=project)
        return super().setUp()

    def test_tree(self):
        """
        example_tree = {
            'taxon': <Taxon: Lepidoptera (order)>,
            'children': [
                {
                    'taxon': <Taxon: Vanessa (genus)>,
                    'children': [
                        {'taxon': <Taxon: Vanessa atalanta (species)>, 'children': []},
                        {'taxon': <Taxon: Vanessa cardui (species)>, 'children': []},
                        {'taxon': <Taxon: Vanessa itea (species)>, 'children': []}
                    ]
                }
            ]
        }
        """
        from ami.main.models import Taxon

        tree = Taxon.objects.tree()
        self.assertDictContainsSubset({"taxon": Taxon.objects.get(name="Lepidoptera")}, tree)

    def test_rank_formatting(self):
        """
        Test that all ranks in the DB are uppercase and match a TaxonRank value
        """

        from ami.main.models import Taxon

        for taxon in Taxon.objects.all():
            self.assertIn(taxon.rank, [rank.name for rank in TaxonRank])
            self.assertEqual(taxon.rank, taxon.rank.upper())

    def _test_filtered_tree(self, filter_ranks: list[TaxonRank]):
        """ """
        filter_rank_names = [rank.name for rank in filter_ranks]
        expected_taxa = list(Taxon.objects.filter(rank__in=filter_rank_names).all())

        tree = Taxon.objects.tree(filter_ranks=filter_ranks)

        # collect all Taxon objects in tree to test against expected
        def _tree_taxa(tree: dict) -> list[Taxon]:
            taxa = []
            taxa.append(tree["taxon"])
            for child in tree["children"]:
                taxa.extend(_tree_taxa(child))
            return taxa

        taxa_in_tree = _tree_taxa(tree)
        expected_taxa = expected_taxa

        self.assertListEqual(taxa_in_tree, expected_taxa)

    def test_tree_filtered_families(self):
        # Try skipping over family
        filter_ranks = [TaxonRank.ORDER, TaxonRank.GENUS, TaxonRank.SPECIES]
        self._test_filtered_tree(filter_ranks)

    def test_tree_filtered_genera(self):
        # Try skipping over genus
        filter_ranks = [TaxonRank.ORDER, TaxonRank.FAMILY, TaxonRank.SPECIES]
        self._test_filtered_tree(filter_ranks)

    def test_tree_filtered_species(self):
        # Try skipping over species
        filter_ranks = [TaxonRank.ORDER, TaxonRank.FAMILY, TaxonRank.GENUS]
        self._test_filtered_tree(filter_ranks)

    def test_tree_filtered_root(self):
        # Try skipping over order
        root = Taxon.objects.root()
        filter_ranks = [rank for rank in TaxonRank if rank != root.get_rank()]
        with self.assertRaises(ValueError):
            self._test_filtered_tree(filter_ranks)

    def test_update_parents(self):
        for taxon in Taxon.objects.all():
            taxon.update_parents(save=True)
            taxon.refresh_from_db()
            self._test_parents_json(taxon)

    def test_update_all_parents(self):
        from ami.main.models import Taxon

        Taxon.objects.update_all_parents()

        for taxon in Taxon.objects.exclude(parent=None):
            self._test_parents_json(taxon)

    def _test_parents_json(self, taxon):
        from ami.main.models import TaxonParent, TaxonRank

        # Ensure all taxon have parents_json populated
        if taxon.parent:
            self.assertGreater(
                len(taxon.parents_json),
                0,
                f"Taxon {taxon} has no parents_json, even though it has the parent {taxon.parent}",
            )
        else:
            self.assertEqual(
                len(taxon.parents_json),
                0,
                f"Taxon {taxon} has parents_json, even though it has no parent",
            )

        for parent_taxon in taxon.parents_json:
            # Ensure all parents_json are TaxonParent objects
            self.assertIsInstance(parent_taxon, TaxonParent)
            self.assertIsInstance(parent_taxon.rank, TaxonRank)

            # Ensure a parent rank is not the same as the taxon itself
            self.assertNotEqual(taxon.rank, parent_taxon.rank)

        # Ensure the order of all parents is correct
        sorted_parents = sorted(taxon.parents_json, key=lambda x: x.rank)
        self.assertListEqual(taxon.parents_json, sorted_parents)

        # For each rank, test that it is lower than the previous rank
        previous_rank = None
        for parent in taxon.parents_json:
            if previous_rank:
                self.assertGreater(parent.rank, previous_rank)
            previous_rank = parent.rank

        # Ensure last item in parents_json is the taxon's direct parent
        if taxon.parent:
            direct_parent = taxon.parents_json[-1]
            self.assertEqual(
                direct_parent.id,
                taxon.parent_id,
                (
                    f"Taxon {taxon} has incorrect direct parent: {direct_parent.name} != {taxon.parent.name}. "
                    f"All parents: {taxon.parents_json}"
                ),
            )


class TestTaxonomyViews(TestCase):
    def setUp(self) -> None:
        project_one, deployment_one = setup_test_project(reuse=False)
        project_two, deployment_two = setup_test_project(reuse=False)
        create_taxa(project=project_one)
        create_taxa(project=project_two)
        # Show project & deployment IDs
        print(f"Project One: {project_one}")
        print(f"Project Two: {project_two}")
        print(f"Deployment One: {deployment_one.pk}")
        print(f"Deployment Two: {deployment_two.pk}")
        create_captures(deployment=deployment_one)
        create_captures(deployment=deployment_two)
        create_occurrences(deployment=deployment_one, num=5)
        create_occurrences(deployment=deployment_two, num=5)
        self.project_one = project_one
        self.project_two = project_two
        return super().setUp()

    def test_occurrences_for_project(self):
        # Test that occurrences are specific to each project
        for project in [self.project_one, self.project_two]:
            response = self.client.get(f"/api/v2/occurrences/?project_id={project.pk}")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["count"], Occurrence.objects.filter(project=project).count())

    def no_test_project_species_list(self):
        """
        Test that the taxa for a project (of species rank) are returned from the API

        @TODO this randomly fails, need to investigate
        """
        species_for_project = self.project_one.taxa.filter(rank=TaxonRank.SPECIES.name)
        # Ensure there are species for the project
        self.assertGreater(species_for_project.count(), 0)

        response = self.client.get(
            "/api/v2/taxa/",
            {
                "project": self.project_one.pk,
                "rank": TaxonRank.SPECIES.name,
            },
        )

        taxa_returned = response.json()["results"]
        self.assertGreater(len(taxa_returned), 0)

        # Assert only species are returned
        for taxon in taxa_returned:
            self.assertEqual(taxon["rank"], str(TaxonRank.SPECIES))

        # Compare lists of taxa:
        self.assertListEqual(
            sorted([taxon.name for taxon in species_for_project]),
            sorted([taxon["name"] for taxon in taxa_returned]),
            "Expected taxa for project (list one) do not match taxa in API response (list two)",
        )

    def _test_taxa_for_project(self, project: Project):
        """
        Ensure the annotation counts are specific to each project, not global counts
        of occurrences and detections.
        """
        from ami.main.models import Taxon

        response = self.client.get(f"/api/v2/taxa/?project_id={project.pk}")
        self.assertEqual(response.status_code, 200)
        project_occurred_taxa = Taxon.objects.filter(occurrences__project=project).distinct()
        # project_any_taxa = Taxon.objects.filter(projects=project)
        self.assertGreater(project_occurred_taxa.count(), 0)
        self.assertEqual(response.json()["count"], project_occurred_taxa.count())

        # Check counts for each taxon
        results = response.json()["results"]
        for taxon_result in results:
            taxon: Taxon = Taxon.objects.get(pk=taxon_result["id"])
            project_occurrences = taxon.occurrences.filter(project=project).count()
            # project_detections = taxon.detections.filter(project=project).count()
            self.assertEqual(taxon_result["occurrences_count"], project_occurrences)

    def test_taxa_for_project(self):
        for project in [self.project_one, self.project_two]:
            self._test_taxa_for_project(project)

    def test_taxon_detail(self):
        from ami.main.models import Taxon

        taxon = Taxon.objects.last()
        assert taxon is not None
        print("Testing taxon", taxon, taxon.pk)
        response = self.client.get(f"/api/v2/taxa/{taxon.pk}/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["name"], taxon.name)

    def test_recursive_occurrence_counts_single(self):
        # First, assert that we have taxa with parents and occurrences
        from ami.main.models import Taxon

        taxa = Taxon.objects.exclude(parent=None).filter(occurrences__isnull=False)
        self.assertGreater(taxa.count(), 0)
        for taxon in taxa:
            occurrence_count_direct = taxon.occurrences.count()
            occurrence_count_total = taxon.occurrences_count_recursive()
            self.assertGreaterEqual(occurrence_count_total, occurrence_count_direct)

            # Manually add up the occurrences for each taxon and its children, recursively:
            def _count_occurrences_recursive(taxon):
                count = taxon.occurrences.count()
                for child in taxon.direct_children.all():
                    count += _count_occurrences_recursive(child)
                return count

            manual_count = _count_occurrences_recursive(taxon)
            self.assertEqual(occurrence_count_total, manual_count)

        # The top level test taxa should have all occurrences
        top_level_taxa = Taxon.objects.root()
        count = top_level_taxa.occurrences_count_recursive()
        self.assertGreater(count, 0)
        project_ids = top_level_taxa.projects.values_list("id", flat=True)
        total_occurrences = Occurrence.objects.filter(project__in=project_ids).count()
        self.assertEqual(count, total_occurrences)

    def test_recursive_occurrence_count_from_manager(self):
        from ami.main.models import Taxon

        with self.assertRaises(NotImplementedError):
            taxa_with_counts = Taxon.objects.with_occurrence_counts()
            for taxon in taxa_with_counts:
                occurrence_count_total = taxon.occurrences_count_recursive()
                self.assertEqual(occurrence_count_total, taxon.occurrences_count)

            for taxon in taxa_with_counts:
                occurrence_count_direct = taxon.occurrences.count()
                occurrence_count_total = taxon.occurrences_count_recursive()
                self.assertEqual(occurrence_count_total, occurrence_count_direct)


class TestIdentification(APITestCase):
    def setUp(self) -> None:
        project, deployment = setup_test_project()
        create_taxa(project=project)
        create_captures(deployment=deployment)
        create_occurrences(deployment=deployment, num=5)
        self.project = project
        self.user = User.objects.create_user(  # type: ignore
            email="testuser@insectai.org",
            is_staff=True,
            is_superuser=True,
        )
        self.factory = APIRequestFactory()
        self.client.force_authenticate(user=self.user)
        return super().setUp()

    def test_identification(self):
        from ami.main.models import Identification, Taxon

        """
        Post a new identification suggestion and check that it changed the occurrence's determination.
        """

        suggest_id_endpoint = f"/api/v2/identifications/?project_id={self.project.pk}"
        taxa = Taxon.objects.filter(projects=self.project)
        assert taxa.count() > 1

        occurrence = Occurrence.objects.filter(project=self.project).exclude(determination=None)[0]
        original_taxon = occurrence.determination
        assert original_taxon is not None
        new_taxon = Taxon.objects.exclude(pk=original_taxon.pk)[0]
        comment = "Test identification comment"

        response = self.client.post(
            suggest_id_endpoint,
            {
                "occurrence_id": occurrence.pk,
                "taxon_id": new_taxon.pk,
                "comment": comment,
            },
        )
        self.assertEqual(response.status_code, 201)
        occurrence.refresh_from_db()
        self.assertEqual(occurrence.determination, new_taxon)
        identification = Identification.objects.get(pk=response.json()["id"])
        self.assertEqual(identification.comment, comment)


class TestMovingSourceImages(TestCase):
    previous_subdir = "test/old_subdir"
    prev_sub_subdir_1 = previous_subdir + "/2022"
    prev_sub_subdir_2 = previous_subdir + "/2023"
    new_subdir = "test/new_subdir"
    new_sub_subdir_1 = new_subdir + "/2022"
    new_sub_subdir_2 = new_subdir + "/2023"
    other_subdir = "test/other_subdir"
    images_per_dir = 10

    def setUp(self) -> None:
        project, deployment = setup_test_project()
        create_captures(
            deployment=deployment, subdir=self.prev_sub_subdir_1, num_nights=1, images_per_night=self.images_per_dir
        )
        create_captures(
            deployment=deployment, subdir=self.prev_sub_subdir_2, num_nights=1, images_per_night=self.images_per_dir
        )
        create_captures(
            deployment=deployment, subdir=self.other_subdir, num_nights=1, images_per_night=self.images_per_dir
        )
        self.project = project
        self.deployment = deployment
        return super().setUp()

    def test_audit_subdirs(self):
        counts = self.deployment.audit_subdir_of_captures(ignore_deepest=False)
        expected_counts = {
            self.prev_sub_subdir_1: self.images_per_dir,
            self.prev_sub_subdir_2: self.images_per_dir,
            self.other_subdir: self.images_per_dir,
        }
        self.assertDictEqual(dict(counts), expected_counts)

    def test_audit_subdirs_ignore_date_folder(self):
        counts = self.deployment.audit_subdir_of_captures(ignore_deepest=True)
        other_subdir_truncated = self.other_subdir.rsplit("/", 1)[0]
        expected_counts = {
            self.previous_subdir: self.images_per_dir * 2,
            other_subdir_truncated: self.images_per_dir,
        }
        self.assertDictEqual(dict(counts), expected_counts)

    def test_update_subdir(self):
        # Move all images to a new subdirectory
        self.deployment.update_subdir_of_captures(new_subdir=self.new_subdir, previous_subdir=self.previous_subdir)

        counts = self.deployment.audit_subdir_of_captures()
        expected_counts = {
            self.new_sub_subdir_1: self.images_per_dir,
            self.new_sub_subdir_2: self.images_per_dir,
            self.other_subdir: self.images_per_dir,
        }
        self.assertDictEqual(dict(counts), expected_counts)


class TestProjectSettingsFiltering(APITestCase):
    """Test  Project Settings filter by project_id"""

    def setUp(self) -> None:
        for _ in range(3):
            project, deployment = setup_test_project(reuse=False)
            create_taxa(project=project)
            create_captures(deployment=deployment)
            create_occurrences(deployment=deployment, num=5)
        self.project_ids = [project.pk for project in Project.objects.all()]

        self.user = User.objects.create_user(  # type: ignore
            email="testuser@insectai.org",
            is_staff=True,
        )
        self.factory = APIRequestFactory()
        self.client.force_authenticate(user=self.user)
        return super().setUp()

    def test_project_summary(self):
        project_id = self.project_ids[1]
        endpoint_url = f"/api/v2/status/summary/?project_id={project_id}"
        response = self.client.get(endpoint_url)
        response_data = response.json()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        project = Project.objects.get(pk=project_id)

        self.assertEqual(response_data["deployments_count"], project.deployments_count())
        self.assertEqual(
            response_data["taxa_count"],
            Taxon.objects.annotate(occurrences_count=models.Count("occurrences"))
            .filter(
                occurrences_count__gt=0,
                occurrences__determination_score__gte=0,
                occurrences__project=project,
            )
            .distinct()
            .count(),
        )
        self.assertEqual(
            response_data["events_count"],
            Event.objects.filter(deployment__project=project, deployment__isnull=False).count(),
        )
        self.assertEqual(
            response_data["captures_count"], SourceImage.objects.filter(deployment__project=project).count()
        )
        self.assertEqual(
            response_data["occurrences_count"],
            Occurrence.objects.filter(
                project=project,
                determination_score__gte=0,
                event__isnull=False,
            ).count(),
        )
        self.assertEqual(
            response_data["captures_count"], SourceImage.objects.filter(deployment__project=project).count()
        )

    def test_project_collections(self):
        project_id = self.project_ids[1]
        project = Project.objects.get(pk=project_id)
        endpoint_url = f"/api/v2/captures/collections/?project_id={project_id}"
        response = self.client.get(endpoint_url)
        response_data = response.json()
        expected_project_collection_ids = {
            source_image_collection.id
            for source_image_collection in SourceImageCollection.objects.filter(project=project)
        }
        response_source_image_collection_ids = {result.get("id") for result in response_data["results"]}
        self.assertEqual(response_source_image_collection_ids, expected_project_collection_ids)

    def test_project_pipelines(self):
        project_id = self.project_ids[0]
        project = Project.objects.get(pk=project_id)
        endpoint_url = f"/api/v2/ml/pipelines/?project_id={project_id}"
        response = self.client.get(endpoint_url)
        response_data = response.json()

        expected_project_pipeline_ids = {pipeline.id for pipeline in Pipeline.objects.filter(projects=project)}
        response_pipeline_ids = {pipeline.get("id") for pipeline in response_data["results"]}
        self.assertEqual(response_pipeline_ids, expected_project_pipeline_ids)

    def test_project_storage(self):
        project_id = self.project_ids[0]
        project = Project.objects.get(pk=project_id)
        endpoint_url = f"/api/v2/storage/?project_id={project_id}"
        response = self.client.get(endpoint_url)
        response_data = response.json()
        expected_storage_ids = {storage.id for storage in S3StorageSource.objects.filter(project=project)}
        response_storage_ids = {storage.get("id") for storage in response_data["results"]}
        self.assertEqual(response_storage_ids, expected_storage_ids)

    def test_project_sites(self):
        project_id = self.project_ids[1]
        project = Project.objects.get(pk=project_id)
        endpoint_url = f"/api/v2/deployments/sites/?project_id={project_id}"
        response = self.client.get(endpoint_url)
        response_data = response.json()
        exepcted_site_ids = {site.id for site in Site.objects.filter(project=project)}
        response_site_ids = {site.get("id") for site in response_data["results"]}
        self.assertEqual(response_site_ids, exepcted_site_ids)

    def test_project_devices(self):
        project_id = self.project_ids[1]
        project = Project.objects.get(pk=project_id)
        endpoint_url = f"/api/v2/deployments/devices/?project_id={project_id}"
        response = self.client.get(endpoint_url)
        response_data = response.json()
        exepcted_device_ids = {device.id for device in Device.objects.filter(project=project)}
        response_device_ids = {device.get("id") for device in response_data["results"]}
        self.assertEqual(response_device_ids, exepcted_device_ids)


class TestProjectOwnerAutoAssignment(APITestCase):
    def setUp(self) -> None:
        self.user_1 = User.objects.create_user(email="testuser@insectai.org", is_staff=True, is_superuser=True)
        self.factory = APIRequestFactory()
        self.client.force_authenticate(user=self.user_1)
        return super().setUp()

    def test_can_auto_assign_project_owner(self):
        project_endpoint = "/api/v2/projects/"
        request = {"name": "Test Project1234", "description": "Test Description"}
        self.client.post(project_endpoint, request)
        project = Project.objects.filter(name=request["name"]).first()
        self.assertEqual(self.user_1.id, project.owner.id)


class TestProjectPermissions(APITestCase):
    def _create_project(self, owner, member):
        self.project = Project.objects.create(name="T Project", description="Test Description", owner=owner)
        self.project.members.add(member)

    def setUp(self) -> None:
        # Create users
        self.superuser = User.objects.create_superuser(
            email="superuser@insectai.org",
            password="password123",
            is_staff=True,
        )
        self.owner = User.objects.create_user(email="owner@insectai.org", is_staff=True)
        self.new_owner = User.objects.create_user(email="new_owner@insectai.org", is_staff=False)
        self.member = User.objects.create_user(email="member@insectai.org", is_staff=False)
        self.other_user = User.objects.create_user(email="other@insectai.org", is_staff=False)
        # Create a staff user
        self.staff_user = User.objects.create_user(
            email="staffuser@insectai.org",
            password="password123",
            is_staff=True,
        )
        # Create a regular user
        self.regular_user = User.objects.create_user(
            email="regularuser@insectai.org",
            password="password123",
        )

        # API endpoint for creating projects
        self.project_create_endpoint = "/api/v2/projects/"
        # Create a project
        self._create_project(self.owner, self.member)
        # Setup the request factory and authenticate as owner by default
        self.factory = APIRequestFactory()

    def test_owner_permissions(self):
        # Owner has view, change, and delete permissions
        self.assertTrue(self.owner.has_perm(Project.Permissions.VIEW_PROJECT, self.project))
        self.assertTrue(self.owner.has_perm(Project.Permissions.UPDATE_PROJECT, self.project))
        self.assertTrue(self.owner.has_perm(Project.Permissions.DELETE_PROJECT, self.project))
        # test permissions from the API
        self.client.force_authenticate(user=self.owner)

        # Owner can view, update, and delete the project
        response = self.client.get(f"/api/v2/projects/{self.project.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        response = self.client.patch(f"/api/v2/projects/{self.project.id}/", {"name": "Updated Project"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        response = self.client.delete(f"/api/v2/projects/{self.project.id}/")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_member_permissions(self):
        # Member has view and change permissions, but not delete
        self.assertTrue(self.member.has_perm(Project.Permissions.VIEW_PROJECT, self.project))
        self.assertFalse(self.member.has_perm(Project.Permissions.DELETE_PROJECT, self.project))

        # test permissions from the API
        # create the project
        self._create_project(self.owner, self.member)

        # Authenticate as member
        self.client.force_authenticate(user=self.member)

        # Member can view and update, but not delete
        response = self.client.get(f"/api/v2/projects/{self.project.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        response = self.client.patch(f"/api/v2/projects/{self.project.id}/", {"name": "Updated Again"})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        response = self.client.delete(f"/api/v2/projects/{self.project.id}/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_other_user_permissions(self):
        # Other users only have view permissions
        self.assertTrue(self.other_user.has_perm(Project.Permissions.VIEW_PROJECT, self.project))
        self.assertFalse(self.other_user.has_perm(Project.Permissions.UPDATE_PROJECT, self.project))
        self.assertFalse(self.other_user.has_perm(Project.Permissions.DELETE_PROJECT, self.project))

        # test permissions from the API
        # Authenticate as other_user
        self.client.force_authenticate(user=self.other_user)

        # Other users can only view
        response = self.client.get(f"/api/v2/projects/{self.project.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        response = self.client.put(f"/api/v2/projects/{self.project.id}/", {"name": "Should Fail"})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        response = self.client.delete(f"/api/v2/projects/{self.project.id}/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_permissions_on_owner_change(self):
        """Test permissions update when the project owner is changed."""

        self._create_project(self.owner, self.member)
        # Change the owner
        self.project.owner = self.new_owner
        self.project.save()

        # Check the new owner has the owner permissions
        self.assertTrue(self.new_owner.has_perm(Project.Permissions.VIEW_PROJECT, self.project))
        self.assertTrue(self.new_owner.has_perm(Project.Permissions.UPDATE_PROJECT, self.project))
        self.assertTrue(self.new_owner.has_perm(Project.Permissions.DELETE_PROJECT, self.project))

    def test_permissions_on_member_removal(self):
        """Test permissions are removed when a user is no longer a member of the project."""
        # Remove the member from the project
        self.project.members.remove(self.member)

        # Check the removed member no longer has permissions
        self.assertFalse(self.member.has_perm(Project.Permissions.UPDATE_PROJECT, self.project))

    def test_superuser_has_all_permissions(self):
        # Log in as the superuser
        self.client.force_authenticate(user=self.superuser)

        # Get all permissions for the superuser on the project
        superuser_permissions = get_perms(self.superuser, self.project)

        # Assert that the superuser has all object-level permissions
        project_permissions = [
            Project.Permissions.VIEW_PROJECT,
            Project.Permissions.UPDATE_PROJECT,
            Project.Permissions.DELETE_PROJECT,
        ]
        for perm in project_permissions:
            self.assertIn(perm, superuser_permissions)

    def test_superuser_can_create_project(self):
        """Ensure a superuser can create a project."""
        self.client.force_authenticate(user=self.superuser)
        data = {"name": "Superuser Project", "description": "Created by superuser"}
        response = self.client.post(self.project_create_endpoint, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_regular_user_cannot_create_project(self):
        """Ensure a regular user cannot create a project."""
        self.client.force_authenticate(user=self.regular_user)
        data = {"name": "Regular User Project", "description": "Created by regular user"}
        response = self.client.post(self.project_create_endpoint, data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_anonymous_user_cannot_create_project(self):
        """Ensure an anonymous user cannot create a project."""
        data = {"name": "Anonymous User Project", "description": "Created by anonymous user"}
        response = self.client.post(self.project_create_endpoint, data)
        self.assertIn(response.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])


class TestRolePermissions(APITestCase):
    # Create users
    def setUp(self) -> None:
        self.super_user = User.objects.create_user(email="super_user@insectai.org", is_staff=True, is_superuser=True)
        self.project_manager = User.objects.create_user(email="project_manager@insectai.org", is_staff=False)
        self._create_project(self.project_manager)

        self.basic_member = User.objects.create_user(email="basic_member@insectai.org", is_staff=False)
        self.identifier = User.objects.create_user(email="identifier@insectai.org", is_staff=False)

        self._assign_roles()
        # Create a regular with no role assigned in the project
        self.regular_user = User.objects.create_user(email="ru@insectai.org", is_staff=False)

        self._create_job()
        self.PERMISSIONS_MAPS = {
            "project_manager": {
                "project": {"create": False, "update": True, "delete": True},
                "collection": {"create": True, "update": True, "delete": True, "populate": True},
                "storage": {"create": True, "update": True, "delete": True, "test": True},
                "sourceimage": {"create": True, "update": True, "delete": True},
                "sourceimageupload": {"create": True, "update": True, "delete": True},
                "site": {"create": True, "update": True, "delete": True},
                "device": {"create": True, "update": True, "delete": True},
                "job": {
                    "create": True,
                    "update": True,
                    "delete": True,
                    "run_single_image": True,
                    "run": False,
                    "retry": False,
                    "cancel": False,
                },
                "identification": {"create": True, "update": True, "delete": True},
                "capture": {"star": True, "unstar": True},
            },
            "basic_member": {
                "project": {"create": False, "update": False, "delete": False},
                "collection": {"create": False, "update": False, "delete": False, "populate": False},
                "storage": {"create": False, "update": False, "delete": False},
                "site": {"create": False, "update": False, "delete": False},
                "sourceimage": {"create": False, "update": False, "delete": False},
                "sourceimageupload": {"create": False, "update": False, "delete": False},
                "device": {"create": False, "update": False, "delete": False},
                "job": {
                    "create": True,
                    "update": False,
                    "delete": False,
                    "run_single_image": True,
                    "run": False,
                    "retry": False,
                    "cancel": False,
                },
                "identification": {"create": False, "delete": False},
                "capture": {"star": True, "unstar": True},
            },
            "identifier": {
                "project": {"create": False, "update": False, "delete": False},
                "collection": {"create": False, "update": False, "delete": False, "populate": False},
                "storage": {"create": False, "update": False, "delete": False},
                "sourceimage": {"create": False, "update": False, "delete": False},
                "sourceimageupload": {"create": False, "update": False, "delete": False},
                "site": {"create": False, "update": False, "delete": False},
                "device": {"create": False, "update": False, "delete": False},
                "job": {
                    "create": True,
                    "update": False,
                    "delete": False,
                    "run_single_image": True,
                    "run": False,
                    "retry": False,
                    "cancel": False,
                },
                "identification": {"create": True, "update": True, "delete": True},
                "capture": {"star": True, "unstar": True},
            },
            "regular_user": {
                "project": {"create": False, "update": False, "delete": False},
                "collection": {"create": False, "update": False, "delete": False, "populate": False},
                "storage": {"create": False, "update": False, "delete": False},
                "sourceimage": {"create": False, "update": False, "delete": False},
                "sourceimageupload": {"create": False, "update": False, "delete": False},
                "site": {"create": False, "update": False, "delete": False},
                "device": {"create": False, "update": False, "delete": False},
                "job": {
                    "create": False,
                    "update": False,
                    "delete": False,
                    "run_single_image": False,
                    "run": False,
                    "retry": False,
                    "cancel": False,
                },
                "identification": {"create": False, "delete": False},
                "capture": {"star": False, "unstar": False},
            },
        }

    def _assign_roles(self):
        ProjectManager.assign_user(self.project_manager, self.project)
        BasicMember.assign_user(self.basic_member, self.project)
        Identifier.assign_user(self.identifier, self.project)

    def _create_project(self, owner):
        self.project = Project.objects.create(name="Insect Project", description="Test Description", owner=owner)
        self.deployment = Deployment.objects.create(name="Test Deployment", project=self.project)
        S3StorageSource.objects.create(name="New source", project=self.project, bucket="Test Bucket")
        create_captures(deployment=self.deployment)
        create_taxa(project=self.project)
        create_occurrences(deployment=self.deployment, num=1)
        self._create_job()
        Identification.objects.create(
            user=self.project_manager, taxon=Taxon.objects.first(), occurrence=self.project.occurrences.first()
        )

    def _create_job(self):
        self.job = Job.objects.create(name="Test Job", project=self.project, job_type_key="ml")

    def _create_source_image_upload_file(self):
        image_buffer = BytesIO()
        image = Image.new("RGB", (100, 100), color=(255, 0, 0))  # a red square
        image.save(image_buffer, format="JPEG")
        image_buffer.seek(0)

        image_file = SimpleUploadedFile(
            name="20210101120000-snapshot.jpg", content=image_buffer.read(), content_type="image/jpeg"
        )
        return image_file

    def _create_test_source_image_upload(self, user):
        """
        Creates a SourceImageUpload instance using a valid in-memory JPEG image
        and self.project.deployments.first() as the deployment.
        """
        deployment = self.project.deployments.first()

        # Generate a valid JPEG image in memory using Pillow
        image_file = self._create_source_image_upload_file()
        upload = SourceImageUpload.objects.create(
            image=image_file,
            user=user,
            deployment=deployment,
        )
        self.source_image_upload = upload
        return upload

    def _create_test_source_image(self):
        return SourceImage.objects.create(
            project=self.project,
            deployment=self.project.deployments.first(),
            uploaded_by=self.project_manager,
            test_image=False,
        )

    def _test_role_permissions(self, role_class, user, permissions_map):
        """Generic function to test role-based permissions based on an entity permission map."""
        self._create_project(owner=self.project_manager)
        self._assign_roles()
        capture_id = self.project.occurrences.first().detections.first().source_image.pk
        occurrence_id = self.project.occurrences.first().pk
        endpoints = {
            "collection": "/api/v2/captures/collections/",
            "site": "/api/v2/deployments/sites/",
            "device": "/api/v2/deployments/devices/",
            "storage": "/api/v2/storage/",
            "job": "/api/v2/jobs/",
            "identification": "/api/v2/identifications/",
            "project": "/api/v2/projects/",
            "capture_star": f"/api/v2/captures/{capture_id}/star/",
            "capture_unstar": f"/api/v2/captures/{capture_id}/unstar/",
        }

        self.client.force_authenticate(user=user)

        entity_ids = {
            "project": self.project.pk,
            "collection": self.project.sourceimage_collections.first().pk,
            "storage": self.project.storage_sources.first().pk,
            "device": self.project.devices.first().pk,
            "site": self.project.sites.first().pk,
            "job": self.project.jobs.first().pk,
            "identification": self.project.occurrences.first().identifications.first().pk,
        }
        create_data = {
            "collection": {
                "description": "New Collection",
                "name": "Collection 1",
                "project": self.project.pk,
                "method": "common_combined",
            },
            "site": {"description": "New Site", "name": "Site 1", "project": self.project.pk},
            "device": {"description": "New Device", "name": "Device 1", "project": self.project.pk},
            "storage": {"name": "New Storage", "project": self.project.pk, "bucket": "test-bucket"},
            "job": {"delay": "1", "name": "Test Job", "project_id": self.project.pk},
            "identification": {"occurrence_id": occurrence_id, "taxon_id": "5", "comment": "Identifier comment"},
            "project": {"name": "New Project", "description": "This is a test project."},
        }

        for entity, actions in permissions_map.items():
            if entity in ["capture", "sourceimageupload", "sourceimage"]:
                continue
            # Check Collection-Level Permissions in List Response
            response = self.client.get(f"{endpoints[entity]}?project_id={self.project.pk}")
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            logger.info(f"{role_class} , {entity} list response {response.json()}")
            expected_collection_permissions = []
            if actions.get("create", False):
                # Identification update permissions are included
                # in the user_permissions field at the object level
                # in the /occurrences/{id}/ endpoint response.
                if entity != "identification":
                    expected_collection_permissions.append("create")
            logger.info(
                f"{role_class}, expected collection level permissions for {entity}: {expected_collection_permissions}"
            )
            self.assertEqual(set(response.json().get("user_permissions", [])), set(expected_collection_permissions))

            # Step 1: Test Create
            logger.info(f"Testing {role_class} create permission for {entity} ")
            can_create = actions["create"] if "create" in actions else False
            logger.info(f"entity endpoint : {endpoints[entity]}")
            if entity == "project":
                response = self.client.post(endpoints[entity], create_data.get(entity, {}), format="multipart")
            else:
                response = self.client.post(endpoints[entity], create_data.get(entity, {}))
            expected_status = status.HTTP_201_CREATED if can_create else status.HTTP_403_FORBIDDEN
            self.assertEqual(response.status_code, expected_status)
            entity_ids[entity] = response.json().get("id") if can_create else entity_ids.get(entity, None)

            #  Check Object-Level Permissions in List Response
            if entity_ids[entity]:
                response = self.client.get(endpoints[entity])
                self.assertEqual(response.status_code, status.HTTP_200_OK)

            object_permissions = []
            # Add update, delete and other custom permissions
            # populate, retry_job, cancel_job, start_job
            for action, allowed in actions.items():
                if allowed and action != "create":
                    object_permissions.append(action)

            results = response.json().get("results", [])
            if results:
                object_id = entity_ids[entity]
                obj = next((r for r in results if r["id"] == object_id), None)
                if obj:
                    self.assertEqual(
                        set(obj.get("user_permissions", [])),
                        set(object_permissions),
                        f"Object permissions mismatch for {entity}",
                    )

            # Step 2: Test Update
            logger.info(f"Testing {role_class} update permission for {entity} , actions {actions}")
            can_update = actions["update"] if "update" in actions else False
            logger.info(f"{entity} can_update: {can_update}")
            if entity_ids[entity]:
                logger.info(f"{entity} update request {create_data.get(entity, {})}")
                response = self.client.patch(
                    f"{endpoints[entity]}{entity_ids[entity]}/",
                    create_data.get(entity, {}).update({"name": "Updated Name"}),
                )
                logger.info(f"{entity} update response {response.json()}")
                expected_status = status.HTTP_200_OK if can_update else status.HTTP_403_FORBIDDEN
                logger.info(f"{entity} expected_status: {expected_status}, response_status:{response.status_code}")
                self.assertEqual(response.status_code, expected_status)

            # Step 3: Test Custom Actions
            if entity == "job" and entity_ids[entity]:
                for action in ["run", "retry", "cancel"]:
                    logger.info(f"Testing {role_class} for job {action} custom permission")
                    if action in actions:
                        response = self.client.post(f"{endpoints[entity]}{entity_ids[entity]}/{action}/")
                        expected_status = status.HTTP_200_OK if actions[action] else status.HTTP_403_FORBIDDEN
                        self.assertEqual(
                            response.status_code,
                            expected_status,
                            f"{role_class} {action} permission failed for {entity}",
                        )

            if entity == "collection" and entity_ids[entity] and "populate" in actions:
                logger.info(f"Testing {role_class} for  collection populate custom permission")
                response = self.client.post(f"{endpoints[entity]}{entity_ids[entity]}/populate/")
                expected_status = status.HTTP_200_OK if actions["populate"] else status.HTTP_403_FORBIDDEN
                self.assertEqual(response.status_code, expected_status)
        # Step 4: Test Capture (Star/Unstar)
        if "capture" in permissions_map:
            logger.info(f"Testing {role_class} for  capture star permission ")
            can_star = permissions_map["capture"].get("star", False)
            response = self.client.post(endpoints["capture_star"])
            expected_status = status.HTTP_200_OK if can_star else status.HTTP_403_FORBIDDEN
            self.assertEqual(response.status_code, expected_status, f"{role_class} star permission failed")
            logger.info(f"Testing {role_class} for  capture unstar permission ")
            can_unstar = permissions_map["capture"].get("unstar", False)
            response = self.client.post(endpoints["capture_unstar"])
            expected_status = status.HTTP_200_OK if can_unstar else status.HTTP_403_FORBIDDEN
            self.assertEqual(response.status_code, expected_status, f"{role_class} unstar permission failed")
        logger.info(f"{role_class}: entity_ids: {entity_ids}")
        # Step 5: Unassign Role and Verify Permissions are Revoked
        if role_class:
            role_class.unassign_user(user, self.project)
            BasicMember.unassign_user(user, project=self.project)
            self.client.force_authenticate(user=user)

            for entity, actions in permissions_map.items():
                if entity in ["sourceimage", "sourceimageupload"]:
                    continue
                if "create" in actions:
                    logger.info(f"Testing {role_class} for create permission on {entity} after role unassignment")
                    response = self.client.post(endpoints[entity], create_data.get(entity, {}))
                    self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
                if "update" in actions:
                    logger.info(f"Testing {role_class} for update permission on {entity} after role unassignment")
                    logger.info(
                        f"""Testing {role_class}
                        after role unassignment endpoint:
                         {endpoints[entity]}{entity_ids[entity]}/"""
                    )
                    response = self.client.patch(
                        f"{endpoints[entity]}{entity_ids[entity]}/",
                        create_data.get(entity, {}).update({"name": "Updated Name"}),
                    )
                    self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

            response = self.client.post(endpoints["capture_star"])
            logger.info(f"star capture response: {response.json()}")
            logger.info(f"Testing {role_class} for star capture permission after role unassignment")
            logger.info(f"{role_class} {user} user permissions: {get_perms(user, self.project)}")
            self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

            response = self.client.post(endpoints["capture_unstar"])
            logger.info(f"Testing {role_class} for unstar capture permission after role unassignment")
            self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # Step 6: Reassign Role and Verify Ability to Delete Objects
        if role_class:
            role_class.assign_user(user, self.project)
            self.client.force_authenticate(user=user)

            for entity, actions in permissions_map.items():
                if entity in ["project", "sourceimage", "sourceimageupload"]:
                    # skip deleting project for now and sourceimage,sourceimageupload
                    continue

                if "delete" in actions and actions["delete"] and entity_ids[entity]:
                    logger.info(f"Testing {role_class} for delete permission on {entity}")
                    can_delete = actions["delete"]
                    response = self.client.delete(f"{endpoints[entity]}{entity_ids[entity]}/")
                    logger.info(f"{role_class} delete response status for {entity} : {response.status_code}")
                    expected_status = status.HTTP_204_NO_CONTENT if can_delete else status.HTTP_403_FORBIDDEN
                    self.assertEqual(response.status_code, expected_status, f"Delete permission failed for {entity}")

            # try to delete the project
            entity = "project"
            actions = permissions_map[entity]
            if "delete" in actions and actions["delete"] and entity_ids[entity]:
                logger.info(f"Testing {role_class} for delete permission on {entity}")
                can_delete = actions["delete"]
                response = self.client.delete(f"{endpoints[entity]}{entity_ids[entity]}/")
                logger.info(f"{role_class} delete response status for {entity} : {response.status_code}")
                expected_status = status.HTTP_204_NO_CONTENT if can_delete else status.HTTP_403_FORBIDDEN
                self.assertEqual(response.status_code, expected_status)

    def _test_sourceimageupload_permissions(self, user, permission_map):
        self._create_project(owner=self.project_manager)
        self.client.force_authenticate(user=self.super_user)
        list_url = "/api/v2/captures/upload/"

        self.client.force_authenticate(user=user)

        # --- Test Create ---
        response = self.client.post(
            list_url,
            {
                "image": self._create_source_image_upload_file(),
                "deployment": self.deployment.pk,
                "project_id": self.project.pk,
            },
            format="multipart",
        )

        if permission_map.get("create", False):
            self.assertEqual(response.status_code, 201, f"{user.email} should be able to create sourceimageupload")
            object_id = response.data["id"]

        else:
            source_image_upload = self._create_test_source_image_upload(user=user)
            object_id = source_image_upload.pk

        detail_url = f"{list_url}{object_id}/"
        # --- Confirm existence ---
        response = self.client.get(detail_url)
        self.assertEqual(
            response.status_code, 200, f"{user.email} should be able to view the sourceimageupload object"
        )
        logger.info(f"[{user.email}] GET {detail_url} returned 200 OK")
        # --- Test Update ---
        expected_update = 200 if permission_map.get("update", False) else 403
        response = self.client.patch(detail_url, {"details": "updated"}, format="json")
        self.assertEqual(response.status_code, expected_update, f"{user.email} update sourceimageupload")

        # --- Test Delete ---
        expected_delete = 204 if permission_map.get("delete", False) else 403
        response = self.client.delete(detail_url)
        self.assertEqual(response.status_code, expected_delete, f"{user.email} delete sourceimageupload")

    def _test_sourceimage_permissions(self, user, permission_map):
        self.client.force_authenticate(user=user)
        self._create_project(owner=self.project_manager)
        list_url = "/api/v2/captures/"
        # --- Test Create ---
        response = self.client.post(
            list_url,
            {"project": self.project.pk, "deployment": self.deployment.pk, "test_image": False},
            format="json",
        )

        if permission_map.get("create", False):
            self.assertEqual(response.status_code, 201, f"{user.email} should be able to create sourceimage")
            object_id = response.data["id"]
        else:
            self.assertEqual(response.status_code, 403, f"{user.email} should NOT be able to create sourceimage")
            image = self._create_test_source_image()
            object_id = image.id

        detail_url = f"{list_url}{object_id}/"

        # --- Test Update ---
        expected_update = 200 if permission_map.get("update", False) else 403
        response = self.client.patch(detail_url, {"test_image": True}, format="json")
        self.assertEqual(response.status_code, expected_update, f"{user.email} update sourceimage")

        # --- Test Delete ---
        expected_delete = 204 if permission_map.get("delete", False) else 403
        response = self.client.delete(detail_url)
        self.assertEqual(response.status_code, expected_delete, f"{user.email} delete sourceimage")

    def test_identifier_permissions(self):
        """Test Identifier role permissions."""

        expected_permissions = Identifier.permissions
        assigned_permissions = set(get_perms(self.identifier, self.project))
        self.assertEqual(assigned_permissions, expected_permissions)
        self._test_role_permissions(Identifier, self.identifier, self.PERMISSIONS_MAPS["identifier"])
        self._test_sourceimage_permissions(
            user=self.identifier, permission_map=self.PERMISSIONS_MAPS["identifier"]["sourceimage"]
        )
        self._test_sourceimageupload_permissions(
            user=self.identifier, permission_map=self.PERMISSIONS_MAPS["identifier"]["sourceimageupload"]
        )

    def test_basic_member_permissions_(self):
        """Test Basic Member role permissions."""
        expected_permissions = BasicMember.permissions
        assigned_permissions = set(get_perms(self.basic_member, self.project))
        self.assertEqual(assigned_permissions, expected_permissions)

        self._test_role_permissions(BasicMember, self.basic_member, self.PERMISSIONS_MAPS["basic_member"])
        self._test_sourceimage_permissions(
            user=self.basic_member, permission_map=self.PERMISSIONS_MAPS["basic_member"]["sourceimage"]
        )
        self._test_sourceimageupload_permissions(
            user=self.basic_member, permission_map=self.PERMISSIONS_MAPS["basic_member"]["sourceimageupload"]
        )

    def test_regular_user_permissions(self):
        """Test Regular User permissions (view-only)."""
        self._test_role_permissions(None, self.regular_user, self.PERMISSIONS_MAPS["regular_user"])
        self._test_sourceimage_permissions(
            user=self.regular_user, permission_map=self.PERMISSIONS_MAPS["regular_user"]["sourceimage"]
        )
        self._test_sourceimageupload_permissions(
            user=self.regular_user, permission_map=self.PERMISSIONS_MAPS["regular_user"]["sourceimageupload"]
        )

    def test_project_manager_permissions_(self):
        """Test Project Manager role permissions."""
        expected_permissions = ProjectManager.permissions
        assigned_permissions = set(get_perms(self.project_manager, self.project))
        self.assertEqual(assigned_permissions, expected_permissions)
        self._test_role_permissions(ProjectManager, self.project_manager, self.PERMISSIONS_MAPS["project_manager"])
        self._test_sourceimage_permissions(
            user=self.project_manager, permission_map=self.PERMISSIONS_MAPS["project_manager"]["sourceimage"]
        )
        self._test_sourceimageupload_permissions(
            user=self.project_manager, permission_map=self.PERMISSIONS_MAPS["project_manager"]["sourceimageupload"]
        )


class TestDeploymentSyncCreatesEvents(TestCase):
    def test_sync_creates_events_and_updates_counts(self):
        # Set up a new project and deployment with test data
        project, deployment = setup_test_project(reuse=False)

        # Populate the object store with image data
        assert deployment.data_source is not None
        populate_bucket(
            config=deployment.data_source.config,
            subdir=f"deployment_{deployment.pk}",
            skip_existing=False,
        )

        # Sync captures
        deployment.sync_captures()

        # Refresh and check results
        deployment.refresh_from_db()
        initial_events = Event.objects.filter(deployment=deployment)
        initial_events_count = initial_events.count()

        # Assertions
        self.assertTrue(initial_events.exists(), "Expected events to be created")
        self.assertEqual(
            deployment.events_count, initial_events.count(), "Deployment events_count should match actual events"
        )
        # Simulate new images added to object store
        populate_bucket(
            config=deployment.data_source.config,
            subdir=f"deployment_{deployment.pk}",
            skip_existing=False,
            num_nights=2,
            images_per_day=5,
            minutes_interval=120,
        )

        # Sync again
        deployment.sync_captures()
        deployment.refresh_from_db()
        updated_events = Event.objects.filter(deployment=deployment)

        # Assertions for second sync
        self.assertGreater(
            updated_events.count(), initial_events_count, "New events should be created after adding new images"
        )
        self.assertEqual(
            deployment.events_count,
            updated_events.count(),
            "Deployment events_count should reflect updated event count",
        )
        logger.info(f"Initial events count: {initial_events_count}, Updated events count: {updated_events.count()}")


class TestFineGrainedJobRunPermission(APITestCase):
    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user(
            email="regularuser@insectai.org",
            password="password123",
        )
        self.client.force_authenticate(self.user)

        self.project = Project.objects.create(
            name="Job Permission Project", description="For testing job run permission"
        )
        assign_perm(Project.Permissions.CREATE_JOB, self.user, self.project)
        self.valid_job_keys = [cls.key for cls in VALID_JOB_TYPES if cls.key != "unknown"]

    def _create_job(self, job_type_key):
        job = Job.objects.create(name="Test Job", project=self.project, job_type_key=job_type_key)
        return job

    def assign_run_permission(self, key):
        perm = f"main.run_{key}_job"
        assign_perm(perm, self.user, self.project)

    def remove_run_permission(self, key):
        perm = f"main.run_{key}_job"
        remove_perm(perm, self.user, self.project)

    def test_can_only_run_permitted_job_type(self):
        allowed_key = self.valid_job_keys[0]
        self.assign_run_permission(allowed_key)

        for job_type_key in self.valid_job_keys:
            job = self._create_job(job_type_key)
            response = self.client.post(f"/api/v2/jobs/{job.pk}/run/", format="json")
            if job_type_key == allowed_key:
                self.assertEqual(response.status_code, status.HTTP_200_OK, f"{job_type_key} should run successfully")
            else:
                self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN, f"{job_type_key} should be denied")

    def test_can_run_multiple_if_permitted(self):
        allowed_keys = self.valid_job_keys[:2]
        for key in allowed_keys:
            self.assign_run_permission(key)

        for job_type_key in self.valid_job_keys:
            job = self._create_job(job_type_key)
            response = self.client.post(f"/api/v2/jobs/{job.pk}/run/", format="json")

            if job_type_key in allowed_keys:
                self.assertEqual(response.status_code, status.HTTP_200_OK, f"{job_type_key} should run successfully")
            else:
                self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN, f"{job_type_key} should be denied")

    def test_cannot_run_any_without_permission(self):
        for job_type_key in self.valid_job_keys:
            job = self._create_job(job_type_key)
            response = self.client.post(f"/api/v2/jobs/{job.pk}/run/", format="json")
            self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN, f"{job_type_key} should be denied")

    def test_user_permissions_reflected_in_job_detail(self):
        job = self._create_job(job_type_key="ml")

        # By default, the user shouldn't have any job-related perms
        response = self.client.get(f"/api/v2/jobs/{job.pk}/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data.get("user_permissions"), [], "User should not have any job perms initially")

        # Assign run permission and check if it's reflected
        assign_perm(Project.Permissions.RUN_ML_JOB, self.user, self.project)
        response = self.client.get(f"/api/v2/jobs/{job.pk}/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("run", response.data.get("user_permissions", []))

        # Remove run permission and confirm it's removed
        remove_perm(Project.Permissions.RUN_ML_JOB, self.user, self.project)
        response = self.client.get(f"/api/v2/jobs/{job.pk}/")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("run", response.data.get("user_permissions", []))


class TestRunSingleImageJobPermission(APITestCase):
    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user(
            email="regularuser@insectai.org",
            password="password123",
        )
        self.project = Project.objects.create(name="Single Image Project", description="Testing single image job")
        self.pipeline = Pipeline.objects.create(
            name="Test ML pipeline",
            description="Test ML pipeline",
        )
        self.pipeline.projects.add(self.project)
        self.deployment = Deployment.objects.create(name="Test Deployment", project=self.project)
        create_captures(deployment=self.deployment)
        group_images_into_events(deployment=self.deployment)
        self.capture = self.deployment.captures.first()
        self.client.force_authenticate(self.user)

    def _grant_create_job__and_run_single_image_perm(self):
        """Grants run_single_image_job permission on a specific capture to the user."""
        assign_perm(Project.Permissions.CREATE_JOB, self.user, self.project)
        assign_perm(Project.Permissions.RUN_SINGLE_IMAGE_JOB, self.user, self.project)

    def _remove_run_single_image_perm(self):
        remove_perm(Project.Permissions.RUN_SINGLE_IMAGE_JOB, self.user, self.project)

    def test_user_can_run_single_image_job_and_perm_is_reflected(self):
        self._grant_create_job__and_run_single_image_perm()

        # Verify permission is reflected in capture detail response
        assert self.capture is not None
        capture_detail_url = f"/api/v2/captures/{self.capture.pk}/?project_id={self.project.pk}"
        response = self.client.get(capture_detail_url)
        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "run_single_image_ml_job",
            response.data.get("user_permissions", []),
            "run_single_image permission not reflected",
        )

        # Try to run a job using source_image_single_id
        run_url = "/api/v2/jobs/?start_now"
        payload = {
            "delay": 0,
            "name": f"Capture #{self.capture.pk}",
            "project_id": str(self.project.pk),
            "pipeline_id": str(self.pipeline.pk),
            "source_image_single_id": str(self.capture.pk),
        }
        response = self.client.post(run_url, payload, format="json")
        self.assertEqual(
            response.status_code, 201, f"User should be able to run single image job, got {response.status_code}"
        )
        # Remove permission
        self._remove_run_single_image_perm()

        # Permission should no longer appear in capture detail
        response = self.client.get(capture_detail_url)
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(
            "run_single_image_ml_job",
            response.data.get("user_permissions", []),
            "run_single_image permission should be removed but still present",
        )

        # Should not be able to run job now
        response = self.client.post(run_url, payload, format="json")
        self.assertEqual(
            response.status_code,
            403,
            f"User should NOT be able to run single image job after permission removal, got {response.status_code}",
        )


class TestDraftProjectPermissions(APITestCase):
    def setUp(self) -> None:
        # Users
        self.owner = User.objects.create_user(email="owner@insectai.org", is_staff=True)
        self.member = User.objects.create_user(email="member@insectai.org", is_staff=False)
        self.outsider = User.objects.create_user(email="outsider@insectai.org", is_staff=False)
        self.superuser = User.objects.create_superuser(
            email="superuser@insectai.org",
            password="password123",
            is_staff=True,
        )
        # Pre-create related test data
        # Draft project with owner
        self.project = Project.objects.create(
            name="Draft Only Project",
            description="Draft visibility test",
            owner=self.owner,
            draft=True,
        )
        self.deployment = Deployment.objects.create(name="Test Deployment", project=self.project)
        Job.objects.create(name="Test Job", project=self.project, job_type_key="ml")
        create_captures(deployment=self.deployment)
        group_images_into_events(deployment=self.deployment)
        create_taxa(project=self.project)
        create_occurrences(deployment=self.deployment, num=1)
        self.project.members.add(self.member)
        self.detail_url = f"/api/v2/projects/{self.project.pk}/"

        Tag.objects.create(name="Test Tag", project=self.project)
        DataExport.objects.create(
            user=self.owner,
            project=self.project,
            format="json",
            filters={},
            filters_display={},
            file_url="https://example.com/export.json",
            record_count=123,
            file_size=456789,
        )
        fake_image = SimpleUploadedFile("test.jpg", b"fake image content", content_type="image/jpeg")
        SourceImageUpload.objects.create(image=fake_image, deployment=self.deployment)
        occurrence = Occurrence.objects.filter(deployment=self.deployment).first()
        Identification.objects.create(occurrence=occurrence)
        S3StorageSource.objects.create(
            name="Test S3 Source",
            bucket="test-bucket",
            access_key="fake-access-key",
            secret_key="fake-secret-key",
            project=self.project,
        )
        taxon = Taxon.objects.create(name="Draft Taxon")
        taxon.projects.add(self.project)
        self.non_draft_project = Project.objects.filter(draft=False).first()

    def _auth_get(self, user, url):
        self.client.force_authenticate(user)
        return self.client.get(url)

    # Project detail tests
    def test_owner_can_view_draft_project(self):
        resp = self._auth_get(self.owner, self.detail_url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK, "Owner should be able to view draft project")

    def test_member_can_view_draft_project(self):
        resp = self._auth_get(self.member, self.detail_url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK, "Member should be able to view draft project")

    def test_member_removed_cannot_view_draft_project(self):
        self.project.members.remove(self.member)
        resp = self._auth_get(self.member, self.detail_url)
        self.assertIn(
            resp.status_code,
            (status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND),
            " Member should not view draft project after removal",
        )

    def test_outsider_cannot_view_draft_project(self):
        resp = self._auth_get(self.outsider, self.detail_url)
        self.assertIn(
            resp.status_code,
            (status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND),
            " Non-member should not view draft project",
        )

    def test_superuser_can_view_draft_project(self):
        resp = self._auth_get(self.superuser, self.detail_url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK, "Superuser should be able to view draft project")

    def test_draft_project_detail_access(self):
        url = f"/api/v2/projects/{self.project.pk}/"

        assert self._auth_get(self.superuser, url).status_code == 200
        assert self._auth_get(self.owner, url).status_code == 200
        assert self._auth_get(self.member, url).status_code == 200

        response = self._auth_get(self.outsider, url)
        assert response.status_code in [403, 404]

    def test_draft_project_list_visibility(self):
        url = "/api/v2/projects/"

        for user in [self.superuser, self.owner, self.member]:
            self.client.force_authenticate(user)
            response = self.client.get(url)
            ids = [p["id"] for p in response.data["results"]]
            assert self.project.pk in ids

        self.client.force_authenticate(self.outsider)
        response = self.client.get(url)
        ids = [p["id"] for p in response.data["results"]]
        assert self.project.pk not in ids

    # Deployment detail & list tests
    def test_deployment_detail_draft_project(self):
        url = f"/api/v2/deployments/{self.deployment.pk}/"

        assert self._auth_get(self.superuser, url).status_code == 200
        assert self._auth_get(self.owner, url).status_code == 200
        assert self._auth_get(self.member, url).status_code == 200

        response = self._auth_get(self.outsider, url)
        assert response.status_code in [403, 404]

    def test_deployment_list_draft_project(self):
        url = f"/api/v2/deployments/?project_id={self.project.pk}"

        for user in [self.superuser, self.owner, self.member]:
            self.client.force_authenticate(user)
            response = self.client.get(url)
            ids = [d["id"] for d in response.data["results"]]
            assert self.deployment.pk in ids

        self.client.force_authenticate(self.outsider)
        response = self.client.get(url)
        ids = [d["id"] for d in response.data["results"]]
        assert self.deployment.pk not in ids

    def test_visible_for_user_across_all_models(self):
        all_users = {
            "superuser": self.superuser,
            "owner": self.owner,
            "member": self.member,
            "outsider": self.outsider,
            "anonymous": AnonymousUser(),
        }

        project_related_models = [
            Project,
            Device,
            Site,
            Deployment,
            Event,
            S3StorageSource,
            SourceImage,
            Occurrence,
            Tag,
            SourceImageCollection,
            Job,
            DataExport,
            Taxon,
            TaxaList,
            ProcessingService,
            Pipeline,
            SourceImageUpload,
            Identification,
            Classification,
            Detection,
            ProjectPipelineConfig,
        ]

        for model in project_related_models:
            project_accessor = model.get_project_accessor()
            if project_accessor is None:
                continue  # skip models not related to a project

            # Filter only objects from the test draft project
            try:
                if model == Project:
                    draft_queryset = model.objects.filter(draft=True)
                    non_draft_queryset = model.objects.filter(draft=False)
                else:
                    draft_queryset = model.objects.filter(**{f"{project_accessor}": self.project})
                    non_draft_queryset = model.objects.filter(**{f"{project_accessor}": self.non_draft_project})
            except Exception as e:
                raise AssertionError(
                    f"Failed to filter querysets for {model.__name__} using accessor '{project_accessor}': {e}"
                )

            self.assertTrue(
                draft_queryset.exists(),
                f"No instances found for model {model.__name__} tied to the draft project",
            )

            for role, user in all_users.items():
                visible_ids = list(draft_queryset.visible_for_user(user).values_list("id", flat=True))
                non_draft_ids = set(non_draft_queryset.values_list("id", flat=True))
                is_draft_viewer = role in {"superuser", "owner", "member"}

                for instance in draft_queryset:
                    msg = f"{model.__name__} visible_for_user failed for role={role}"

                    is_in_non_draft = instance.id in non_draft_ids
                    should_be_visible = is_draft_viewer or is_in_non_draft

                    if should_be_visible:
                        self.assertIn(instance.id, visible_ids, msg)
                    else:
                        self.assertNotIn(instance.id, visible_ids, msg)

    def test_summary_counts(self):
        """
        Test the expected counts returned by the /status/summary/ endpoint.

        - Compare when a project is in draft mode vs non-draft mode.
        - Verify counts from the perspective of a project member vs an outsider.
        - Confirm that when the project is made non-draft, outsiders see the same counts as members.
        """
        project_url: str = f"/api/v2/status/summary/?project_id={self.project.pk}"
        global_url: str = "/api/v2/status/summary/"

        logger.info(f"Testing exact summary statistics for project {self.project.pk}")

        # Ensure project is in draft mode
        self.project.draft = True
        self.project.save()

        # Test 1: Get the exact counts for the draft project from member perspective
        member_project_response = self._auth_get(self.member, project_url)
        self.assertEqual(member_project_response.status_code, 200)
        draft_project_counts: dict[str, typing.Any] = member_project_response.json()

        # Test 2: Verify outsider sees zeros for draft project (except projects_count)
        outsider_project_response = self._auth_get(self.outsider, project_url)
        self.assertEqual(outsider_project_response.status_code, 200)
        outsider_project_data: dict[str, typing.Any] = outsider_project_response.json()

        non_draft_project_count: int = Project.objects.filter(draft=False).count()

        project_count_keys = ("projects_count", "num_projects")  # One of these is a deprecated alias

        for key, value in outsider_project_data.items():
            if key in project_count_keys:
                self.assertEqual(
                    value,
                    non_draft_project_count,
                    f"Outsider should see exactly {non_draft_project_count} non-draft projects for {key}, got {value}",
                )
            else:
                self.assertEqual(value, 0, f"Outsider should see exactly 0 for {key} in draft project, got {value}")

        # Test 3: Get global counts for both users
        outsider_global_response = self._auth_get(self.outsider, global_url)
        member_global_response = self._auth_get(self.member, global_url)

        self.assertEqual(outsider_global_response.status_code, 200)
        self.assertEqual(member_global_response.status_code, 200)

        outsider_global_data: dict[str, typing.Any] = outsider_global_response.json()
        member_global_data: dict[str, typing.Any] = member_global_response.json()

        # Test 4: Verify exact differences in global counts
        for key in draft_project_counts.keys():
            if key in project_count_keys:
                # Skip project counts as they are not affected by draft status
                continue

            if key in ("num_taxa", "num_species", "taxa_count"):  # Two are deprecated aliases! @TOOD
                # Taxa can be in multiple projects, so skip exact count check
                logger.debug(f"Skipping exact count check for {key} due to potential multi-project association")
                continue

            outsider_global_count: int = outsider_global_data.get(key, 0)
            member_global_count: int = member_global_data.get(key, 0)
            draft_project_count: int = draft_project_counts[key]

            # The difference should be exactly the draft project counts
            # (assuming member has no other draft project access)
            expected_member_count: int = outsider_global_count + draft_project_count

            self.assertEqual(
                member_global_count,
                expected_member_count,
                f"Member global count for {key} should be exactly {expected_member_count} "
                f"(outsider: {outsider_global_count} + draft project: {draft_project_count}), "
                f"got {member_global_count}",
            )

            logger.info(
                f"{key} exact counts - Draft project: {draft_project_count}, "
                f"Outsider global: {outsider_global_count}, "
                f"Member global: {member_global_count}, "
                f"Difference: {member_global_count - outsider_global_count}"
            )

        # Test 5: Verify behavior when project becomes non-draft
        self.project.draft = False
        self.project.save()

        # Now outsider should see the same counts as member saw before
        non_draft_outsider_response = self._auth_get(self.outsider, project_url)
        self.assertEqual(non_draft_outsider_response.status_code, 200)
        non_draft_outsider_data: dict[str, typing.Any] = non_draft_outsider_response.json()

        for key, expected_value in draft_project_counts.items():
            actual_value: int = non_draft_outsider_data.get(key, 0)
            self.assertEqual(
                actual_value,
                expected_value,
                f"Outsider should see exactly {expected_value} for {key} in non-draft project, got {actual_value}",
            )

        logger.info("All exact count validations passed")


class TestProjectDefaultThresholdFilter(APITestCase):
    """API tests for default score threshold filtering"""

    def setUp(self):
        # Create project, deployment, and test data
        self.project, self.deployment = setup_test_project(reuse=False)
        taxa_list = create_taxa(self.project)
        taxa = list(taxa_list.taxa.all())
        low_taxon = taxa[0]
        high_taxon = taxa[1]
        create_captures(deployment=self.deployment, num_nights=1, images_per_night=3)

        # Create multiple low and high determination score occurrences
        create_occurrences(deployment=self.deployment, num=3, determination_score=0.3, taxon=low_taxon)
        create_occurrences(deployment=self.deployment, num=3, determination_score=0.9, taxon=high_taxon)

        self.low_occurrences = Occurrence.objects.filter(deployment=self.deployment, determination_score=0.3)
        self.high_occurrences = Occurrence.objects.filter(deployment=self.deployment, determination_score=0.9)

        # Project default threshold
        self.default_threshold = 0.6
        self.project.default_filters_score_threshold = self.default_threshold
        self.project.save()

        # Auth user
        self.user = User.objects.create_user(email="tester@insectai.org", is_staff=False, is_superuser=False)
        self.client.force_authenticate(user=self.user)

        self.url = f"/api/v2/occurrences/?project_id={self.project.pk}&page_size=1000"
        self.url_taxa = f"/api/v2/taxa/?project_id={self.project.pk}&page_size=1000"

    # OccurrenceViewSet tests
    def test_occurrences_respect_project_threshold(self):
        """Occurrences below project threshold should be filtered out"""
        res = self.client.get(self.url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        ids = {o["id"] for o in res.data["results"]}

        # High-scoring occurrences should remain
        for occ in self.high_occurrences:
            self.assertIn(occ.id, ids)
        # Low-scoring occurrences should be excluded
        for occ in self.low_occurrences:
            self.assertNotIn(occ.id, ids)

    def test_apply_defaults_false_bypasses_threshold(self):
        """apply_defaults=false should allow explicit classification_threshold to override project default"""
        res = self.client.get(self.url + "&apply_defaults=false&classification_threshold=0.2")
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        # Check that our test occurrences are present
        expected_ids = {occ.id for occ in list(self.high_occurrences) + list(self.low_occurrences)}
        returned_ids = {o["id"] for o in res.data["results"]}

        self.assertTrue(expected_ids.issubset(returned_ids), f"Missing occurrence IDs: {expected_ids - returned_ids}")

    def test_query_threshold_ignored_when_defaults_applied(self):
        """classification_threshold param is ignored if apply_defaults is not false"""
        res = self.client.get(self.url + "&classification_threshold=0.1")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        ids = {o["id"] for o in res.data["results"]}
        # Still should apply project default (0.5)
        for occ in self.high_occurrences:
            self.assertIn(occ.id, ids)
        for occ in self.low_occurrences:
            self.assertNotIn(occ.id, ids)

    def test_no_project_id_returns_all(self):
        """Without project_id, threshold falls back to 0.0 and returns all occurrences"""
        url = "/api/v2/occurrences/?page_size=1000"
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        # Check that our test occurrences are present (don't assume all in DB are ours)
        expected_ids = {occ.pk for occ in list(self.high_occurrences) + list(self.low_occurrences)}
        returned_ids = {o["id"] for o in res.data["results"]}

        self.assertTrue(expected_ids.issubset(returned_ids), f"Missing occurrence IDs: {expected_ids - returned_ids}")

    def test_retrieve_occurrence_respects_threshold(self):
        """Detail retrieval should 404 if occurrence is filtered out by threshold"""
        low_occ = self.low_occurrences[0]
        detail_url = f"/api/v2/occurrences/{low_occ.id}/?project_id={self.project.pk}"
        res = self.client.get(detail_url)
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

        high_occ = self.high_occurrences[0]
        detail_url = f"/api/v2/occurrences/{high_occ.id}/?project_id={self.project.pk}"
        res = self.client.get(detail_url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)

    # TaxonViewSet tests
    def test_taxa_respect_project_threshold(self):
        """Taxa with only low-score occurrences should be excluded"""
        res = self.client.get(self.url_taxa)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        names = {t["name"] for t in res.data["results"]}

        for occ in self.high_occurrences:
            self.assertIn(occ.determination.name, names)
        for occ in self.low_occurrences:
            self.assertNotIn(occ.determination.name, names)

    def test_apply_defaults_false_bypasses_threshold_taxa(self):
        """apply_defaults=false should allow low-score taxa to appear"""
        res = self.client.get(self.url_taxa + "&apply_defaults=false&classification_threshold=0.2")
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        # Check that our test taxa are present
        expected_names = {occ.determination.name for occ in list(self.high_occurrences) + list(self.low_occurrences)}
        returned_names = {t["name"] for t in res.data["results"]}

        self.assertTrue(
            expected_names.issubset(returned_names), f"Missing taxa names: {expected_names - returned_names}"
        )

    def test_query_threshold_ignored_when_defaults_applied_taxa(self):
        """classification_threshold is ignored when defaults apply"""
        res = self.client.get(self.url_taxa + "&classification_threshold=0.1")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        names = {t["name"] for t in res.data["results"]}

        for occ in self.high_occurrences:
            self.assertIn(occ.determination.name, names)
        for occ in self.low_occurrences:
            self.assertNotIn(occ.determination.name, names)

    def test_include_unobserved_true_returns_unobserved_taxa(self):
        """include_unobserved=true should return taxa even without valid occurrences"""
        res = self.client.get(self.url_taxa + "&include_unobserved=true")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        # There should be more taxa than just the ones tied to high occurrences
        self.assertGreater(len(res.data["results"]), self.high_occurrences.count())

    def test_taxon_detail_example_occurrences_respects_threshold(self):
        """Detail view should prefetch only above-threshold occurrences"""
        taxon = self.high_occurrences.first().determination
        detail_url = f"/api/v2/taxa/{taxon.id}/?project_id={self.project.pk}"
        res = self.client.get(detail_url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        example_occ = res.data.get("example_occurrences", [])
        self.assertTrue(all(o["determination_score"] >= 0.6 for o in example_occ))

    def test_taxa_count_matches_summary_with_threshold(self):
        """Taxa count from taxa endpoint should match taxa_count in summary when defaults applied"""
        # Get taxa list
        res_taxa = self.client.get(self.url_taxa)
        self.assertEqual(res_taxa.status_code, status.HTTP_200_OK)
        taxa_count = len(res_taxa.data["results"])

        # Get summary (global status summary, filtered by project_id)
        url_summary = f"/api/v2/status/summary/?project_id={self.project.pk}"
        res_summary = self.client.get(url_summary)
        self.assertEqual(res_summary.status_code, status.HTTP_200_OK)

        summary_taxa_count = res_summary.data["taxa_count"]

        self.assertEqual(
            taxa_count,
            summary_taxa_count,
            f"Mismatch: taxa endpoint returned {taxa_count}, summary returned {summary_taxa_count}",
        )

    # SourceImageViewSet tests
    def test_source_image_counts_respect_threshold(self):
        """occurrences_count and taxa_count should exclude low-score occurrences (per-capture assertions)."""
        url = f"/api/v2/captures/?project_id={self.project.pk}&with_counts=true"
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        for capture in res.data["results"]:
            cap_id = capture["id"]

            # All occurrences linked to this capture via detections
            cap_occs = Occurrence.objects.filter(
                detections__source_image_id=cap_id,
                deployment=self.deployment,
            ).distinct()

            cap_high_occs = cap_occs.filter(determination_score__gte=self.default_threshold)

            # Expected counts for this capture under default threshold
            expected_occurrences_count = cap_high_occs.count()
            expected_taxa_count = cap_high_occs.values("determination_id").distinct().count()

            # Exact assertions against the API’s annotated fields
            self.assertEqual(capture["occurrences_count"], expected_occurrences_count)
            self.assertEqual(capture["taxa_count"], expected_taxa_count)

            # If capture only has low-score occurrences, both counts must be zero
            if cap_occs.exists() and not cap_high_occs.exists():
                self.assertEqual(capture["occurrences_count"], 0)
                self.assertEqual(capture["taxa_count"], 0)

    def _make_collection_with_some_images(self, name="Test Manual Source Image Collection"):
        """Create a manual collection including a few of this deployment's captures using populate_sample()."""
        images = list(SourceImage.objects.filter(deployment=self.deployment).order_by("id"))
        self.assertGreaterEqual(len(images), 3, "Need at least 3 source images from setup")

        collection = SourceImageCollection.objects.create(
            name=name,
            project=self.project,
            method="manual",
            kwargs={"image_ids": [img.pk for img in images[:3]]},  # deterministic subset
        )
        collection.save()
        collection.populate_sample()
        return collection

    def _expected_counts_for_collection(self, collection, threshold: float) -> tuple[int, int]:
        """Return (occurrences_count, taxa_count) for a collection under a given threshold."""
        coll_occs = Occurrence.objects.filter(
            detections__source_image__collections=collection,
            deployment=self.deployment,
        ).distinct()
        coll_high = coll_occs.filter(determination_score__gte=threshold)
        occ_count = coll_high.count()
        taxa_count = coll_high.values("determination_id").distinct().count()
        return occ_count, taxa_count

    # SourceImageCollectionViewSet tests
    def test_collections_counts_respect_threshold(self):
        """occurrences_count and taxa_count on collections should exclude low-score occurrences."""
        collection = self._make_collection_with_some_images()

        url = f"/api/v2/captures/collections/?project_id={self.project.pk}&with_counts=true"
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        row = next((r for r in res.data["results"] if r["id"] == collection.id), None)
        self.assertIsNotNone(row, "Expected the created collection in list response")

        expected_occ, expected_taxa = self._expected_counts_for_collection(collection, self.default_threshold)
        self.assertEqual(row["occurrences_count"], expected_occ)
        self.assertEqual(row["taxa_count"], expected_taxa)

    def _expected_event_taxa_count(self, event, threshold: float) -> int:
        """Distinct determinations among this event's occurrences at/above threshold."""
        return (
            Occurrence.objects.filter(
                event=event,
                determination_score__gte=threshold,
            )
            .values("determination_id")
            .distinct()
            .count()
        )

    # EventViewSet tests
    def test_event_taxa_count_respects_threshold(self):
        create_captures(deployment=self.deployment, num_nights=3, images_per_night=3)
        group_images_into_events(deployment=self.deployment)

        url = f"/api/v2/events/?project_id={self.project.pk}"
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        expected = {
            e.pk: self._expected_event_taxa_count(e, self.default_threshold)
            for e in Event.objects.filter(deployment__project=self.project)
        }

        for row in res.data["results"]:
            self.assertEqual(row["taxa_count"], expected[row["id"]])

    # SummaryView tests
    def test_summary_counts_respect_project_threshold(self):
        """Summary should apply project default threshold to occurrences_count and taxa_count."""
        url = f"/api/v2/status/summary/?project_id={self.project.pk}"
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        expected_occurrences = (
            Occurrence.objects.valid()
            .filter(project=self.project, determination_score__gte=self.default_threshold)
            .count()
        )
        expected_taxa = (
            Occurrence.objects.filter(
                project=self.project,
                determination_score__gte=self.default_threshold,
            )
            .values("determination_id")
            .distinct()
            .count()
        )

        self.assertEqual(res.data["occurrences_count"], expected_occurrences)
        self.assertEqual(res.data["taxa_count"], expected_taxa)

    # DeploymentViewSet tests
    def test_deployment_counts_respect_threshold(self):
        """occurrences_count and taxa_count on deployments should exclude low-score occurrences."""
        # Call the save() method to refresh counts
        for dep in Deployment.objects.all():
            dep.save()
        url = f"/api/v2/deployments/?project_id={self.project.pk}"
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        for row in res.data["results"]:
            dep_id = row["id"]
            dep = Deployment.objects.get(pk=dep_id)

            # All occurrences for this deployment
            dep_occs = Occurrence.objects.filter(deployment=dep).distinct()
            dep_high_occs = dep_occs.filter(determination_score__gte=self.default_threshold)

            expected_occurrences_count = dep_high_occs.count()
            expected_taxa_count = dep_high_occs.values("determination_id").distinct().count()

            # Assert the API matches expected counts
            self.assertEqual(row["occurrences_count"], expected_occurrences_count)
            self.assertEqual(row["taxa_count"], expected_taxa_count)

            # If deployment only has low-score occurrences, both counts must be zero
            if dep_occs.exists() and not dep_high_occs.exists():
                self.assertEqual(row["occurrences_count"], 0)
                self.assertEqual(row["taxa_count"], 0)

    def test_taxa_include_occurrence_determinations_not_directly_linked(self):
        """
        Taxa should still appear in taxa list and summary if they come from
        determinations of occurrences in the project, even when those taxa are
        not directly linked to the project via the M2M field.
        """
        # Clear existing taxa and occurrences for a clean slate
        self.project.taxa.clear()
        Occurrence.objects.filter(project=self.project).delete()
        # Create a new taxon not linked to the project
        outside_taxon = Taxon.objects.create(name="OutsideTaxon")

        # Create occurrences in this project with that taxon as determination
        create_occurrences(
            deployment=self.deployment,
            num=2,
            determination_score=0.9,
            taxon=outside_taxon,
        )

        # Confirm taxon is not directly associated with the project
        self.assertFalse(self.project in outside_taxon.projects.all())

        # Taxa endpoint should include the taxon (because of occurrences)
        res_taxa = self.client.get(self.url_taxa)
        self.assertEqual(res_taxa.status_code, status.HTTP_200_OK)
        taxa_names = {t["name"] for t in res_taxa.data["results"]}
        self.assertIn(outside_taxon.name, taxa_names)

        # Summary should also count it
        url_summary = f"/api/v2/status/summary/?project_id={self.project.pk}"
        res_summary = self.client.get(url_summary)
        self.assertEqual(res_summary.status_code, status.HTTP_200_OK)
        summary_taxa_count = res_summary.data["taxa_count"]

        taxa_count = len(res_taxa.data["results"])
        self.assertEqual(
            taxa_count,
            summary_taxa_count,
            f"Mismatch with outside taxon: taxa endpoint returned {taxa_count}, summary {summary_taxa_count}",
        )


class TestProjectDefaultTaxaFilter(APITestCase):
    """
    Tests for project default taxa filtering (include/exclude lists).

    These tests verify that the apply_default_filters() and build_default_filters_q()
    methods correctly apply taxa inclusion and exclusion filters across all viewsets
    and model methods.

    Edge Cases to be Tested (TODO):
    - Empty include/exclude lists (should not filter)
    - Conflicting filters (taxa in both include AND exclude - exclude should win)
    - Hierarchical taxa filtering edge cases (excluding parent excludes children)
    - Invalid project_id or None project handling
    - Direct model method testing (Event.get_occurrences_count, Deployment.update_calculated_fields)
    - apply_defaults=true explicit vs default behavior
    - Taxa with no occurrences in filtered results
    """

    def setUp(self):
        self.project, self.deployment = setup_test_project(reuse=False)
        create_taxa(project=self.project)
        create_captures(deployment=self.deployment)

        # Multiple taxa for include/exclude testing
        self.include_taxa = [
            Taxon.objects.create(name="IncludeTaxonA"),
            Taxon.objects.create(name="IncludeTaxonB"),
        ]
        self.exclude_taxa = [
            Taxon.objects.create(name="ExcludeTaxonA"),
            Taxon.objects.create(name="ExcludeTaxonB"),
        ]

        # Add parent/child taxa for include/exclude
        include_parent = Taxon.objects.create(name="IncludeParent", rank="GENUS")
        include_child = Taxon.objects.create(name="IncludeChild", parent=include_parent, rank="SPECIES")
        exclude_parent = Taxon.objects.create(name="ExcludeParent", rank="GENUS")
        exclude_child = Taxon.objects.create(name="ExcludeChild", parent=exclude_parent, rank="SPECIES")

        # Add parents/children to project & to include/exclude lists
        for t in [include_parent, include_child, exclude_parent, exclude_child]:
            t.projects.add(self.project)
        self.include_taxa_and_parents = self.include_taxa.copy() + [include_parent]
        self.exclude_taxa_and_parents = self.exclude_taxa.copy() + [exclude_parent]
        self.include_taxa += [include_parent, include_child]
        self.exclude_taxa += [exclude_parent, exclude_child]

        # Create occurrences for all taxa
        for taxon in self.include_taxa:
            create_occurrences(deployment=self.deployment, num=2, taxon=taxon, determination_score=0.5)
        for taxon in self.exclude_taxa:
            create_occurrences(deployment=self.deployment, num=2, taxon=taxon, determination_score=0.95)
        self.high_score_taxa = [self.include_taxa[0], self.include_taxa[1]]
        for taxon in self.high_score_taxa:
            create_occurrences(deployment=self.deployment, num=2, taxon=taxon, determination_score=0.95)
        self.user = User.objects.create_user(email="tester@insectai.org", is_staff=False, is_superuser=False)
        self.client.force_authenticate(user=self.user)

    # OccurrenceViewSet tests
    def _get_occurrence_ids(self):
        url = f"/api/v2/occurrences/?project_id={self.project.pk}"
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        return {r.get("determination", {}).get("id") for r in res.json()["results"] if r.get("determination")}

    def test_occurrence_viewset_include_taxa_filter(self):
        self.project.default_filters_include_taxa.set(self.include_taxa_and_parents)
        ids = self._get_occurrence_ids()
        for taxon in self.include_taxa:
            self.assertIn(taxon.id, ids)
        for taxon in self.exclude_taxa:
            self.assertNotIn(taxon.id, ids)

    def test_occurrence_viewset_exclude_taxa_filter(self):
        self.project.default_filters_exclude_taxa.set(self.exclude_taxa_and_parents)
        ids = self._get_occurrence_ids()
        for taxon in self.include_taxa:
            self.assertIn(taxon.id, ids)
        for taxon in self.exclude_taxa:
            self.assertNotIn(taxon.id, ids)

    # TaxonViewSet tests
    def _get_taxon_ids(self):
        url = f"/api/v2/taxa/?project_id={self.project.pk}"
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        return {r["id"] for r in res.json()["results"]}

    def test_taxon_viewset_include_taxa_filter(self):
        self.project.default_filters_include_taxa.set(self.include_taxa_and_parents)
        ids = self._get_taxon_ids()
        for taxon in self.include_taxa:
            self.assertIn(taxon.id, ids)
        for taxon in self.exclude_taxa:
            self.assertNotIn(taxon.id, ids)

    def test_taxon_viewset_exclude_taxa_filter(self):
        self.project.default_filters_exclude_taxa.set(self.exclude_taxa_and_parents)
        ids = self._get_taxon_ids()
        for taxon in self.include_taxa:
            self.assertIn(taxon.id, ids)
        for taxon in self.exclude_taxa:
            self.assertNotIn(taxon.id, ids)

    def test_taxon_viewset_apply_defaults_false_bypasses_taxa_filters(self):
        """
        With apply_defaults=false, taxa view should bypass include/exclude filters.
        This test ensures that build_default_filters_q respects the apply_defaults flag.
        """
        # Set up strict filters: only include a subset of taxa
        self.project.default_filters_include_taxa.set(self.include_taxa_and_parents)

        # With defaults applied, should only see included taxa
        url_with_defaults = f"/api/v2/taxa/?project_id={self.project.pk}"
        res_with_defaults = self.client.get(url_with_defaults)
        self.assertEqual(res_with_defaults.status_code, status.HTTP_200_OK)
        ids_with_defaults = {r["id"] for r in res_with_defaults.json()["results"]}

        # With apply_defaults=false, should see ALL taxa (including excluded ones)
        url_without_defaults = f"/api/v2/taxa/?project_id={self.project.pk}&apply_defaults=false"
        res_without_defaults = self.client.get(url_without_defaults)
        self.assertEqual(res_without_defaults.status_code, status.HTTP_200_OK)
        ids_without_defaults = {r["id"] for r in res_without_defaults.json()["results"]}

        # Verify: without defaults should include ALL taxa (both include and exclude lists)
        all_test_taxa = self.include_taxa + self.exclude_taxa
        for taxon in all_test_taxa:
            self.assertIn(
                taxon.id,
                ids_without_defaults,
                f"With apply_defaults=false, {taxon.name} should be present in taxa list",
            )

        # Verify: without defaults returns more taxa than with defaults
        self.assertGreater(
            len(ids_without_defaults),
            len(ids_with_defaults),
            "apply_defaults=false should return more taxa than with filters applied",
        )

        # Verify: excluded taxa should NOT appear with defaults
        for taxon in self.exclude_taxa:
            self.assertNotIn(
                taxon.id,
                ids_with_defaults,
                f"With defaults applied, excluded taxon {taxon.name} should NOT be present",
            )

    # EventViewSet tests
    def _get_event_counts(self):
        """Helper to return list of (event_id, occurrences_count, taxa_count) from EventViewSet"""
        url = f"/api/v2/events/?project_id={self.project.pk}"
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        return [(e["id"], e["occurrences_count"], e["taxa_count"]) for e in res.json()["results"]]

    def _update_calculated_fields(self):
        for event in Event.objects.filter(project=self.project):
            event.save()

    def test_event_viewset_counts_respect_include_taxa_filter(self):
        """
        EventViewSet occurrences_count and taxa_count should respect default include taxa filters.
        """
        self.project.default_filters_include_taxa.set(self.include_taxa_and_parents)
        self._update_calculated_fields()
        events = self._get_event_counts()

        for event_id, occ_count, taxa_count in events:
            expected_occ_count = Occurrence.objects.filter(
                event_id=event_id, determination__in=self.include_taxa
            ).count()
            expected_taxa_count = (
                Occurrence.objects.filter(event_id=event_id, determination__in=self.include_taxa)
                .values("determination_id")
                .distinct()
                .count()
            )
            self.assertEqual(
                occ_count,
                expected_occ_count,
                f"Event {event_id}: occurrences_count did not respect include taxa filter",
            )
            self.assertEqual(
                taxa_count,
                expected_taxa_count,
                f"Event {event_id}: taxa_count did not respect include taxa filter",
            )

    def test_event_viewset_counts_respect_exclude_taxa_filter(self):
        """
        EventViewSet occurrences_count and taxa_count should respect default exclude taxa filters.
        """
        self.project.default_filters_exclude_taxa.set(self.exclude_taxa_and_parents)
        self._update_calculated_fields()
        events = self._get_event_counts()

        for event_id, occ_count, taxa_count in events:
            expected_occ_count = (
                Occurrence.objects.exclude(determination__in=self.exclude_taxa).filter(event_id=event_id).count()
            )
            expected_taxa_count = (
                Occurrence.objects.exclude(determination__in=self.exclude_taxa)
                .filter(event_id=event_id)
                .values("determination_id")
                .distinct()
                .count()
            )
            self.assertEqual(
                occ_count,
                expected_occ_count,
                f"Event {event_id}: occurrences_count did not respect exclude taxa filter",
            )
            self.assertEqual(
                taxa_count,
                expected_taxa_count,
                f"Event {event_id}: taxa_count did not respect exclude taxa filter",
            )

    # DeploymentViewSet tests
    def _get_deployment_counts(self):
        """Helper to return list of (deployment_id, occurrences_count, taxa_count) from DeploymentViewSet"""
        url = f"/api/v2/deployments/?project_id={self.project.pk}"
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        return [(d["id"], d["occurrences_count"], d["taxa_count"]) for d in res.json()["results"]]

    def _update_deployment_calculated_fields(self):
        """Ensure pre-calculated fields on deployments are up to date before testing"""
        for deployment in Deployment.objects.filter(project=self.project):
            deployment.save()  # This should trigger update_calculated_fields in model save()

    def test_deployment_viewset_counts_respect_include_taxa_filter(self):
        """
        DeploymentViewSet occurrences_count and taxa_count should respect default include taxa filters.
        """
        self.project.default_filters_include_taxa.set(self.include_taxa_and_parents)
        self._update_deployment_calculated_fields()
        deployments = self._get_deployment_counts()

        for dep_id, occ_count, taxa_count in deployments:
            expected_occ_count = Occurrence.objects.filter(
                deployment_id=dep_id, determination__in=self.include_taxa
            ).count()
            expected_taxa_count = (
                Occurrence.objects.filter(deployment_id=dep_id, determination__in=self.include_taxa)
                .values("determination_id")
                .distinct()
                .count()
            )
            self.assertEqual(
                occ_count,
                expected_occ_count,
                f"Deployment {dep_id}: occurrences_count did not respect include taxa filter",
            )
            self.assertEqual(
                taxa_count,
                expected_taxa_count,
                f"Deployment {dep_id}: taxa_count did not respect include taxa filter",
            )

    def test_deployment_viewset_counts_respect_exclude_taxa_filter(self):
        """
        DeploymentViewSet occurrences_count and taxa_count should respect default exclude taxa filters.
        """
        self.project.default_filters_exclude_taxa.set(self.exclude_taxa_and_parents)
        self._update_deployment_calculated_fields()
        deployments = self._get_deployment_counts()

        for dep_id, occ_count, taxa_count in deployments:
            expected_occ_count = (
                Occurrence.objects.exclude(determination__in=self.exclude_taxa).filter(deployment_id=dep_id).count()
            )
            expected_taxa_count = (
                Occurrence.objects.exclude(determination__in=self.exclude_taxa)
                .filter(deployment_id=dep_id)
                .values("determination_id")
                .distinct()
                .count()
            )
            self.assertEqual(
                occ_count,
                expected_occ_count,
                f"Deployment {dep_id}: occurrences_count did not respect exclude taxa filter",
            )
            self.assertEqual(
                taxa_count,
                expected_taxa_count,
                f"Deployment {dep_id}: taxa_count did not respect exclude taxa filter",
            )

    # SourceImageViewSet tests
    def _get_source_image_counts(self):
        """
        Helper to fetch list of (capture_id, occurrences_count, taxa_count) from SourceImageViewSet
        """
        url = f"/api/v2/captures/?project_id={self.project.pk}&with_counts=true"
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        return [(c["id"], c["occurrences_count"], c["taxa_count"]) for c in res.json()["results"]]

    def test_sourceimage_viewset_counts_respect_include_taxa_filter(self):
        """
        SourceImageViewSet occurrences_count and taxa_count should respect default include taxa filters.
        """
        self.project.default_filters_include_taxa.set(self.include_taxa_and_parents)
        captures = self._get_source_image_counts()

        for capture_id, occ_count, taxa_count in captures:
            # Get all occurrences linked to this capture via detections
            expected_occurrence_qs = Occurrence.objects.filter(
                detections__source_image_id=capture_id,
                determination__in=self.include_taxa,
            ).distinct()

            expected_occ_count = expected_occurrence_qs.count()
            expected_taxa_count = expected_occurrence_qs.values("determination_id").distinct().count()

            self.assertEqual(
                occ_count,
                expected_occ_count,
                f"Capture {capture_id}: occurrences_count did not respect include taxa filter",
            )
            self.assertEqual(
                taxa_count,
                expected_taxa_count,
                f"Capture {capture_id}: taxa_count did not respect include taxa filter",
            )

    def test_sourceimage_viewset_counts_respect_exclude_taxa_filter(self):
        """
        SourceImageViewSet occurrences_count and taxa_count should respect default exclude taxa filters.
        """
        self.project.default_filters_exclude_taxa.set(self.exclude_taxa_and_parents)
        captures = self._get_source_image_counts()

        for capture_id, occ_count, taxa_count in captures:
            expected_occurrence_qs = (
                Occurrence.objects.exclude(determination__in=self.exclude_taxa)
                .filter(detections__source_image_id=capture_id)
                .distinct()
            )

            expected_occ_count = expected_occurrence_qs.count()
            expected_taxa_count = expected_occurrence_qs.values("determination_id").distinct().count()

            self.assertEqual(
                occ_count,
                expected_occ_count,
                f"Capture {capture_id}: occurrences_count did not respect exclude taxa filter",
            )
            self.assertEqual(
                taxa_count,
                expected_taxa_count,
                f"Capture {capture_id}: taxa_count did not respect exclude taxa filter",
            )

    # SourceImageCollectionViewSet tests
    def _get_collection_counts(self):
        """Helper to return list of (collection_id, occurrences_count, taxa_count)"""
        url = f"/api/v2/captures/collections/?project_id={self.project.pk}&with_counts=true"
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        return [(c["id"], c["occurrences_count"], c["taxa_count"]) for c in res.json()["results"]]

    def test_sourceimagecollection_viewset_counts_respect_include_taxa_filter(self):
        """
        SourceImageCollectionViewSet occurrences_count and taxa_count should respect default include taxa filters.
        """
        self.project.default_filters_include_taxa.set(self.include_taxa_and_parents)
        collections = self._get_collection_counts()

        for collection_id, occ_count, taxa_count in collections:
            expected_occurrence_qs = Occurrence.objects.filter(
                detections__source_image__collections__id=collection_id,
                determination__in=self.include_taxa,
            ).distinct()

            expected_occ_count = expected_occurrence_qs.count()
            expected_taxa_count = expected_occurrence_qs.values("determination_id").distinct().count()

            self.assertEqual(
                occ_count,
                expected_occ_count,
                f"Collection {collection_id}: occurrences_count did not respect include taxa filter",
            )
            self.assertEqual(
                taxa_count,
                expected_taxa_count,
                f"Collection {collection_id}: taxa_count did not respect include taxa filter",
            )

    def test_sourceimagecollection_viewset_counts_respect_exclude_taxa_filter(self):
        """
        SourceImageCollectionViewSet occurrences_count and taxa_count should respect default exclude taxa filters.
        """
        self.project.default_filters_exclude_taxa.set(self.exclude_taxa_and_parents)
        collections = self._get_collection_counts()

        for collection_id, occ_count, taxa_count in collections:
            expected_occurrence_qs = (
                Occurrence.objects.exclude(determination__in=self.exclude_taxa)
                .filter(detections__source_image__collections__id=collection_id)
                .distinct()
            )

            expected_occ_count = expected_occurrence_qs.count()
            expected_taxa_count = expected_occurrence_qs.values("determination_id").distinct().count()

            self.assertEqual(
                occ_count,
                expected_occ_count,
                f"Collection {collection_id}: occurrences_count did not respect exclude taxa filter",
            )
            self.assertEqual(
                taxa_count,
                expected_taxa_count,
                f"Collection {collection_id}: taxa_count did not respect exclude taxa filter",
            )

    # SummaryView tests
    def _get_summary_counts(self):
        """Helper to return occurrences_count and taxa_count from SummaryView."""
        url = f"/api/v2/status/summary/?project_id={self.project.pk}"
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.json()
        return data["occurrences_count"], data["taxa_count"]

    def test_summary_view_counts_respect_include_taxa_filter(self):
        """
        SummaryView occurrences_count and taxa_count should respect default include taxa filters.
        """
        self.project.default_filters_include_taxa.set(self.include_taxa_and_parents)
        occ_count, taxa_count = self._get_summary_counts()

        expected_occ_count = Occurrence.objects.filter(
            project=self.project,
            determination__in=self.include_taxa,
        ).count()

        expected_taxa_count = (
            Occurrence.objects.filter(project=self.project, determination__in=self.include_taxa)
            .values("determination_id")
            .distinct()
            .count()
        )

        self.assertEqual(
            occ_count,
            expected_occ_count,
            "SummaryView occurrences_count did not respect include taxa filter",
        )
        self.assertEqual(
            taxa_count,
            expected_taxa_count,
            "SummaryView taxa_count did not respect include taxa filter",
        )

    def test_summary_view_counts_respect_exclude_taxa_filter(self):
        """
        SummaryView occurrences_count and taxa_count should respect default exclude taxa filters.
        """
        self.project.default_filters_exclude_taxa.set(self.exclude_taxa_and_parents)
        occ_count, taxa_count = self._get_summary_counts()

        expected_occ_count = (
            Occurrence.objects.exclude(determination__in=self.exclude_taxa).filter(project=self.project).count()
        )
        expected_taxa_count = (
            Occurrence.objects.exclude(determination__in=self.exclude_taxa)
            .filter(project=self.project)
            .values("determination_id")
            .distinct()
            .count()
        )

        self.assertEqual(
            occ_count,
            expected_occ_count,
            "SummaryView occurrences_count did not respect exclude taxa filter",
        )
        self.assertEqual(
            taxa_count,
            expected_taxa_count,
            "SummaryView taxa_count did not respect exclude taxa filter",
        )

    def test_summary_counts_respect_threshold_and_include_taxa(self):
        """
        SummaryView occurrences_count and taxa_count should respect both
        default score threshold and include taxa filters.
        """
        threshold = 0.9
        self.project.default_filters_score_threshold = threshold
        self.project.save()
        self.project.default_filters_include_taxa.set(self.include_taxa_and_parents)

        occ_count, taxa_count = self._get_summary_counts()

        expected_occurrences = Occurrence.objects.filter(
            project=self.project,
            determination__in=self.high_score_taxa,
            determination_score__gte=threshold,
        )
        expected_occ_count = expected_occurrences.count()
        expected_taxa_count = expected_occurrences.values("determination_id").distinct().count()

        self.assertEqual(
            occ_count,
            expected_occ_count,
            "SummaryView occurrences_count did not respect threshold + include taxa filters",
        )
        self.assertEqual(
            taxa_count,
            expected_taxa_count,
            "SummaryView taxa_count did not respect threshold + include taxa filters",
        )

    # Combined filter tests (threshold + taxa)
    def test_combined_threshold_and_include_taxa_occurrences(self):
        """
        OccurrenceViewSet should apply both score threshold and include taxa filters together.
        Only occurrences that meet BOTH criteria should be returned.
        """
        threshold = 0.8
        self.project.default_filters_score_threshold = threshold
        self.project.save()
        self.project.default_filters_include_taxa.set(self.include_taxa_and_parents)

        url = f"/api/v2/occurrences/?project_id={self.project.pk}"
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        returned_ids = {r.get("determination", {}).get("id") for r in res.json()["results"] if r.get("determination")}

        # Should only include taxa from include list with high scores
        for taxon in self.high_score_taxa:
            self.assertIn(taxon.id, returned_ids, f"High-score included taxon {taxon.name} should be present")

        # Should exclude low-score included taxa
        for taxon in [t for t in self.include_taxa if t not in self.high_score_taxa]:
            self.assertNotIn(taxon.id, returned_ids, f"Low-score included taxon {taxon.name} should be filtered out")

        # Should exclude all excluded taxa regardless of score
        for taxon in self.exclude_taxa:
            self.assertNotIn(taxon.id, returned_ids, f"Excluded taxon {taxon.name} should not be present")

    def test_combined_threshold_and_exclude_taxa_occurrences(self):
        """
        OccurrenceViewSet should apply both score threshold and exclude taxa filters together.
        Occurrences must meet threshold AND not be in exclude list.
        """
        threshold = 0.8
        self.project.default_filters_score_threshold = threshold
        self.project.save()
        self.project.default_filters_exclude_taxa.set(self.exclude_taxa_and_parents)

        url = f"/api/v2/occurrences/?project_id={self.project.pk}"
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        returned_ids = {r.get("determination", {}).get("id") for r in res.json()["results"] if r.get("determination")}

        # Should include high-score included taxa
        for taxon in self.high_score_taxa:
            self.assertIn(taxon.id, returned_ids, f"High-score non-excluded taxon {taxon.name} should be present")

        # Should exclude low-score included taxa (filtered by threshold)
        for taxon in [t for t in self.include_taxa if t not in self.high_score_taxa]:
            self.assertNotIn(taxon.id, returned_ids, f"Low-score taxon {taxon.name} should be filtered by threshold")

        # Should exclude all excluded taxa even if high score
        for taxon in self.exclude_taxa:
            self.assertNotIn(
                taxon.id,
                returned_ids,
                f"Excluded taxon {taxon.name} should not be present even with high score",
            )

    def test_combined_threshold_and_include_taxa_in_taxa_list(self):
        """
        TaxonViewSet should show only taxa that have occurrences meeting both
        score threshold and taxa inclusion criteria.
        """
        threshold = 0.8
        self.project.default_filters_score_threshold = threshold
        self.project.save()
        self.project.default_filters_include_taxa.set(self.include_taxa_and_parents)

        url = f"/api/v2/taxa/?project_id={self.project.pk}"
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        returned_ids = {r["id"] for r in res.json()["results"]}

        # Should only show taxa from include list that have high-score occurrences
        for taxon in self.high_score_taxa:
            self.assertIn(taxon.id, returned_ids, f"High-score included taxon {taxon.name} should appear in taxa list")

        # Should NOT show low-score included taxa
        for taxon in [t for t in self.include_taxa if t not in self.high_score_taxa]:
            self.assertNotIn(taxon.id, returned_ids, f"Low-score taxon {taxon.name} should not appear")

        # Should NOT show excluded taxa
        for taxon in self.exclude_taxa:
            self.assertNotIn(taxon.id, returned_ids, f"Excluded taxon {taxon.name} should not appear")

    def test_combined_filters_bypass_with_apply_defaults_false(self):
        """
        Setting apply_defaults=false should bypass BOTH threshold and taxa filters.
        """
        threshold = 0.8
        self.project.default_filters_score_threshold = threshold
        self.project.save()
        self.project.default_filters_include_taxa.set(self.include_taxa_and_parents)

        # With apply_defaults=false and low threshold, should get everything
        url = f"/api/v2/occurrences/?project_id={self.project.pk}&apply_defaults=false&classification_threshold=0.0"
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        returned_ids = {r.get("determination", {}).get("id") for r in res.json()["results"] if r.get("determination")}

        # Should include ALL taxa (include and exclude) with any score
        all_taxa = self.include_taxa + self.exclude_taxa
        for taxon in all_taxa:
            self.assertIn(taxon.id, returned_ids, f"With apply_defaults=false, {taxon.name} should be present")

    # SourceImageCollectionViewSet tests with taxa filters
    def test_collection_counts_respect_include_taxa_with_threshold(self):
        """
        SourceImageCollectionViewSet counts should respect both score threshold
        and include taxa filters for nested occurrences.
        """
        threshold = 0.8
        self.project.default_filters_score_threshold = threshold
        self.project.save()
        self.project.default_filters_include_taxa.set(self.include_taxa_and_parents)

        # Create a collection with some images
        collection = SourceImageCollection.objects.filter(project=self.project).first()
        if not collection:
            collection = SourceImageCollection.objects.create(
                name="Test Collection",
                project=self.project,
                method="manual",
            )

        # Add some images to the collection
        images = SourceImage.objects.filter(deployment=self.deployment)[:3]
        collection.images.set(images)

        url = f"/api/v2/captures/collections/?project_id={self.project.pk}&with_counts=true"
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        # Find our collection in results
        results = {r["id"]: r for r in res.json()["results"]}
        self.assertIn(collection.pk, results, "Collection should be in results")

        collection_data = results[collection.pk]

        # Calculate expected counts: occurrences through images->detections->occurrences
        # that meet both threshold and taxa inclusion
        expected_occurrences = Occurrence.objects.filter(
            detections__source_image__in=images,
            determination__in=self.high_score_taxa,
            determination_score__gte=threshold,
        ).distinct()

        expected_occ_count = expected_occurrences.count()
        expected_taxa_count = expected_occurrences.values("determination_id").distinct().count()

        self.assertEqual(
            collection_data["occurrences_count"],
            expected_occ_count,
            "Collection occurrences_count should respect combined filters",
        )
        self.assertEqual(
            collection_data["taxa_count"],
            expected_taxa_count,
            "Collection taxa_count should respect combined filters",
        )

    def test_collection_counts_respect_exclude_taxa_with_threshold(self):
        """
        SourceImageCollectionViewSet counts should respect both score threshold
        and exclude taxa filters for nested occurrences.
        """
        threshold = 0.8
        self.project.default_filters_score_threshold = threshold
        self.project.save()
        self.project.default_filters_exclude_taxa.set(self.exclude_taxa_and_parents)

        # Create a collection with some images
        collection = SourceImageCollection.objects.filter(project=self.project).first()
        if not collection:
            collection = SourceImageCollection.objects.create(
                name="Test Collection 2",
                project=self.project,
                method="manual",
            )

        # Add some images to the collection
        images = SourceImage.objects.filter(deployment=self.deployment)[:3]
        collection.images.set(images)

        url = f"/api/v2/captures/collections/?project_id={self.project.pk}&with_counts=true"
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        # Find our collection in results
        results = {r["id"]: r for r in res.json()["results"]}
        self.assertIn(collection.pk, results, "Collection should be in results")

        collection_data = results[collection.pk]

        # Calculate expected counts: high-score occurrences NOT in exclude list
        expected_occurrences = (
            Occurrence.objects.filter(
                detections__source_image__in=images,
                determination_score__gte=threshold,
            )
            .exclude(determination__in=self.exclude_taxa)
            .distinct()
        )

        expected_occ_count = expected_occurrences.count()
        expected_taxa_count = expected_occurrences.values("determination_id").distinct().count()

        self.assertEqual(
            collection_data["occurrences_count"],
            expected_occ_count,
            "Collection occurrences_count should respect threshold + exclude filters",
        )
        self.assertEqual(
            collection_data["taxa_count"],
            expected_taxa_count,
            "Collection taxa_count should respect threshold + exclude filters",
        )

    def test_taxon_detail_visible_when_excluded_from_list(self):
        """
        Taxon excluded by default project taxa filter should not appear in list,
        but should still be accessible via detail view.
        """
        excluded_taxon = self.exclude_taxa[0]
        self.project.default_filters_exclude_taxa.set([excluded_taxon])

        # Taxon should NOT appear in list view
        list_ids = self._get_taxon_ids()
        self.assertNotIn(excluded_taxon.id, list_ids)

        # Taxon detail endpoint should still return 200
        detail_url = f"/api/v2/taxa/{excluded_taxon.id}/?project_id={self.project.pk}"
        res = self.client.get(detail_url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
