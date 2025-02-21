import datetime
import logging

from django.db import connection, models
from django.test import TestCase
from guardian.shortcuts import get_perms
from rest_framework import status
from rest_framework.test import APIRequestFactory, APITestCase
from rich import print

from ami.jobs.models import Job
from ami.main.models import (
    Deployment,
    Device,
    Event,
    Occurrence,
    Project,
    S3StorageSource,
    Site,
    SourceImage,
    SourceImageCollection,
    Taxon,
    TaxonRank,
    group_images_into_events,
)
from ami.ml.models.pipeline import Pipeline
from ami.tests.fixtures.main import create_captures, create_occurrences, create_taxa, setup_test_project
from ami.users.models import User
from ami.users.roles import BasicMember, Identifier, MLDataManager, ProjectManager, Researcher

logger = logging.getLogger(__name__)


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

        create_captures(deployment=self.deployment)
        events = group_images_into_events(deployment=self.deployment)

        for event in events:
            event.captures.all().delete()

        delete_empty_events(deployment=self.deployment)

        remaining_events = Event.objects.filter(pk__in=[event.pk for event in events])

        assert remaining_events.count() == 0

    def test_setting_image_dimensions(self):
        from ami.main.models import set_dimensions_for_collection

        image_width, image_height = 100, 100

        create_captures(deployment=self.deployment)
        events = group_images_into_events(deployment=self.deployment)

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
        group_images_into_events(deployment=deployment)
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
        group_images_into_events(deployment=self.deployment)
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
        group_images_into_events(deployment=self.deployment)

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
        group_images_into_events(deployment=deployment_one)
        group_images_into_events(deployment=deployment_two)
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
        group_images_into_events(deployment=deployment)
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
        group_images_into_events(deployment=deployment)
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
            group_images_into_events(deployment=deployment)
            create_occurrences(deployment=deployment, num=5)
        self.project_ids = [project.id for project in Project.objects.all()]

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
        self.user_1 = User.objects.create_user(
            email="testuser@insectai.org",
            is_staff=True,
        )
        self.user_2 = User.objects.create_user(
            email="testuser2@insectai.org",
            is_staff=True,
        )
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
        self.assertTrue(self.owner.has_perm(Project.Permissions.VIEW, self.project))
        self.assertTrue(self.owner.has_perm(Project.Permissions.CHANGE, self.project))
        self.assertTrue(self.owner.has_perm(Project.Permissions.DELETE, self.project))
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
        self.assertTrue(self.member.has_perm(Project.Permissions.VIEW, self.project))
        self.assertTrue(self.member.has_perm(Project.Permissions.CHANGE, self.project))
        self.assertFalse(self.member.has_perm(Project.Permissions.DELETE, self.project))

        # test permissions from the API
        # create the project
        self._create_project(self.owner, self.member)

        # Authenticate as member
        self.client.force_authenticate(user=self.member)

        # Member can view and update, but not delete
        response = self.client.get(f"/api/v2/projects/{self.project.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        response = self.client.patch(f"/api/v2/projects/{self.project.id}/", {"name": "Updated Again"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        response = self.client.delete(f"/api/v2/projects/{self.project.id}/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_other_user_permissions(self):
        # Other users only have view permissions
        self.assertTrue(self.other_user.has_perm(Project.Permissions.VIEW, self.project))
        self.assertFalse(self.other_user.has_perm(Project.Permissions.CHANGE, self.project))
        self.assertFalse(self.other_user.has_perm(Project.Permissions.DELETE, self.project))

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
        self.assertTrue(self.new_owner.has_perm(Project.Permissions.VIEW, self.project))
        self.assertTrue(self.new_owner.has_perm(Project.Permissions.CHANGE, self.project))
        self.assertTrue(self.new_owner.has_perm(Project.Permissions.DELETE, self.project))

    def test_permissions_on_member_removal(self):
        """Test permissions are removed when a user is no longer a member of the project."""
        # Remove the member from the project
        self.project.members.remove(self.member)

        # Check the removed member no longer has permissions
        self.assertFalse(self.member.has_perm(Project.Permissions.CHANGE, self.project))

    def test_superuser_has_all_permissions(self):
        # Log in as the superuser
        self.client.force_authenticate(user=self.superuser)

        # Get all permissions for the superuser on the project
        superuser_permissions = get_perms(self.superuser, self.project)

        # Assert that the superuser has all object-level permissions
        project_permissions = [
            Project.Permissions.VIEW,
            Project.Permissions.CHANGE,
            Project.Permissions.DELETE,
        ]
        for perm in project_permissions:
            self.assertIn(perm, superuser_permissions)

    def test_superuser_can_create_project(self):
        """Ensure a superuser can create a project."""
        self.client.force_authenticate(user=self.superuser)
        data = {"name": "Superuser Project", "description": "Created by superuser"}
        response = self.client.post(self.project_create_endpoint, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_staff_user_can_create_project(self):
        """Ensure a staff user can create a project."""
        self.client.force_authenticate(user=self.staff_user)
        data = {"name": "Staff User Project", "description": "Created by staff user"}
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
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class TestRolePermissions(APITestCase):
    # Create users
    def setUp(self) -> None:
        self.project_manager = User.objects.create_user(email="project_manager@insectai.org", is_staff=False)
        self._create_project(self.project_manager)
        ProjectManager.assign_user(self.project_manager, self.project)

        self.basic_member = User.objects.create_user(email="basic_member@insectai.org", is_staff=False)
        BasicMember.assign_user(self.basic_member, self.project)
        self.identifier = User.objects.create_user(email="identifier@insectai.org", is_staff=False)
        Identifier.assign_user(self.identifier, self.project)
        self.researcher = User.objects.create_user(email="researcher@insectai.org", is_staff=False)
        Researcher.assign_user(self.researcher, self.project)

        self.ml_data_manager = User.objects.create_user(email="ml_data_manager@insectai.org", is_staff=False)
        MLDataManager.assign_user(self.ml_data_manager, self.project)
        # Create a staff user
        self.staff_user = User.objects.create_user(
            email="staffuser@insectai.org",
            password="password123",
            is_staff=True,
        )
        # Create a regular with no role assigned in the project
        self.other = User.objects.create_user(
            email="other@insectai.org",
            password="password123",
        )
        self._create_job()

    def _create_project(self, owner):
        self.project = Project.objects.create(name="Insect Project", description="Test Description", owner=owner)
        self.deployment = Deployment.objects.create(name="Test Deployment", project=self.project)

        create_captures(deployment=self.deployment)
        group_images_into_events(deployment=self.deployment)
        create_taxa(project=self.project)
        create_occurrences(deployment=self.deployment, num=1)
        self._create_job()

    def _create_job(self):
        self.job = Job.objects.create(name="Test Job", project=self.project)

    def _can_user_update_identification(self, user):
        url = "/api/v2/identifications/"
        self.client.force_authenticate(user=user)

        response = self.client.post(
            url,
            {
                "occurrence_id": self.project.occurrences.first().pk,
                "taxon_id": Taxon.objects.first().pk,
            },
        )
        return response.status_code, response.json().get("id")

    def _can_user_delete_identification(self, user, identification_id):
        url = f"/api/v2/identifications/{identification_id}/"
        self.client.force_authenticate(user=user)

        response = self.client.delete(url)
        return response.status_code

    def _can_user_create_project(self, user):
        self.client.force_authenticate(user=user)
        payload = {"name": "Test Project", "description": "Test Description"}
        # Create a project
        response = self.client.post("/api/v2/projects/", payload)
        project_id = response.json().get("id")
        return response.status_code, project_id

    def _can_user_update_project(self, user, project_id):
        """Tests if the user can update a project."""
        self.client.force_authenticate(user=user)

        payload = {"name": "Updated Project Name"}

        response = self.client.patch(f"/api/v2/projects/{project_id}/", payload)
        return response.status_code

    def _can_user_delete_project(self, user, project_id):
        """Tests if the user can delete a project."""
        self.client.force_authenticate(user=user)

        response = self.client.delete(f"/api/v2/projects/{project_id}/")
        print(f"Response: {response.content}")
        return response.status_code

    def _can_user_view_project(self, user, project_id):
        # Get the project
        self.client.force_authenticate(user=user)
        response = self.client.get(f"/api/v2/projects/{project_id}/")
        return response.status_code

    def _user_can_create_job(self, user):
        jobs_url = "/api/v2/jobs/"
        self.client.force_authenticate(user=user)

        payload = {"delay": "1", "name": "test", "project_id": self.project.pk, "source_image_collection_id": 1}
        response = self.client.post(jobs_url, payload)
        return response.status_code

    def _can_user_run_job(self, user, job_id):
        run_job_url = f"/api/v2/jobs/{job_id}/run/"

        self.client.force_authenticate(user=user)
        response = self.client.post(run_job_url)
        return response.status_code

    def _can_user_retry_job(self, user, job_id):
        retry_job_url = f"/api/v2/jobs/{job_id}/run/"

        self.client.force_authenticate(user=user)
        response = self.client.post(retry_job_url)
        return response.status_code

    def test_basic_member_permissions(self):
        """Test BasicMember role permissions."""

        expected_permissions = BasicMember.permissions
        assigned_permissions = set(get_perms(self.basic_member, self.project))
        self.assertEqual(assigned_permissions, expected_permissions)
        # BasicMember can not update an identification
        response_status, _ = self._can_user_update_identification(self.basic_member)
        self.assertEqual(response_status, status.HTTP_403_FORBIDDEN)

        self._create_job()

        # BasicMember cannot delete a project
        self.assertEqual(self._can_user_delete_project(self.basic_member, self.project.id), status.HTTP_403_FORBIDDEN)
        # Basic Member can update a project
        self.assertEqual(self._can_user_update_project(self.basic_member, self.project.id), status.HTTP_200_OK)

        # basic member cannot run job
        self.assertEqual(self._can_user_run_job(self.basic_member, self.job.pk), status.HTTP_403_FORBIDDEN)
        # basic member cannot retry job
        self.assertEqual(self._can_user_retry_job(self.basic_member, self.job.pk), status.HTTP_403_FORBIDDEN)

    def test_researcher_permissions(self):
        """Test Researcher role permissions."""

        expected_permissions = Researcher.permissions
        assigned_permissions = set(get_perms(self.researcher, self.project))
        self.assertEqual(assigned_permissions, expected_permissions)

    def test_identifier_permissions(self):
        """Test Identifier role permissions."""

        expected_permissions = Identifier.permissions
        assigned_permissions = set(get_perms(self.identifier, self.project))
        self.assertEqual(assigned_permissions, expected_permissions)

        # Identifier can  update an identification
        response_status, identification_id = self._can_user_update_identification(self.identifier)
        self.assertEqual(response_status, status.HTTP_201_CREATED)

        # Identifier can only delete their own identifications
        self.assertEqual(
            self._can_user_delete_identification(self.identifier, identification_id), status.HTTP_204_NO_CONTENT
        )

        response_status, project_manager_identification_id = self._can_user_update_identification(self.project_manager)
        # Identifier cannot delete identifications created by other users
        self.assertEqual(
            self._can_user_delete_identification(self.identifier, project_manager_identification_id),
            status.HTTP_403_FORBIDDEN,
        )
        # Project manager can delete identifications created by other users
        response_status, identification_id = self._can_user_update_identification(self.identifier)
        self.assertEqual(
            self._can_user_delete_identification(self.identifier, identification_id), status.HTTP_204_NO_CONTENT
        )

    def test_ml_data_manager_permissions(self):
        """Test MLDataManager role permissions."""

        expected_permissions = MLDataManager.permissions
        assigned_permissions = set(get_perms(self.ml_data_manager, self.project))
        self.assertEqual(assigned_permissions, expected_permissions)

        # MLDataManager can run jobs
        self.assertEqual(self._can_user_run_job(self.ml_data_manager, self.job.pk), status.HTTP_200_OK)
        # MLDataManager can retry jobs
        self.assertEqual(self._can_user_retry_job(self.ml_data_manager, self.job.pk), status.HTTP_200_OK)

    def test_project_manager_permissions(self):
        """Test ProjectManager role comprehensive permissions."""

        expected_permissions = ProjectManager.permissions
        assigned_permissions = set(get_perms(self.project_manager, self.project))
        self.assertEqual(assigned_permissions, expected_permissions)
        collections_url = "/api/v2/captures/collections/"

        self.client.force_authenticate(user=self.project_manager)
        response = self.client.post(
            collections_url,
            {
                "description": "new collection description",
                "name": "new collection",
                "project": self.project.pk,
                "method": "common_combined",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        collection_id = response.json().get("id")
        # Collections
        # Project Manager can update the collection
        response = self.client.patch(f"/api/v2/captures/collections/{collection_id}/", {"name": "Updated Collection"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Project Manager can populate the collection
        populate_url = f"/api/v2/captures/collections/{collection_id}/populate/"
        response = self.client.post(populate_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Project Manager can delete the collection
        response = self.client.delete(f"/api/v2/captures/collections/{collection_id}/")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        response = self.client.post(
            collections_url,
            {
                "description": "new collection description",
                "name": "new collection",
                "project": self.project.pk,
                "method": "common_combined",
            },
        )
        collection_id = response.get("id")
        # Storage
        # Project Manager can create storage
        storage_url = "/api/v2/storage/"
        response = self.client.post(storage_url, {"name": "test", "project": self.project.pk, "bucket": "test"})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        storage_id = response.json().get("id")

        # Project Manager can update storage
        response = self.client.patch(f"/api/v2/storage/{storage_id}/", {"name": "Updated Storage"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Project Manager can delete storage
        response = self.client.delete(f"/api/v2/storage/{storage_id}/")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # Site
        # Project Manager can create a site
        sites_url = "/api/v2/deployments/sites/"
        response = self.client.post(
            sites_url, {"description": "new site description", "name": "new site", "project": self.project.pk}
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        site_id = response.json().get("id")

        # Project Manager can update site
        response = self.client.patch(f"/api/v2/deployments/sites/{site_id}/", {"name": "Updated Site"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Project Manager can delete site
        response = self.client.delete(f"/api/v2/deployments/sites/{site_id}/")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # Device
        # Project Manager can create a device
        devices_url = "/api/v2/deployments/devices/"
        response = self.client.post(
            devices_url, {"description": "device description", "name": "device", "project": self.project.pk}
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        device_id = response.json().get("id")

        # Project Manager can update device
        response = self.client.patch(f"/api/v2/deployments/devices/{device_id}/", {"name": "Updated Device"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Project Manager can delete device
        response = self.client.delete(f"/api/v2/deployments/devices/{device_id}/")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # Jobs
        #  Project Manager can create a job
        jobs_url = "/api/v2/jobs/"
        response = self.client.post(jobs_url, {"delay": "1", "name": "new job ", "project_id": self.project.pk})
        logger.info(f"Job create response {response.json()}")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        job_id = response.json().get("id")

        # #  Project Manager can start a job
        # start_job_url = f"/api/v2/jobs/{job_id}/start/"
        # response = self.client.post(start_job_url)
        # self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Project Manager can retry a job
        retry_job_url = f"/api/v2/jobs/{job_id}/retry/"
        response = self.client.post(retry_job_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Project Manager can cancel a job
        cancel_job_url = f"/api/v2/jobs/{job_id}/cancel/"
        response = self.client.post(cancel_job_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Project Manager can delete a job
        delete_job_url = f"/api/v2/jobs/{job_id}/"
        response = self.client.delete(delete_job_url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
