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
