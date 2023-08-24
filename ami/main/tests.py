import datetime

from django.db import connection
from django.test import TestCase
from rich import print

from ami.main.models import Deployment, Event, Project, SourceImage, group_images_into_events


class TestImageGrouping(TestCase):
    def setUp(self) -> None:
        print(f"Currently active database: {connection.settings_dict}")
        self.project, _ = Project.objects.get_or_create(name="Test Project")
        self.deployment, _ = Deployment.objects.get_or_create(project=self.project, name="Test Deployment")
        return super().setUp()

    def create_captures(
        self, deployment: Deployment, num_nights: int = 3, images_per_night: int = 3, interval_minutes: int = 10
    ):
        # Create some images over a few monitoring nights
        first_night = datetime.datetime.now()

        for night in range(num_nights):
            for i in range(images_per_night):
                SourceImage.objects.create(
                    deployment=deployment,
                    timestamp=first_night + datetime.timedelta(days=night, minutes=i * interval_minutes),
                    path=f"test/{night}_{i}.jpg",
                )

    def test_grouping(self):
        num_nights = 3
        images_per_night = 3

        self.create_captures(
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

        self.create_captures(deployment=self.deployment)
        events = group_images_into_events(deployment=self.deployment)

        for event in events:
            event.captures.all().delete()

        delete_empty_events()

        remaining_events = Event.objects.filter(pk__in=[event.pk for event in events])

        assert remaining_events.count() == 0

    def test_setting_image_dimesions(self):
        from ami.main.models import set_dimensions_from_first_image

        image_width, image_height = 100, 100

        self.create_captures(deployment=self.deployment)
        events = group_images_into_events(deployment=self.deployment)

        for event in events:
            first_image = event.captures.first()
            assert first_image is not None
            first_image.width, first_image.height = image_width, image_height
            first_image.save()
            set_dimensions_from_first_image(event=event)

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
