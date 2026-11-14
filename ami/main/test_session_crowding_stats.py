"""How crowded a session's captures got: detections-per-capture distribution and histogram."""

import datetime

from rest_framework import status
from rest_framework.test import APITestCase

from ami.main.models import Detection, Event, SourceImage, Taxon, update_detection_counts
from ami.tests.fixtures.main import create_captures, create_taxa, setup_test_project
from ami.users.models import User

HISTOGRAM_TITLE = "Captures by number of detections"


def _add_occurrence(capture: SourceImage, taxon: Taxon, score: float):
    """One detection in ``capture`` classified as ``taxon``, with its own occurrence."""
    detection = Detection.objects.create(source_image=capture, timestamp=capture.timestamp, bbox=[0.1, 0.1, 0.2, 0.2])
    detection.classifications.create(taxon=taxon, score=score, timestamp=datetime.datetime.now())
    return detection.associate_new_occurrence()


class TestEventCrowdingStats(APITestCase):
    """One session of three captures: capture 1 has three high-score detections, capture 2
    has five low-score detections (below the project threshold, so its cached count is 0)
    and capture 3 has one high-score detection. Per-capture counts are therefore [3, 0, 1].
    """

    def setUp(self):
        self.project, self.deployment = setup_test_project(reuse=False)
        self.project.default_filters_score_threshold = 0.5
        self.project.save()
        create_taxa(self.project)
        taxon_a, taxon_b = Taxon.objects.filter(name__in=["Vanessa cardui", "Vanessa atalanta"]).order_by("name")
        create_captures(deployment=self.deployment, num_nights=1, images_per_night=3)
        self.event = Event.objects.get(deployment=self.deployment)
        self.c1, self.c2, self.c3 = self.event.captures.order_by("timestamp")

        for _ in range(3):
            _add_occurrence(self.c1, taxon_a, score=0.9)
        for _ in range(5):
            _add_occurrence(self.c2, taxon_a, score=0.1)
        _add_occurrence(self.c3, taxon_b, score=0.9)
        update_detection_counts(qs=SourceImage.objects.filter(deployment=self.deployment), project=self.project)

        self.user = User.objects.create_user(email="crowding@insectai.org", is_superuser=True)
        self.client.force_authenticate(user=self.user)

    def _get_event(self) -> dict:
        res = self.client.get(f"/api/v2/events/{self.event.pk}/?project_id={self.project.pk}")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        return res.json()

    def test_stats_describe_the_detections_per_capture_distribution(self):
        stats = self._get_event()["stats"]
        self.assertEqual(stats["captures_count"], 3)
        self.assertEqual(stats["detections_min_count"], 0)
        self.assertEqual(stats["detections_max_count"], 3)
        self.assertEqual(stats["detections_q1_count"], 0.5)
        self.assertEqual(stats["detections_median_count"], 1.0)
        self.assertEqual(stats["detections_q3_count"], 2.0)
        self.assertEqual(stats["busiest_capture"]["id"], self.c1.pk)
        self.assertEqual(stats["busiest_capture"]["detections_count"], 3)

    def test_stats_skip_captures_without_a_cached_count(self):
        SourceImage.objects.filter(pk=self.c1.pk).update(detections_count=None)
        stats = self._get_event()["stats"]
        self.assertEqual(stats["captures_count"], 2)
        self.assertEqual(stats["detections_max_count"], 1)
        self.assertEqual(stats["busiest_capture"]["id"], self.c3.pk)

    def test_stats_are_empty_for_a_session_without_counts(self):
        self.event.captures.update(detections_count=None)
        stats = self._get_event()["stats"]
        self.assertEqual(stats["captures_count"], 0)
        self.assertIsNone(stats["detections_max_count"])
        self.assertIsNone(stats["busiest_capture"])

    def test_histogram_has_a_bin_for_every_count_up_to_the_busiest_capture(self):
        plots = self._get_event()["summary_data"]
        histogram = next(plot for plot in plots if plot["title"] == HISTOGRAM_TITLE)
        self.assertEqual(histogram["data"], {"x": [0, 1, 2, 3], "y": [1, 1, 0, 1]})
