"""An occurrence's history: algorithm results and reviews, and the endpoint that reads them."""

from django.test import TestCase

from ami.main import tests as main_tests
from ami.main.models import Occurrence, OccurrenceHistoryRecord
from ami.tests.fixtures.main import setup_test_project


class OccurrenceHistoryPayloadTestCase(TestCase):
    """A history payload always fits the schema for its kind and subtype, however it is written."""

    def setUp(self) -> None:
        self.project, self.deployment = setup_test_project(reuse=False)
        self.occurrence = Occurrence.objects.create(project=self.project, deployment=self.deployment)

    def _size_filter(self, payload: dict) -> OccurrenceHistoryRecord:
        return OccurrenceHistoryRecord.build(
            occurrence_id=self.occurrence.pk,
            kind=OccurrenceHistoryRecord.Kind.ALGORITHM_RESULT,
            subtype="size_filter",
            payload=payload,
        )

    def test_a_valid_payload_is_stored_as_given(self):
        record = self._size_filter({"size_threshold": 0.001, "detection_ids": [3, 4]})
        record.save()
        record.refresh_from_db()
        self.assertEqual(record.payload["detection_ids"], [3, 4])
        self.assertIsNone(record.payload["taxon_after_id"])

    def test_a_payload_that_does_not_fit_its_schema_is_refused(self):
        for label, payload in (
            ("missing field", {"size_threshold": 0.001}),
            ("wrong type", {"size_threshold": "small", "detection_ids": []}),
            ("unknown field", {"size_threshold": 0.001, "detection_ids": [], "note": "x"}),
        ):
            with self.subTest(label), self.assertRaises(ValueError):
                self._size_filter(payload)

    def test_save_validates_too_and_an_unknown_subtype_is_refused(self):
        record = OccurrenceHistoryRecord(
            occurrence=self.occurrence,
            kind=OccurrenceHistoryRecord.Kind.ALGORITHM_RESULT,
            subtype="size_filter",
            payload={"size_threshold": 0.001},
            timestamp=self.occurrence.created_at,
        )
        with self.assertRaises(ValueError):
            record.save()
        record.subtype = "not_a_subtype"
        record.payload = {}
        with self.assertRaises(ValueError):
            record.save()
        self.assertFalse(OccurrenceHistoryRecord.objects.exists())


class TrackCompleteReviewTestCase(main_tests.TrackFixtureTestCase):
    """Confirming a track posts a review only when the confirmed set of detections differs from the last one."""

    def verify(self, occurrence: Occurrence | None = None):
        self.client.force_authenticate(user=self.curator)
        occurrence = occurrence or self.occurrence
        response = self.client.post(f"/api/v2/occurrences/{occurrence.pk}/verify-grouping/", format="json")
        self.assertEqual(response.status_code, 200, response.data)

    def reviews(self, occurrence: Occurrence | None = None):
        return OccurrenceHistoryRecord.objects.filter(
            occurrence=occurrence or self.occurrence,
            kind=OccurrenceHistoryRecord.Kind.REVIEW,
            subtype="track_complete",
        ).order_by("timestamp", "pk")

    def test_the_first_confirmation_posts_a_review_and_an_unchanged_one_does_not(self):
        self.verify()
        self.verify()

        review = self.reviews().get()
        self.assertEqual(review.user, self.curator)
        self.assertEqual(review.payload["detection_ids"], sorted(d.pk for d in self.detections))
        self.assertEqual(review.payload["frames_count"], len(self.captures))
        self.assertEqual(review.payload["first_timestamp"], self.captures[0].timestamp.isoformat())
        self.assertEqual(review.payload["last_timestamp"], self.captures[-1].timestamp.isoformat())
        self.assertEqual((review.payload["detections_added"], review.payload["detections_removed"]), ([], []))
        self.occurrence.refresh_from_db()
        self.assertEqual(self.occurrence.grouping_verified_by, self.curator)
        self.assertGreaterEqual(self.occurrence.grouping_verified_at, review.timestamp)

    def test_a_confirmation_after_an_edit_records_what_changed(self):
        self.verify()
        response = self.post("remove-detection", self.detections[-1], user=self.curator)
        self.assertEqual(response.status_code, 200, response.data)
        self.verify()

        first, second = self.reviews()
        self.assertEqual(second.payload["detections_removed"], [self.detections[-1].pk])
        self.assertEqual(second.payload["detections_added"], [])
        self.assertEqual(second.payload["frames_count"], len(self.captures) - 1)
        self.assertEqual(first.payload["detection_ids"], sorted(d.pk for d in self.detections))

    def test_merging_an_occurrence_keeps_its_reviews(self):
        other, _ = self._make_track(1, captures=self._make_captures_after(1))
        self.verify(other)
        self.client.force_authenticate(user=self.curator)
        response = self.client.post(
            f"/api/v2/occurrences/{self.occurrence.pk}/merge/", {"occurrence_ids": [other.pk]}, format="json"
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(self.reviews().count(), 1)
