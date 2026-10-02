"""Algorithm results, validation reviews, and the occurrence history endpoint that reads them."""

import datetime

from django.db import IntegrityError, transaction
from django.test import TestCase

from ami.main import tests as main_tests
from ami.main.models import (
    AlgorithmResult,
    Classification,
    Detection,
    Identification,
    Occurrence,
    Project,
    SourceImage,
    Taxon,
    ValidationReview,
)
from ami.main.models_future.history import latest_track_complete_review
from ami.main.models_future.project_scope import ProjectScopeError, project_mismatch_counts
from ami.main.models_future.tracks import verify_grouping
from ami.ml.models import Algorithm
from ami.tests.fixtures.main import create_captures, setup_test_project
from ami.users.models import User
from ami.users.roles import Identifier, MLDataManager

# Measured: two savepoints, the project, the occurrence, then results, their taxa, reviews,
# identifications and predictions.
HISTORY_QUERIES = 9

SIZE_FILTER = AlgorithmResult.Kind.SIZE_FILTER
GROUPING = ValidationReview.Aspect.GROUPING


class AlgorithmResultTestCase(TestCase):
    """A result's data fits its kind, its project is its target's, and a new result replaces the current one."""

    def setUp(self) -> None:
        self.project, self.deployment = setup_test_project(reuse=False)
        self.occurrence = Occurrence.objects.create(project=self.project, deployment=self.deployment)
        self.algorithm = Algorithm.objects.create(name="Size filter", key="size-filter-result-test")

    def _size_filter(self, data: dict | None, **fields) -> AlgorithmResult:
        fields.setdefault("occurrence", self.occurrence)
        return AlgorithmResult(algorithm=self.algorithm, kind=SIZE_FILTER, data=data, **fields)

    def test_data_that_does_not_fit_its_kind_is_refused_on_every_write_path(self):
        for label, data in (
            ("missing field", {"size_threshold": 0.001}),
            ("wrong type", {"size_threshold": "small", "detection_ids": []}),
            ("unknown field", {"size_threshold": 0.001, "detection_ids": [], "note": "x"}),
        ):
            with self.subTest(label):
                with self.assertRaises(ValueError):
                    self._size_filter(data).save()
                with self.assertRaises(ValueError):
                    AlgorithmResult.objects.record_many([self._size_filter(data)])
        with self.assertRaises(ValueError):
            AlgorithmResult.objects.record(
                occurrence=self.occurrence, algorithm=self.algorithm, kind="unregistered", data={}
            )
        self.assertFalse(AlgorithmResult.objects.exists())

    def test_a_kind_without_a_schema_can_carry_a_value(self):
        result = AlgorithmResult.objects.record(
            occurrence=self.occurrence, algorithm=self.algorithm, kind="ood_score", value=0.8
        )
        self.assertEqual((result.project_id, result.value, result.data), (self.project.pk, 0.8, None))

    def test_a_new_result_becomes_current_and_the_earlier_one_stays_as_history(self):
        first = AlgorithmResult.objects.record(
            occurrence=self.occurrence,
            algorithm=self.algorithm,
            kind=SIZE_FILTER,
            data={"size_threshold": 0.01, "detection_ids": [1]},
        )
        other_target = Occurrence.objects.create(project=self.project, deployment=self.deployment)
        second, untouched = AlgorithmResult.objects.record_many(
            [
                self._size_filter({"size_threshold": 0.02, "detection_ids": [1]}),
                self._size_filter({"size_threshold": 0.02, "detection_ids": [2]}, occurrence=other_target),
            ]
        )
        first.refresh_from_db()
        self.assertFalse(first.is_current)
        self.assertTrue(second.is_current and untouched.is_current)
        self.assertEqual(AlgorithmResult.objects.for_occurrence(self.occurrence).count(), 2)
        self.assertEqual(AlgorithmResult.objects.for_occurrence(self.occurrence).current().get().pk, second.pk)

    def test_the_database_holds_one_current_result_per_target_algorithm_and_kind(self):
        self._size_filter({"size_threshold": 0.01, "detection_ids": []}).save()
        with transaction.atomic(), self.assertRaises(IntegrityError):
            self._size_filter({"size_threshold": 0.02, "detection_ids": []}).save()

    def test_a_result_needs_exactly_one_target(self):
        create_captures(deployment=self.deployment, num_nights=1, images_per_night=1)
        event = SourceImage.objects.filter(deployment=self.deployment).get().event
        with self.assertRaises(ProjectScopeError):
            self._size_filter({"size_threshold": 0.01, "detection_ids": []}, event=event).save()
        result = self._size_filter({"size_threshold": 0.01, "detection_ids": []}, occurrence=None, event=event)
        result.save()
        self.assertEqual(result.project_id, self.project.pk)
        with transaction.atomic(), self.assertRaises(IntegrityError):
            AlgorithmResult.objects.filter(pk=result.pk).update(occurrence=self.occurrence)

    def test_project_comes_from_the_target_and_falls_back_to_its_station(self):
        other = Project.objects.create(name="Another project")
        Occurrence.objects.filter(pk=self.occurrence.pk).update(project=None)
        result = self._size_filter({"size_threshold": 0.01, "detection_ids": []}, project=other)
        result.save()
        self.assertEqual(result.project_id, self.project.pk)
        self.assertEqual(project_mismatch_counts()["main.AlgorithmResult"], 0)

        Occurrence.objects.filter(pk=self.occurrence.pk).update(project=other)
        self.assertEqual(project_mismatch_counts()["main.AlgorithmResult"], 1)


class ValidationReviewTestCase(TestCase):
    def setUp(self) -> None:
        self.project, self.deployment = setup_test_project(reuse=False)
        self.occurrence = Occurrence.objects.create(project=self.project, deployment=self.deployment)
        self.user = User.objects.create_user(email="review-model@insectai.org")  # type: ignore

    def test_a_comment_has_no_verdict_and_every_other_aspect_needs_one(self):
        for label, fields in (
            ("comment with a verdict", {"aspect": "comment", "comment": "x", "verdict": "confirmed"}),
            ("empty comment", {"aspect": "comment", "comment": ""}),
            ("grouping without a verdict", {"aspect": "bbox"}),
        ):
            with self.subTest(label), transaction.atomic(), self.assertRaises(IntegrityError):
                ValidationReview.objects.create(occurrence=self.occurrence, user=self.user, **fields)

    def test_one_current_review_per_person_target_and_aspect_but_any_number_of_comments(self):
        for _ in range(2):
            ValidationReview.objects.create(occurrence=self.occurrence, user=self.user, aspect="comment", comment="x")
        ValidationReview.objects.create(occurrence=self.occurrence, user=self.user, aspect="bbox", verdict="confirmed")
        with transaction.atomic(), self.assertRaises(IntegrityError):
            ValidationReview.objects.create(
                occurrence=self.occurrence, user=self.user, aspect="bbox", verdict="rejected"
            )

    def test_a_detection_review_takes_its_captures_project(self):
        create_captures(deployment=self.deployment, num_nights=1, images_per_night=1)
        capture = SourceImage.objects.filter(deployment=self.deployment).get()
        detection = Detection.objects.create(source_image=capture, bbox=[0, 0, 1, 1])
        review = ValidationReview.objects.create(
            detection=detection, user=self.user, aspect="bbox", verdict="rejected"
        )
        self.assertEqual(review.project_id, capture.project_id)
        self.assertEqual(project_mismatch_counts()["main.ValidationReview"], 0)


class TrackCompleteReviewTestCase(main_tests.TrackFixtureTestCase):
    """Confirming a track writes a grouping review when its detections or its confirming person changed."""

    def verify(self, occurrence: Occurrence | None = None, user: User | None = None):
        self.client.force_authenticate(user=user or self.curator)
        occurrence = occurrence or self.occurrence
        response = self.client.post(f"/api/v2/occurrences/{occurrence.pk}/verify-grouping/", format="json")
        self.assertEqual(response.status_code, 200, response.data)

    def unverify(self):
        self.client.force_authenticate(user=self.curator)
        response = self.client.post(f"/api/v2/occurrences/{self.occurrence.pk}/unverify-grouping/", format="json")
        self.assertEqual(response.status_code, 200, response.data)

    def reviews(self, occurrence: Occurrence | None = None):
        return ValidationReview.objects.filter(occurrence=occurrence or self.occurrence, aspect=GROUPING).order_by(
            "timestamp", "pk"
        )

    def test_the_first_confirmation_writes_a_review_and_an_unchanged_one_does_not(self):
        self.verify()
        self.verify()

        review = self.reviews().get()
        self.assertEqual((review.user, review.verdict), (self.curator, "confirmed"))
        self.assertTrue(review.is_current)
        self.assertFalse(review.withdrawn)
        self.assertEqual(review.project_id, self.project.pk)
        self.assertEqual(review.payload["detection_ids"], sorted(d.pk for d in self.detections))
        self.assertEqual(review.payload["frames_count"], len(self.captures))
        self.assertEqual(review.payload["first_timestamp"], self.captures[0].timestamp.isoformat())
        self.assertEqual(review.payload["last_timestamp"], self.captures[-1].timestamp.isoformat())
        self.assertEqual((review.payload["detections_added"], review.payload["detections_removed"]), ([], []))
        self.occurrence.refresh_from_db()
        self.assertEqual(self.occurrence.grouping_verified_by, self.curator)

    def test_a_replayed_confirmation_keeps_its_time_and_a_second_replay_writes_nothing(self):
        verified_at = datetime.datetime(2024, 6, 1, 23, 30)
        for _ in range(2):
            verify_grouping(self.occurrence, self.curator, timestamp=verified_at)

        review = self.reviews().get()
        self.assertEqual(review.timestamp, verified_at)
        self.occurrence.refresh_from_db()
        self.assertEqual(self.occurrence.grouping_verified_at, verified_at)
        self.assertTrue(
            ValidationReview.objects.current(aspect=GROUPING)
            .filter(occurrence=self.occurrence, user=self.curator, timestamp=verified_at)
            .exists()
        )

    def test_the_review_answers_the_current_tracking_result(self):
        tracking = Algorithm.objects.create(name="Tracking", key="tracking-review-test")
        result = AlgorithmResult.objects.record(
            occurrence=self.occurrence,
            algorithm=tracking,
            kind=AlgorithmResult.Kind.TRACKING,
            data={"detections_count": 4, "frames_linked": 3},
        )
        self.verify()
        self.assertEqual(self.reviews().get().reviewed_result, result)
        self.assertEqual(list(ValidationReview.objects.answering(result)), list(self.reviews()))

    def test_unconfirming_withdraws_the_review_and_reconfirming_writes_a_new_one(self):
        self.verify()
        self.unverify()
        withdrawn = self.reviews().get()
        self.assertTrue(withdrawn.withdrawn)
        self.assertFalse(ValidationReview.objects.current(aspect=GROUPING).exists())

        self.verify()
        first, second = self.reviews()
        self.assertEqual(first.pk, withdrawn.pk)
        self.assertFalse(first.is_current)
        self.assertTrue(second.is_current and not second.withdrawn)

    def test_a_confirmation_after_an_edit_records_what_changed(self):
        self.verify()
        self.unverify()
        response = self.post("remove-detection", self.detections[-1], user=self.curator)
        self.assertEqual(response.status_code, 200, response.data)
        self.verify()

        first, second = self.reviews()
        self.assertEqual(second.payload["detections_removed"], [self.detections[-1].pk])
        self.assertEqual(second.payload["detections_added"], [])
        self.assertEqual(second.payload["frames_count"], len(self.captures) - 1)
        self.assertEqual(first.payload["detection_ids"], sorted(d.pk for d in self.detections))

    def test_a_confirmation_by_someone_else_writes_a_review_and_both_stand(self):
        self.verify()
        other_curator = User.objects.create_user(email="second-curator@insectai.org")  # type: ignore
        MLDataManager.assign_user(other_curator, self.project)
        self.verify(user=other_curator)

        reviews = list(self.reviews())
        self.assertEqual([r.user for r in reviews], [self.curator, other_curator])
        self.assertTrue(all(r.is_current for r in reviews))
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

        latest = latest_track_complete_review(self.occurrence)
        self.assertEqual(latest.payload["detections_added"], [d.pk for d in other_detections])
        self.assertEqual(latest.payload["detections_removed"], [])
        self.assertEqual(self.reviews().filter(is_current=True).get().pk, latest.pk)

    def test_merging_an_occurrence_keeps_its_reviews_and_comments(self):
        other, _ = self._make_track(1, captures=self._make_captures_after(1))
        self.verify(other)
        comment = ValidationReview.objects.create(occurrence=other, user=self.reader, aspect="comment", comment="x")
        self.client.force_authenticate(user=self.curator)
        response = self.client.post(
            f"/api/v2/occurrences/{self.occurrence.pk}/merge/", {"occurrence_ids": [other.pk]}, format="json"
        )
        self.assertEqual(response.status_code, 200, response.data)
        moved = self.reviews().get()
        self.assertFalse(moved.is_current)
        comment.refresh_from_db()
        self.assertEqual((comment.occurrence_id, comment.is_current), (self.occurrence.pk, True))

    def edited_since_verified(self) -> bool:
        self.client.force_authenticate(user=self.curator)
        response = self.client.get(f"/api/v2/occurrences/{self.occurrence.pk}/?project_id={self.project.pk}")
        self.assertEqual(response.status_code, 200, response.data)
        return response.data["grouping_edited_since_verified"]

    def test_the_detail_says_whether_the_detections_changed_since_the_last_confirmation(self):
        self.assertFalse(self.edited_since_verified())
        self.verify()
        self.assertFalse(self.edited_since_verified())
        response = self.post("remove-detection", self.detections[-1], user=self.curator)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertTrue(self.edited_since_verified())

    def test_a_null_marker_on_the_occurrence_is_not_an_edit(self):
        self.verify()
        self.unverify()
        Detection.objects.create(source_image=self.captures[0], occurrence=self.occurrence, bbox=None)
        self.assertFalse(self.edited_since_verified())


class OccurrenceHistoryEndpointTestCase(main_tests.TrackFixtureTestCase):
    """GET /occurrences/{id}/history/ merges results, reviews, identifications and predictions, newest first."""

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
            AlgorithmResult.objects.record(
                occurrence=self.occurrence,
                algorithm=self.tracking,
                kind=AlgorithmResult.Kind.TRACKING,
                data={
                    "detections_count": 4,
                    "frames_linked": 3,
                    "taxon_before_id": self.other_taxon.pk,
                    "taxon_after_id": self.taxon.pk,
                },
                timestamp=at,
            )
            Classification.objects.create(
                detection=self.detections[0], taxon=self.taxon, score=0.1, algorithm=self.tracking, timestamp=at
            )
            identification = Identification.objects.create(
                occurrence=self.occurrence, user=self.reader, taxon=self.other_taxon, comment=f"round {i}"
            )
            Identification.objects.filter(pk=identification.pk).update(created_at=at + datetime.timedelta(hours=1))
            ValidationReview.objects.create(
                occurrence=self.occurrence,
                user=self.curator,
                aspect="comment",
                comment=f"note {i}",
                timestamp=at + datetime.timedelta(hours=2),
            )

    def test_entries_are_merged_newest_first_and_a_folded_prediction_is_left_out(self):
        # Predictions are stamped with created_at (now), so the history rows sit in the past.
        self._add_history(datetime.datetime.now() - datetime.timedelta(days=2))
        self.client.force_authenticate(user=self.reader)
        response = self.client.get(self.url())
        self.assertEqual(response.status_code, 200, response.data)

        types = [entry["type"] for entry in response.data]
        self.assertEqual(types[-3:], ["review", "identification", "algorithm_result"])
        self.assertEqual(set(types[:-3]), {"prediction"})
        # The fixture's detections share one tied top prediction, so it is shown once.
        self.assertEqual(len(types[:-3]), 1)
        self.assertIsNone(response.data[0]["algorithm"])
        timestamps = [entry["timestamp"] for entry in response.data]
        self.assertEqual(timestamps, sorted(timestamps, reverse=True))

        review, identification, result = response.data[-3:]
        self.assertEqual(set(review["user"]), {"id", "name", "image"})
        self.assertEqual(review["user"]["id"], self.curator.pk)
        self.assertEqual((review["subtype"], review["comment"], review["verdict"]), ("comment", "note 0", None))
        self.assertEqual(identification["user"]["id"], self.reader.pk)
        self.assertEqual(identification["taxon"]["id"], self.other_taxon.pk)
        self.assertEqual(identification["payload"]["comment"], "round 0")
        self.assertEqual(result["subtype"], "tracking")
        self.assertTrue(result["is_current"])
        self.assertEqual(result["algorithm"]["key"], self.tracking.key)
        self.assertEqual(result["taxon"]["id"], self.taxon.pk)
        self.assertEqual(result["taxon_before"]["id"], self.other_taxon.pk)
        self.assertNotIn("email", str(response.data))

    def test_each_algorithm_shows_one_prediction_preferring_terminal_then_latest(self):
        """Tied top scores would otherwise show the same prediction once per detection."""
        classifier = Algorithm.objects.create(name="Tied classifier", key="tied-classifier-history-test")
        other = Algorithm.objects.create(name="Second tied classifier", key="second-tied-classifier-history-test")
        now = datetime.datetime.now()

        def classify(detection, algorithm, terminal, created_at):
            classification = Classification.objects.create(
                detection=detection, taxon=self.taxon, score=0.8, algorithm=algorithm, terminal=terminal, timestamp=now
            )
            Classification.objects.filter(pk=classification.pk).update(created_at=created_at)
            return classification

        classify(self.detections[0], classifier, False, now)
        terminal = classify(self.detections[1], classifier, True, now - datetime.timedelta(hours=1))
        classify(self.detections[2], other, True, now - datetime.timedelta(hours=1))
        latest = classify(self.detections[3], other, True, now)

        self.client.force_authenticate(user=self.reader)
        response = self.client.get(self.url())
        self.assertEqual(response.status_code, 200, response.data)

        predictions = [entry for entry in response.data if entry["type"] == "prediction"]
        by_algorithm = {
            entry["algorithm"]["key"] if entry["algorithm"] else None: entry["id"] for entry in predictions
        }
        self.assertEqual(len(predictions), 3)
        self.assertEqual(by_algorithm[classifier.key], terminal.pk)
        self.assertEqual(by_algorithm[other.key], latest.pk)
        self.assertIn(None, by_algorithm)

    def test_query_count_does_not_grow_with_the_number_of_entries(self):
        self.client.force_authenticate(user=self.reader)
        now = datetime.datetime.now()
        for rounds, total in ((1, 1), (2, 3)):
            self._add_history(now - datetime.timedelta(days=3 * total), rounds=rounds)
            with self.subTest(rounds=total), main_tests.cachalot_disabled():
                with self.assertNumQueries(HISTORY_QUERIES):
                    response = self.client.get(self.url())
                self.assertEqual(response.status_code, 200)
                self.assertEqual(len(response.data), 3 * total + 1)

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


class OccurrenceCommentEndpointTestCase(main_tests.TrackFixtureTestCase):
    """POST /occurrences/{id}/reviews/ leaves a comment, for whoever may identify on the project."""

    def setUp(self) -> None:
        super().setUp()
        self.identifier = User.objects.create_user(email="comment-identifier@insectai.org")  # type: ignore
        Identifier.assign_user(self.identifier, self.project)
        self.superuser = User.objects.create_superuser(email="comment-super@insectai.org")  # type: ignore
        self.outsider = User.objects.create_user(email="comment-outsider@insectai.org")  # type: ignore

    def comment(self, user: User | None, body: dict | None = None):
        self.client.force_authenticate(user=user)
        return self.client.post(
            f"/api/v2/occurrences/{self.occurrence.pk}/reviews/?project_id={self.project.pk}",
            body if body is not None else {"comment": "  The second frame is a different moth.  "},
            format="json",
        )

    def test_a_comment_is_stored_as_a_review_and_returned_as_a_history_entry(self):
        response = self.comment(self.identifier)
        self.assertEqual(response.status_code, 201, response.data)
        review = ValidationReview.objects.get()
        self.assertEqual((review.aspect, review.verdict, review.user), ("comment", None, self.identifier))
        self.assertEqual(review.comment, "The second frame is a different moth.")
        self.assertEqual(review.project_id, self.project.pk)
        self.assertEqual((response.data["type"], response.data["id"]), ("review", review.pk))
        self.assertNotIn("email", str(response.data))

    def test_an_empty_comment_or_another_aspect_is_refused(self):
        for body in ({"comment": "   "}, {"aspect": "grouping", "comment": "x"}):
            with self.subTest(body=body):
                self.assertEqual(self.comment(self.identifier, body).status_code, 400)
        self.assertFalse(ValidationReview.objects.exists())

    def test_permission_matrix(self):
        """Identifier and curator may comment; a basic member, a non-member and anonymous may not."""
        expected = {
            "identifier": 201,
            "curator": 201,
            "superuser": 201,
            "basic member": 403,
            "non-member": 403,
            "anonymous": 401,
        }
        users = {
            "identifier": self.identifier,
            "curator": self.curator,
            "superuser": self.superuser,
            "basic member": self.reader,
            "non-member": self.outsider,
            "anonymous": None,
        }
        for label, user in users.items():
            with self.subTest(user=label):
                self.assertEqual(self.comment(user).status_code, expected[label])
        self.assertEqual(ValidationReview.objects.count(), 3)
