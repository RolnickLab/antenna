"""An occurrence's history: algorithm results and reviews, and the endpoint that reads them."""

import datetime

from django.test import TestCase

from ami.main import tests as main_tests
from ami.main.models import Classification, Identification, Occurrence, OccurrenceHistoryRecord, Taxon
from ami.ml.models import Algorithm
from ami.tests.fixtures.main import setup_test_project
from ami.users.models import User
from ami.users.roles import MLDataManager

# Measured: two savepoints, the project, the occurrence, then history records, their taxa,
# identifications and predictions.
HISTORY_QUERIES = 8


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
    """Confirming a track posts a review unless the same person re-confirms a still-confirmed, unchanged set."""

    def verify(self, occurrence: Occurrence | None = None, user: User | None = None):
        self.client.force_authenticate(user=user or self.curator)
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

    def test_a_confirmation_after_it_was_withdrawn_or_by_someone_else_posts_a_review(self):
        self.verify()
        self.client.force_authenticate(user=self.curator)
        response = self.client.post(f"/api/v2/occurrences/{self.occurrence.pk}/unverify-grouping/", format="json")
        self.assertEqual(response.status_code, 200, response.data)
        self.verify()
        other_curator = User.objects.create_user(email="second-curator@insectai.org")  # type: ignore
        MLDataManager.assign_user(other_curator, self.project)
        self.verify(user=other_curator)

        reviews = list(self.reviews())
        self.assertEqual([r.user for r in reviews], [self.curator, self.curator, other_curator])
        self.assertTrue(all(r.payload["detections_added"] == [] for r in reviews))
        self.occurrence.refresh_from_db()
        self.assertEqual(self.occurrence.grouping_verified_at, reviews[-1].timestamp)

    def test_a_confirmation_after_a_merge_compares_with_this_occurrences_own_review(self):
        other, other_detections = self._make_track(1, captures=self._make_captures_after(1))
        self.verify()
        self.verify(other)
        self.client.force_authenticate(user=self.curator)
        response = self.client.post(
            f"/api/v2/occurrences/{self.occurrence.pk}/merge/", {"occurrence_ids": [other.pk]}, format="json"
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.verify()

        latest = self.reviews().last()
        self.assertEqual(latest.payload["detections_added"], [d.pk for d in other_detections])
        self.assertEqual(latest.payload["detections_removed"], [])

    def test_merging_an_occurrence_keeps_its_reviews(self):
        other, _ = self._make_track(1, captures=self._make_captures_after(1))
        self.verify(other)
        self.client.force_authenticate(user=self.curator)
        response = self.client.post(
            f"/api/v2/occurrences/{self.occurrence.pk}/merge/", {"occurrence_ids": [other.pk]}, format="json"
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(self.reviews().count(), 1)


class OccurrenceHistoryEndpointTestCase(main_tests.TrackFixtureTestCase):
    """GET /occurrences/{id}/history/ merges records, identifications and predictions, newest first."""

    def setUp(self) -> None:
        super().setUp()
        self.tracking = Algorithm.objects.create(name="Occurrence Tracking", key="tracking-history-test")
        self.other_taxon = Taxon.objects.filter(projects=self.project).exclude(pk=self.taxon.pk).first()
        self.superuser = User.objects.create_superuser(email="history-super@insectai.org")  # type: ignore
        self.outsider = User.objects.create_user(email="history-outsider@insectai.org")  # type: ignore

    def url(self, occurrence: Occurrence | None = None) -> str:
        return f"/api/v2/occurrences/{(occurrence or self.occurrence).pk}/history/?project_id={self.project.pk}"

    def _add_history(self, start: datetime.datetime, rounds: int = 1) -> None:
        """Per round: a tracking result, a folded tracking prediction, an identification and a review."""
        for i in range(rounds):
            at = start + datetime.timedelta(hours=4 * i)
            OccurrenceHistoryRecord.build(
                occurrence_id=self.occurrence.pk,
                kind=OccurrenceHistoryRecord.Kind.ALGORITHM_RESULT,
                subtype="tracking",
                payload={
                    "detections_count": 4,
                    "frames_linked": 3,
                    "taxon_before_id": self.other_taxon.pk,
                    "taxon_after_id": self.taxon.pk,
                },
                timestamp=at,
                algorithm=self.tracking,
            ).save()
            Classification.objects.create(
                detection=self.detections[0], taxon=self.taxon, score=0.1, algorithm=self.tracking, timestamp=at
            )
            identification = Identification.objects.create(
                occurrence=self.occurrence, user=self.reader, taxon=self.other_taxon, comment=f"round {i}"
            )
            Identification.objects.filter(pk=identification.pk).update(created_at=at + datetime.timedelta(hours=1))
            OccurrenceHistoryRecord.build(
                occurrence_id=self.occurrence.pk,
                kind=OccurrenceHistoryRecord.Kind.REVIEW,
                subtype="track_complete",
                payload={"detection_ids": [d.pk for d in self.detections], "frames_count": 4},
                timestamp=at + datetime.timedelta(hours=2),
                user=self.curator,
            ).save()

    def test_entries_are_merged_newest_first_and_a_folded_prediction_is_left_out(self):
        # Predictions are stamped with created_at (now), so the history rows sit in the past.
        self._add_history(datetime.datetime.now() - datetime.timedelta(days=2))
        self.client.force_authenticate(user=self.reader)
        response = self.client.get(self.url())
        self.assertEqual(response.status_code, 200, response.data)

        types = [entry["type"] for entry in response.data]
        self.assertEqual(types[-3:], ["review", "identification", "algorithm_result"])
        self.assertEqual(set(types[:-3]), {"prediction"})
        self.assertEqual(len(types[:-3]), len(self.detections))
        self.assertTrue(all(entry["algorithm"] is None for entry in response.data[:-3]))
        timestamps = [entry["timestamp"] for entry in response.data]
        self.assertEqual(timestamps, sorted(timestamps, reverse=True))

        review, identification, result = response.data[-3:]
        self.assertEqual(set(review["user"]), {"id", "name", "image"})
        self.assertEqual(review["user"]["id"], self.curator.pk)
        self.assertEqual(identification["user"]["id"], self.reader.pk)
        self.assertEqual(identification["taxon"]["id"], self.other_taxon.pk)
        self.assertEqual(identification["payload"]["comment"], "round 0")
        self.assertEqual(result["subtype"], "tracking")
        self.assertEqual(result["algorithm"]["key"], self.tracking.key)
        self.assertEqual(result["taxon"]["id"], self.taxon.pk)
        self.assertEqual(result["taxon_before"]["id"], self.other_taxon.pk)
        self.assertNotIn("email", str(response.data))

    def test_query_count_does_not_grow_with_the_number_of_entries(self):
        self.client.force_authenticate(user=self.reader)
        now = datetime.datetime.now()
        for rounds, total in ((1, 1), (2, 3)):
            self._add_history(now - datetime.timedelta(days=3 * total), rounds=rounds)
            with self.subTest(rounds=total), main_tests.cachalot_disabled():
                with self.assertNumQueries(HISTORY_QUERIES):
                    response = self.client.get(self.url())
                self.assertEqual(response.status_code, 200)
                self.assertEqual(len(response.data), 3 * total + len(self.detections))

    def test_visible_to_whoever_can_open_the_occurrence(self):
        """Member, non-member, anonymous and superuser, on a public and on a draft project."""
        expected = {
            False: {"member": 200, "non-member": 200, "anonymous": 200, "superuser": 200},
            True: {"member": 200, "non-member": 404, "anonymous": 404, "superuser": 200},
        }
        users = {"member": self.reader, "non-member": self.outsider, "anonymous": None, "superuser": self.superuser}
        for draft, codes in expected.items():
            self.project.draft = draft
            self.project.save()
            for label, user in users.items():
                with self.subTest(draft=draft, user=label):
                    self.client.force_authenticate(user=user)
                    detail = self.client.get(f"/api/v2/occurrences/{self.occurrence.pk}/?project_id={self.project.pk}")
                    history = self.client.get(self.url())
                    self.assertEqual(history.status_code, codes[label])
                    self.assertEqual(history.status_code, detail.status_code)

    def test_an_occurrence_the_default_filters_hide_still_has_a_history(self):
        """The session view lists occurrences with the default filters off, so their history must open too."""
        self.project.default_filters_score_threshold = 0.95
        self.project.save()
        self.client.force_authenticate(user=self.reader)
        detail = self.client.get(f"/api/v2/occurrences/{self.occurrence.pk}/?project_id={self.project.pk}")
        self.assertEqual(detail.status_code, 404)
        self.assertEqual(self.client.get(self.url()).status_code, 200)
