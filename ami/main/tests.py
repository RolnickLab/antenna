import datetime
from unittest import TestCase

from ami.main.models import Deployment, Project, SourceImage, group_images_into_events


class TestImageGrouping(TestCase):
    def setUp(self) -> None:
        # print(f"Currently active database: {connection.settings_dict}")
        self.project, _ = Project.objects.get_or_create(name="Test Project")
        self.deployment, _ = Deployment.objects.get_or_create(project=self.project, name="Test Deployment")
        return super().setUp()

    def test_grouping(self):
        # Create some images over a few nights
        images = []
        first_night = datetime.datetime.now()
        SourceImage.objects.filter(deployment=self.deployment).delete()

        num_nights = 3
        images_per_night = 3
        for night in range(num_nights):
            for i in range(images_per_night):
                images.append(
                    SourceImage.objects.create(
                        deployment=self.deployment,
                        timestamp=first_night + datetime.timedelta(days=night, minutes=i * 10),
                    )
                )

        events = group_images_into_events(
            deployment=self.deployment,
            max_time_gap=datetime.timedelta(hours=2),
        )

        assert len(events) == num_nights
        for event in events:
            assert event.captures.count() == images_per_night
