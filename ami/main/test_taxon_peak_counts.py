"""Where each taxon peaked: the session with the most occurrences and the capture with the
most detections."""

import datetime

from cachalot.api import cachalot_disabled
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework import status
from rest_framework.test import APITestCase

from ami.main.models import Detection, Event, SourceImage, SourceImageCollection, Taxon
from ami.tests.fixtures.main import create_captures, create_taxa, setup_test_project
from ami.users.models import User


def _add_occurrence(capture: SourceImage, taxon: Taxon, score: float):
    """One detection in ``capture`` classified as ``taxon``, with its own occurrence."""
    detection = Detection.objects.create(source_image=capture, timestamp=capture.timestamp, bbox=[0.1, 0.1, 0.2, 0.2])
    detection.classifications.create(taxon=taxon, score=score, timestamp=datetime.datetime.now())
    return detection.associate_new_occurrence()


class TestTaxonPeakCounts(APITestCase):
    """Two sessions of three captures with a known detection layout.

    Session 1: capture 1 has three high-score detections of taxon A, capture 2 has five
    low-score detections of A (below the project threshold), capture 3 has one of taxon B.
    Session 2: four high-score detections of A spread over its captures (two in capture 4),
    plus one of taxon C. So A peaks per session in session 2 (4 occurrences) but per capture
    in capture 1 (3 detections), and the low-score captures only count once default filters
    are bypassed.
    """

    def setUp(self):
        self.project, self.deployment = setup_test_project(reuse=False)
        self.project.default_filters_score_threshold = 0.5
        self.project.save()
        create_taxa(self.project)
        self.taxon_a, self.taxon_b, self.taxon_c = Taxon.objects.filter(
            name__in=["Vanessa cardui", "Vanessa atalanta", "Vanessa itea"]
        ).order_by("name")
        create_captures(deployment=self.deployment, num_nights=2, images_per_night=3)
        self.event_1, self.event_2 = Event.objects.filter(deployment=self.deployment).order_by("start")
        self.c1, self.c2, self.c3 = self.event_1.captures.order_by("timestamp")
        self.c4, self.c5, self.c6 = self.event_2.captures.order_by("timestamp")

        for _ in range(3):
            _add_occurrence(self.c1, self.taxon_a, score=0.9)
        for _ in range(5):
            _add_occurrence(self.c2, self.taxon_a, score=0.1)
        _add_occurrence(self.c3, self.taxon_b, score=0.9)
        for capture in (self.c4, self.c4, self.c5, self.c6):
            _add_occurrence(capture, self.taxon_a, score=0.9)
        _add_occurrence(self.c6, self.taxon_c, score=0.9)

        self.user = User.objects.create_user(email="peaks@insectai.org", is_superuser=True)
        self.client.force_authenticate(user=self.user)

    def _list(self, params: str = "") -> dict[int, dict]:
        res = self.client.get(f"/api/v2/taxa/?project_id={self.project.pk}&{params}")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        return {row["id"]: row for row in res.json()["results"]}

    def test_list_leaves_peaks_null_unless_requested(self):
        row = self._list()[self.taxon_a.pk]
        self.assertIsNone(row["peak_event"])
        self.assertIsNone(row["peak_capture"])

    def test_list_reports_the_busiest_session_and_capture_per_taxon(self):
        rows = self._list("with_peak_counts=true")
        self.assertEqual(rows[self.taxon_a.pk]["peak_event"], {"id": self.event_2.pk, "occurrences_count": 4})
        self.assertEqual(
            rows[self.taxon_a.pk]["peak_capture"],
            {"id": self.c1.pk, "event_id": self.event_1.pk, "detections_count": 3},
        )
        self.assertEqual(rows[self.taxon_b.pk]["peak_event"], {"id": self.event_1.pk, "occurrences_count": 1})
        self.assertEqual(
            rows[self.taxon_b.pk]["peak_capture"],
            {"id": self.c3.pk, "event_id": self.event_1.pk, "detections_count": 1},
        )

    def test_peaks_follow_the_default_filters(self):
        # Bypassing the score threshold lets the five low-score detections in capture 2 win.
        row = self._list("with_peak_counts=true&apply_defaults=false")[self.taxon_a.pk]
        self.assertEqual(row["peak_event"], {"id": self.event_1.pk, "occurrences_count": 8})
        self.assertEqual(row["peak_capture"], {"id": self.c2.pk, "event_id": self.event_1.pk, "detections_count": 5})

    def test_peaks_are_skipped_under_a_collection_filter(self):
        collection = SourceImageCollection.objects.create(project=self.project, name="All captures")
        collection.images.set(SourceImage.objects.filter(deployment=self.deployment))
        row = self._list(f"with_peak_counts=true&collection={collection.pk}")[self.taxon_a.pk]
        self.assertIsNone(row["peak_event"])
        self.assertIsNone(row["peak_capture"])

    def test_invalid_param_is_a_400(self):
        res = self.client.get(f"/api/v2/taxa/?project_id={self.project.pk}&with_peak_counts=abc")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_detail_always_includes_peaks(self):
        res = self.client.get(f"/api/v2/taxa/{self.taxon_a.pk}/?project_id={self.project.pk}")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.json()["peak_event"], {"id": self.event_2.pk, "occurrences_count": 4})
        self.assertEqual(
            res.json()["peak_capture"], {"id": self.c1.pk, "event_id": self.event_1.pk, "detections_count": 3}
        )

    def test_peak_query_count_does_not_grow_with_page_size(self):
        # Both peaks are annotations on the page query, so a one-row page and a three-row
        # page must issue exactly the same number of queries. Cachalot is disabled so the
        # second measurement is not served from the first one's cache; assertions stay
        # outside the context so a failure cannot leave it disabled for later tests.
        def count_queries(limit: int) -> tuple[int, int]:
            with CaptureQueriesContext(connection) as ctx:
                rows = self._list(f"with_peak_counts=true&limit={limit}")
            return len(rows), len(ctx.captured_queries)

        with cachalot_disabled():
            small_rows, small = count_queries(limit=1)
            large_rows, large = count_queries(limit=3)
        self.assertEqual((small_rows, large_rows), (1, 3))
        self.assertEqual(small, large, f"Query count scaled with page size: {small} -> {large}")
