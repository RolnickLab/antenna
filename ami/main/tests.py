import datetime

from django.db import connection
from django.test import TestCase
from rich import print

from ami.main.models import (
    Deployment,
    Event,
    Occurrence,
    Project,
    SourceImage,
    TaxaList,
    Taxon,
    group_images_into_events,
)


def setup_test_project() -> tuple[Project, Deployment]:
    project, _ = Project.objects.get_or_create(name="Test Project")
    deployment, _ = Deployment.objects.get_or_create(project=project, name="Test Deployment")
    return project, deployment


def create_captures(
    deployment: Deployment, num_nights: int = 3, images_per_night: int = 3, interval_minutes: int = 10
):
    # Create some images over a few monitoring nights
    first_night = datetime.datetime.now()

    created = []
    for night in range(num_nights):
        for i in range(images_per_night):
            img = SourceImage.objects.create(
                deployment=deployment,
                timestamp=first_night + datetime.timedelta(days=night, minutes=i * interval_minutes),
                path=f"test/{night}_{i}.jpg",
            )
            created.append(img)

    return created


def create_taxa(project: Project) -> TaxaList:
    taxa_list = TaxaList.objects.create(project=project, name="Test Taxa List")
    parent_taxon = Taxon.objects.create(taxa_list=taxa_list, name="Lepidoptera", rank="order")
    family_taxon = Taxon.objects.create(taxa_list=taxa_list, name="Nymphalidae", parent=parent_taxon, rank="family")
    genus_taxon = Taxon.objects.create(taxa_list=taxa_list, name="Vanessa", parent=family_taxon, rank="genus")
    for species in ["Vanessa itea", "Vanessa cardui", "Vanessa atalanta"]:
        Taxon.objects.create(taxa_list=taxa_list, name=species, parent=genus_taxon, rank="species")
    return taxa_list


def create_occurrences(
    deployment: Deployment,
    num: int = 12,
):
    event = Event.objects.filter(deployment=deployment).first()
    if not event:
        raise ValueError("No events found for deployment")

    for i in range(num):
        Occurrence.objects.create(
            project=deployment.project,
            deployment=deployment,
            determination=Taxon.objects.order_by("?").first(),
            event=event,
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
        create_occurrences(deployment=self.deployment)

        return super().setUp()

    def test_initial_project(self):
        assert self.deployment.project == self.project_one
        assert self.deployment.captures.first().project == self.project_one
        assert self.deployment.events.first().project == self.project_one
        assert self.deployment.occurrences.first().project == self.project_one

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
