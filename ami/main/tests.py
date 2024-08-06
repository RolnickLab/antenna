import datetime
import logging
import pathlib
import uuid

from django.db import connection
from django.test import TestCase
from rest_framework.test import APIRequestFactory, APITestCase
from rich import print

from ami.main.models import (
    Deployment,
    Detection,
    Event,
    Occurrence,
    Project,
    SourceImage,
    TaxaList,
    Taxon,
    TaxonRank,
    group_images_into_events,
)
from ami.users.models import User

logger = logging.getLogger(__name__)


def setup_test_project(reuse=True) -> tuple[Project, Deployment]:
    if reuse:
        project, _ = Project.objects.get_or_create(name="Test Project")
        deployment, _ = Deployment.objects.get_or_create(project=project, name="Test Deployment")
    else:
        short_id = uuid.uuid4().hex[:8]
        project = Project.objects.create(name=f"Test Project {short_id}")
        deployment = Deployment.objects.create(project=project, name=f"Test Deployment {short_id}")
    return project, deployment


def create_captures(
    deployment: Deployment,
    num_nights: int = 3,
    images_per_night: int = 3,
    interval_minutes: int = 10,
    subdir: str = "test",
):
    # Create some images over a few monitoring nights
    first_night = datetime.datetime.now()

    created = []
    for night in range(num_nights):
        for i in range(images_per_night):
            path = pathlib.Path(subdir) / f"{night}_{i}.jpg"
            img = SourceImage.objects.create(
                deployment=deployment,
                timestamp=first_night + datetime.timedelta(days=night, minutes=i * interval_minutes),
                path=path,
            )
            created.append(img)

    return created


TEST_TAXA_CSV_DATA = """
id,name,rank,parent
1,Lepidoptera,ORDER,
2,Nymphalidae,FAMILY,Lepidoptera
3,Vanessa,GENUS,Nymphalidae
4,Vanessa atalanta,SPECIES,Vanessa
5,Vanessa cardui,SPECIES,Vanessa
6,Vanessa itea,SPECIES,Vanessa
""".strip()


def create_taxa(project: Project, csv_data: str = TEST_TAXA_CSV_DATA):
    import csv
    from io import StringIO

    taxa_list = TaxaList.objects.create(name="Test Taxa List")
    taxa_list.projects.add(project)

    def create_taxon(taxon_data: dict, parent=None):
        taxon, _ = Taxon.objects.get_or_create(
            id=taxon_data["id"],
            name=taxon_data["name"],
            rank=taxon_data["rank"],
            parent=parent,
        )
        taxon.projects.add(project)
        taxa_list.taxa.add(taxon)

        for child_data in taxon_data.get("children", []):
            create_taxon(child_data, parent=taxon)
        return taxon

    reader = csv.DictReader(StringIO(csv_data.strip()))
    for row in reader:
        create_taxon(row)

    return taxa_list


def create_occurrences(
    deployment: Deployment,
    num: int = 6,
):
    event = Event.objects.filter(deployment=deployment).first()
    if not event:
        raise ValueError("No events found for deployment")

    for i in range(num):
        # Every Occurrence requires a Detection
        source_image = SourceImage.objects.filter(event=event).order_by("?").first()
        if not source_image:
            raise ValueError("No source images found for event")
        taxon = Taxon.objects.filter(projects=deployment.project).order_by("?").first()
        if not taxon:
            raise ValueError("No taxa found for project")
        detection = Detection.objects.create(
            source_image=source_image,
            timestamp=source_image.timestamp,  # @TODO this should be automatically set to the source image timestamp
        )
        # Could speed this up by creating an Occurrence with a determined taxon directly
        # but this tests more of the code.
        detection.classifications.create(
            taxon=taxon,
            score=0.9,
            timestamp=datetime.datetime.now(),
        )
        occurrence = detection.associate_new_occurrence()

        # Assert that the occurrence was created and has a detection, event, first_appearance,
        # and species determination
        assert detection.occurrence is not None
        assert detection.occurrence.event is not None
        assert detection.occurrence.first_appearance is not None
        assert occurrence.best_detection is not None
        assert occurrence.best_prediction is not None
        assert occurrence.determination is not None
        assert occurrence.determination_score is not None


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

        delete_empty_events()

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
            taxon.update_parents()
            self._test_parents_json(taxon)

    def test_update_all_parents(self):
        from ami.main.models import Taxon

        Taxon.objects.update_all_parents()

        for taxon in Taxon.objects.exclude(parent=None):
            self._test_parents_json(taxon)

    def _test_parents_json(self, taxon):
        from ami.main.models import TaxonParent

        # Ensure all taxon have parents_json populated
        self.assertGreater(
            len(taxon.parents_json),
            0,
            f"Taxon {taxon} has no parents_json, even though it has the parent {taxon.parent}",
        )

        for parent_taxon in taxon.parents_json:
            # Ensure all parents_json are TaxonParent objects
            self.assertIsInstance(parent_taxon, TaxonParent)

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
        print(taxon, taxon.parent, taxon.parents_json)
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
            response = self.client.get(f"/api/v2/occurrences/?project={project.pk}")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["count"], Occurrence.objects.filter(project=project).count())

    def test_taxa_list(self):
        from ami.main.models import Taxon

        response = self.client.get("/api/v2/taxa/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], Taxon.objects.count())

    def _test_taxa_for_project(self, project: Project):
        """
        Ensure the annotation counts are specific to each project, not global counts
        of occurrences and detections.
        """
        from ami.main.models import Taxon

        response = self.client.get(f"/api/v2/taxa/?project={project.pk}")
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
        )
        self.factory = APIRequestFactory()
        self.client.force_authenticate(user=self.user)
        return super().setUp()

    def test_identification(self):
        from ami.main.models import Identification, Taxon

        """
        Post a new identification suggestion and check that it changed the occurrence's determination.
        """

        suggest_id_endpoint = "/api/v2/identifications/"
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
