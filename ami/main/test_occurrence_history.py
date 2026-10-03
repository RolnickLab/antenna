"""Algorithm results, validation reviews, and the occurrence history endpoint that reads them."""

import contextlib
import datetime

from cachalot.api import cachalot_disabled
from django.db import IntegrityError, connection, transaction
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APITestCase

from ami.jobs.models import Job
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
from ami.ml.models import Algorithm
from ami.tests.fixtures.main import create_captures, create_taxa, setup_test_project
from ami.users.models import User
from ami.users.roles import BasicMember, Identifier, ProjectManager

# Measured: two savepoints, the project, the occurrence, then the results with their algorithm and
# job, their taxa, the classifications they created, reviews, identifications and predictions.
HISTORY_QUERIES = 10

SIZE_FILTER = AlgorithmResult.Kind.SIZE_FILTER
CLASS_MASKING = AlgorithmResult.Kind.CLASS_MASKING


@contextlib.contextmanager
def no_query_cache():
    """``cachalot_disabled`` that restores the cache even when the block raises, so one failure stays one."""
    context = cachalot_disabled()
    context.__enter__()
    try:
        yield
    finally:
        context.__exit__(None, None, None)


class AlgorithmResultTestCase(TestCase):
    """A result's data fits its kind, its project is its occurrence's, and a new result replaces the current one."""

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

        result = AlgorithmResult.objects.record(
            occurrence=self.occurrence,
            algorithm=self.algorithm,
            kind=SIZE_FILTER,
            data={"size_threshold": 0.01, "detection_ids": []},
        )
        result.data["size_threshold"] = "small"
        with self.assertRaises(ValueError):
            AlgorithmResult.objects.bulk_update([result], ["data"])

    def test_a_new_result_becomes_current_and_the_earlier_one_stays_as_history(self):
        first = AlgorithmResult.objects.record(
            occurrence=self.occurrence,
            algorithm=self.algorithm,
            kind=SIZE_FILTER,
            data={"size_threshold": 0.01, "detection_ids": [1]},
        )
        other_occurrence = Occurrence.objects.create(project=self.project, deployment=self.deployment)
        second, untouched = AlgorithmResult.objects.record_many(
            [
                self._size_filter({"size_threshold": 0.02, "detection_ids": [1]}),
                self._size_filter({"size_threshold": 0.02, "detection_ids": [2]}, occurrence=other_occurrence),
            ]
        )
        first.refresh_from_db()
        self.assertFalse(first.is_current)
        self.assertTrue(second.is_current and untouched.is_current)
        self.assertEqual(AlgorithmResult.objects.for_occurrence(self.occurrence).count(), 2)
        self.assertEqual(AlgorithmResult.objects.for_occurrence(self.occurrence).current().get().pk, second.pk)

    def test_the_database_holds_one_current_result_per_occurrence_algorithm_and_kind(self):
        self._size_filter({"size_threshold": 0.01, "detection_ids": []}).save()
        with transaction.atomic(), self.assertRaises(IntegrityError):
            self._size_filter({"size_threshold": 0.02, "detection_ids": []}).save()

    def test_project_comes_from_the_occurrence_or_its_station_and_a_result_with_neither_is_skipped(self):
        other = Project.objects.create(name="Another project")
        Occurrence.objects.filter(pk=self.occurrence.pk).update(project=None)
        self.occurrence.refresh_from_db()
        result = self._size_filter({"size_threshold": 0.01, "detection_ids": []})
        result.save()
        self.assertEqual(result.project_id, self.project.pk)

        Occurrence.objects.filter(pk=self.occurrence.pk).update(project=other)
        self.occurrence.refresh_from_db()
        self.assertEqual(
            AlgorithmResult.objects.record_many([self._size_filter({"size_threshold": 0.02, "detection_ids": []})])[
                0
            ].project_id,
            other.pk,
        )

        Occurrence.objects.filter(pk=self.occurrence.pk).update(project=None, deployment=None)
        self.occurrence.refresh_from_db()
        with self.assertLogs("ami.main.models", level="WARNING"):
            written = AlgorithmResult.objects.record_many(
                [self._size_filter({"size_threshold": 0.03, "detection_ids": []})]
            )
        self.assertEqual(written, [])
        with self.assertRaises(ValueError):
            self._size_filter({"size_threshold": 0.03, "detection_ids": []}).save()
        self.assertEqual(AlgorithmResult.objects.count(), 2)


class ValidationReviewTestCase(TestCase):
    def setUp(self) -> None:
        self.project, self.deployment = setup_test_project(reuse=False)
        self.occurrence = Occurrence.objects.create(project=self.project, deployment=self.deployment)
        self.user = User.objects.create_user(email="review-model@insectai.org")  # type: ignore

    def test_a_comment_has_text_and_no_verdict(self):
        for label, fields in (
            ("comment with a verdict", {"comment": "x", "verdict": "confirmed"}),
            ("empty comment", {"comment": ""}),
        ):
            with self.subTest(label), transaction.atomic(), self.assertRaises(IntegrityError):
                ValidationReview.objects.create(occurrence=self.occurrence, user=self.user, aspect="comment", **fields)
        with self.assertRaises(ValueError):
            ValidationReview.objects.create(
                occurrence=self.occurrence, user=self.user, aspect="comment", comment="x", payload={"extra": 1}
            )

    def test_a_review_takes_its_occurrences_project(self):
        Occurrence.objects.filter(pk=self.occurrence.pk).update(project=None)
        self.occurrence.refresh_from_db()
        review = ValidationReview.objects.create(
            occurrence=self.occurrence, user=self.user, aspect="comment", comment="x"
        )
        self.assertEqual(review.project_id, self.project.pk)


class OccurrenceFixtureTestCase(APITestCase):
    """One occurrence of four classified detections, with a project manager and a basic member."""

    def setUp(self) -> None:
        self.project, self.deployment = setup_test_project(reuse=False)
        create_taxa(project=self.project)
        create_captures(deployment=self.deployment, num_nights=1, images_per_night=4, interval_minutes=1)
        captures = list(SourceImage.objects.filter(deployment=self.deployment).order_by("timestamp"))
        self.taxon = Taxon.objects.filter(projects=self.project).order_by("pk").first()

        self.manager = User.objects.create_user(email="history-manager@insectai.org")  # type: ignore
        self.reader = User.objects.create_user(email="history-reader@insectai.org")  # type: ignore
        ProjectManager.assign_user(self.manager, self.project)
        BasicMember.assign_user(self.reader, self.project)

        self.occurrence = Occurrence.objects.create(
            event=captures[0].event, deployment=self.deployment, project=self.project
        )
        self.detections = []
        for capture in captures[:4]:
            detection = Detection.objects.create(
                source_image=capture, timestamp=capture.timestamp, bbox=[10, 10, 40, 40], occurrence=self.occurrence
            )
            detection.classifications.create(taxon=self.taxon, score=0.9, timestamp=capture.timestamp)
            self.detections.append(detection)
        self.occurrence.save()
        return super().setUp()


class OccurrenceHistoryEndpointTestCase(OccurrenceFixtureTestCase):
    """GET /occurrences/{id}/history/ merges results, reviews, identifications and predictions, newest first."""

    def setUp(self) -> None:
        super().setUp()
        self.size_filter = Algorithm.objects.create(name="Small size filter", key="size-filter-history-test")
        self.job = Job.objects.create(
            project=self.project,
            name="Size filter run",
            job_type_key="post_processing",
            params={"task": "small_size_filter", "config": {"size_threshold": 0.01}},
        )
        self.other_taxon = Taxon.objects.filter(projects=self.project).exclude(pk=self.taxon.pk).first()
        self.superuser = User.objects.create_superuser(email="history-super@insectai.org")  # type: ignore
        self.outsider = User.objects.create_user(email="history-outsider@insectai.org")  # type: ignore

    def url(self, occurrence: Occurrence | None = None) -> str:
        return f"/api/v2/occurrences/{(occurrence or self.occurrence).pk}/history/?project_id={self.project.pk}"

    def get(self, user: User | None = None):
        self.client.force_authenticate(user=user or self.reader)
        response = self.client.get(self.url())
        self.assertEqual(response.status_code, 200, response.data)
        return response.data

    def _add_history(self, start: datetime.datetime, rounds: int = 1) -> None:
        """Per round: a size filter result with the classification it created, an identification and a comment."""
        for i in range(rounds):
            at = start + datetime.timedelta(hours=4 * i)
            result = AlgorithmResult.objects.record(
                occurrence=self.occurrence,
                algorithm=self.size_filter,
                job=self.job,
                kind=SIZE_FILTER,
                data={
                    "size_threshold": 0.01,
                    "detection_ids": [self.detections[0].pk],
                    "taxon_before_id": self.other_taxon.pk,
                    "taxon_after_id": self.taxon.pk,
                },
                timestamp=at,
            )
            Classification.objects.create(
                detection=self.detections[0],
                taxon=self.taxon,
                score=0.1,
                algorithm=self.size_filter,
                timestamp=at,
                job=self.job,
                algorithm_result=result,
            )
            identification = Identification.objects.create(
                occurrence=self.occurrence, user=self.reader, taxon=self.other_taxon, comment=f"round {i}"
            )
            Identification.objects.filter(pk=identification.pk).update(created_at=at + datetime.timedelta(hours=1))
            ValidationReview.objects.create(
                occurrence=self.occurrence,
                user=self.manager,
                aspect="comment",
                comment=f"note {i}",
                timestamp=at + datetime.timedelta(hours=2),
            )

    def test_entries_are_merged_newest_first_and_a_result_carries_the_classifications_it_created(self):
        # Predictions are stamped with created_at (now), so the history rows sit in the past.
        self._add_history(datetime.datetime.now() - datetime.timedelta(days=2))
        data = self.get()

        types = [entry["type"] for entry in data]
        self.assertEqual(types[-3:], ["review", "identification", "algorithm_result"])
        # The fixture's detections share one tied top prediction, shown once; the result's
        # classification is shown inside the result, not as a prediction of its own.
        self.assertEqual(types[:-3], ["prediction"])
        self.assertIsNone(data[0]["algorithm"])
        timestamps = [entry["timestamp"] for entry in data]
        self.assertEqual(timestamps, sorted(timestamps, reverse=True))

        review, identification, result = data[-3:]
        self.assertEqual(set(review["user"]), {"id", "name", "image"})
        self.assertEqual(review["user"]["id"], self.manager.pk)
        self.assertEqual((review["subtype"], review["comment"], review["verdict"]), ("comment", "note 0", None))
        self.assertEqual(identification["user"]["id"], self.reader.pk)
        self.assertEqual(identification["taxon"]["id"], self.other_taxon.pk)
        self.assertEqual(identification["payload"]["comment"], "round 0")
        self.assertEqual(result["subtype"], "size_filter")
        self.assertTrue(result["is_current"])
        self.assertEqual(result["algorithm"]["key"], self.size_filter.key)
        self.assertEqual(result["job"], {"id": self.job.pk, "name": self.job.name, "config": {"size_threshold": 0.01}})
        self.assertEqual(result["taxon"]["id"], self.taxon.pk)
        self.assertEqual(result["taxon_before"]["id"], self.other_taxon.pk)
        created = Classification.objects.get(algorithm=self.size_filter)
        self.assertEqual(
            result["classifications"],
            [
                {
                    "id": created.pk,
                    "taxon": {"id": self.taxon.pk, "name": self.taxon.name, "rank": self.taxon.rank},
                    "score": 0.1,
                    "terminal": True,
                    "detection_id": self.detections[0].pk,
                    "applied_to_id": None,
                }
            ],
        )
        self.assertNotIn("email", str(data))

    def test_a_demoted_prediction_names_the_result_that_superseded_it(self):
        """Class masking demotes the original classification and links its replacement to the result."""
        classifier = Algorithm.objects.create(name="Classifier", key="classifier-history-test")
        masker = Algorithm.objects.create(name="Masked classifier", key="masker-history-test")
        original = Classification.objects.get(detection=self.detections[1])
        Classification.objects.filter(pk=original.pk).update(terminal=False, algorithm=classifier)
        result = AlgorithmResult.objects.record(
            occurrence=self.occurrence,
            algorithm=masker,
            job=self.job,
            kind=CLASS_MASKING,
            data={
                "taxa_list_id": 1,
                "source_algorithm_id": 1,
                "detection_ids": [self.detections[1].pk],
                "taxon_before_id": self.taxon.pk,
                "taxon_after_id": self.other_taxon.pk,
            },
        )
        masked = Classification.objects.create(
            detection=self.detections[1],
            taxon=self.other_taxon,
            score=0.95,
            algorithm=masker,
            timestamp=datetime.datetime.now(),
            applied_to=original,
            job=self.job,
            algorithm_result=result,
        )
        data = self.get()

        result_entry = next(entry for entry in data if entry["type"] == "algorithm_result")
        self.assertEqual([c["id"] for c in result_entry["classifications"]], [masked.pk])
        # The masked classification shows inside the result, not as a prediction; the original
        # still has its card, marked as superseded by the run.
        predictions = {
            entry["algorithm"]["key"] if entry["algorithm"] else None: entry
            for entry in data
            if entry["type"] == "prediction"
        }
        self.assertEqual(set(predictions), {None, classifier.key})
        demoted = predictions[classifier.key]
        self.assertEqual(demoted["id"], original.pk)
        self.assertEqual(demoted["payload"]["superseded_by_result_id"], result.pk)
        self.assertFalse(demoted["payload"]["terminal"])
        self.assertIsNone(predictions[None]["payload"]["superseded_by_result_id"])

    def test_a_classification_without_a_result_link_is_matched_to_its_jobs_result(self):
        result = AlgorithmResult.objects.record(
            occurrence=self.occurrence,
            algorithm=self.size_filter,
            job=self.job,
            kind=SIZE_FILTER,
            data={"size_threshold": 0.01, "detection_ids": [self.detections[0].pk]},
        )
        created = Classification.objects.create(
            detection=self.detections[0],
            taxon=self.taxon,
            score=0.1,
            algorithm=self.size_filter,
            timestamp=datetime.datetime.now(),
            job=self.job,
        )
        data = self.get()

        result_entry = next(entry for entry in data if entry["type"] == "algorithm_result")
        self.assertEqual(result_entry["id"], result.pk)
        self.assertEqual([c["id"] for c in result_entry["classifications"]], [created.pk])
        predictions = [e for e in data if e["type"] == "prediction"]
        self.assertEqual([e["algorithm"] for e in predictions], [None])
        self.assertNotEqual(predictions[0]["id"], created.pk)

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

        predictions = [entry for entry in self.get() if entry["type"] == "prediction"]
        by_algorithm = {
            entry["algorithm"]["key"] if entry["algorithm"] else None: entry["id"] for entry in predictions
        }
        self.assertEqual(len(predictions), 3)
        self.assertEqual(by_algorithm[classifier.key], terminal.pk)
        self.assertEqual(by_algorithm[other.key], latest.pk)
        self.assertIn(None, by_algorithm)

    def test_query_count_does_not_grow_with_the_entries_and_no_score_arrays_are_loaded(self):
        self.client.force_authenticate(user=self.reader)
        now = datetime.datetime.now()
        for rounds, total in ((1, 1), (2, 3)):
            self._add_history(now - datetime.timedelta(days=3 * total), rounds=rounds)
            with self.subTest(rounds=total), no_query_cache():
                with CaptureQueriesContext(connection) as queries, self.assertNumQueries(HISTORY_QUERIES):
                    response = self.client.get(self.url())
                self.assertEqual(response.status_code, 200)
                self.assertEqual(len(response.data), 3 * total + 1)
                self.assertFalse(
                    [q["sql"] for q in queries.captured_queries if '"main_classification"."scores"' in q["sql"]]
                )

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


class OccurrenceCommentEndpointTestCase(OccurrenceFixtureTestCase):
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
            body if body is not None else {"comment": "  The second detection is a different moth.  "},
            format="json",
        )

    def test_a_comment_is_stored_as_a_review_and_returned_as_a_history_entry(self):
        response = self.comment(self.identifier)
        self.assertEqual(response.status_code, 201, response.data)
        review = ValidationReview.objects.get()
        self.assertEqual((review.aspect, review.verdict, review.user), ("comment", None, self.identifier))
        self.assertEqual(review.comment, "The second detection is a different moth.")
        self.assertEqual(review.project_id, self.project.pk)
        self.assertEqual((response.data["type"], response.data["id"]), ("review", review.pk))
        self.assertNotIn("email", str(response.data))

    def test_an_empty_comment_or_another_aspect_is_refused(self):
        for body in ({"comment": "   "}, {"aspect": "grouping", "comment": "x"}):
            with self.subTest(body=body):
                self.assertEqual(self.comment(self.identifier, body).status_code, 400)
        self.assertFalse(ValidationReview.objects.exists())

    def test_permission_matrix(self):
        """Whoever may identify may comment; a basic member, a non-member and anonymous may not."""
        expected = {
            "identifier": 201,
            "project manager": 201,
            "superuser": 201,
            "basic member": 403,
            "non-member": 403,
            "anonymous": 401,
        }
        users = {
            "identifier": self.identifier,
            "project manager": self.manager,
            "superuser": self.superuser,
            "basic member": self.reader,
            "non-member": self.outsider,
            "anonymous": None,
        }
        for label, user in users.items():
            with self.subTest(user=label):
                self.assertEqual(self.comment(user).status_code, expected[label])
        self.assertEqual(ValidationReview.objects.count(), 3)
