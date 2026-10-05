"""Algorithm results and the occurrence history endpoint that reads them."""

import contextlib
import datetime

from cachalot.api import cachalot_disabled
from django.db import IntegrityError, connection, transaction
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APITestCase

from ami.jobs.models import Job
from ami.main.models import Classification, Detection, Identification, Occurrence, SourceImage, TaxaList, Taxon
from ami.main.models_future.history import occurrence_timeline
from ami.main.models_future.references import Ref, job_setting_references, resolve_references
from ami.ml.models import Algorithm, AlgorithmResult
from ami.tests.fixtures.main import create_captures, create_taxa, setup_test_project
from ami.users.models import User
from ami.users.roles import BasicMember, ProjectManager

# Measured: two savepoints, the project, the occurrence, then the results with their algorithm and
# job, their taxa, the classifications they created, identifications and predictions. A class
# masking job's settings add one query each for the species lists and source algorithms, whatever
# the number of entries.
HISTORY_QUERIES = 9

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
            ("missing field", {}),
            ("wrong type", {"relative_size": "small"}),
            ("unknown field", {"relative_size": 0.001, "note": "x"}),
            ("extra that is not JSON", {"relative_size": 0.001, "extra": {"when": object()}}),
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
            value=0.001,
            data={"relative_size": 0.001, "extra": {"service": "size-filter 1.2"}},
        )
        self.assertEqual(result.value, 0.001)
        self.assertEqual(result.data["extra"], {"service": "size-filter 1.2"})
        result.data["relative_size"] = "small"
        with self.assertRaises(ValueError):
            AlgorithmResult.objects.bulk_update([result], ["data"])

    def test_a_new_result_becomes_current_and_the_earlier_one_stays_as_history(self):
        first = AlgorithmResult.objects.record(
            occurrence=self.occurrence,
            algorithm=self.algorithm,
            kind=SIZE_FILTER,
            data={"relative_size": 0.01},
        )
        other_occurrence = Occurrence.objects.create(project=self.project, deployment=self.deployment)
        second, untouched = AlgorithmResult.objects.record_many(
            [
                self._size_filter({"relative_size": 0.02}),
                self._size_filter({"relative_size": 0.02}, occurrence=other_occurrence),
            ]
        )
        first.refresh_from_db()
        self.assertFalse(first.is_current)
        self.assertTrue(second.is_current and untouched.is_current)
        self.assertEqual(self.occurrence.algorithm_results.count(), 2)
        self.assertEqual(self.occurrence.algorithm_results.current().get().pk, second.pk)

    def test_merging_moves_results_and_keeps_one_current_per_algorithm_and_kind(self):
        """The kept occurrence's current result wins a collision; otherwise the latest moved one stays current."""
        other_algorithm = Algorithm.objects.create(name="Second size filter", key="size-filter-merge-test")
        absorbed = [Occurrence.objects.create(project=self.project, deployment=self.deployment) for _ in range(3)]

        def record(occurrence, algorithm, size):
            return AlgorithmResult.objects.record(
                occurrence=occurrence, algorithm=algorithm, kind=SIZE_FILTER, data={"relative_size": size}
            )

        kept_current = record(self.occurrence, self.algorithm, 0.01)
        history = record(absorbed[0], self.algorithm, 0.02)
        colliding = record(absorbed[0], self.algorithm, 0.03)
        older = record(absorbed[1], other_algorithm, 0.04)
        latest = record(absorbed[2], other_algorithm, 0.05)

        moved = AlgorithmResult.objects.move_to_occurrence(self.occurrence, [o.pk for o in absorbed])

        self.assertEqual(moved, 4)
        results = {r.pk: r for r in AlgorithmResult.objects.filter(occurrence=self.occurrence)}
        self.assertEqual(set(results), {kept_current.pk, history.pk, colliding.pk, older.pk, latest.pk})
        current = {pk for pk, r in results.items() if r.is_current}
        self.assertEqual(current, {kept_current.pk, latest.pk})

    def test_the_database_holds_one_current_result_per_occurrence_algorithm_and_kind(self):
        self._size_filter({"relative_size": 0.01}).save()
        with transaction.atomic(), self.assertRaises(IntegrityError):
            self._size_filter({"relative_size": 0.02}).save()

    def test_project_comes_from_the_occurrence_and_a_result_without_one_is_skipped(self):
        result = self._size_filter({"relative_size": 0.01})
        result.save()
        self.assertEqual(result.project_id, self.project.pk)

        orphan = Occurrence.objects.create(project=None, deployment=self.deployment)
        with self.assertLogs("ami.ml.models.algorithm_result", level="WARNING"):
            written = AlgorithmResult.objects.record_many(
                [
                    self._size_filter({"relative_size": 0.02}),
                    self._size_filter({"relative_size": 0.03}, occurrence=orphan),
                ]
            )
        # The occurrence with a project still gets its result; the other is skipped, not fatal.
        self.assertEqual([r.occurrence_id for r in written], [self.occurrence.pk])
        with self.assertRaises(ValueError):
            self._size_filter({"relative_size": 0.03}, occurrence=orphan).save()

    def test_the_model_lives_in_the_ml_app(self):
        self.assertEqual(AlgorithmResult._meta.app_label, "ml")


class ReferenceTestCase(TestCase):
    """Ids shown in the history become {type, id, name}; a deleted row keeps its id with no name."""

    def setUp(self):
        self.project, self.deployment = setup_test_project(reuse=False)

    def test_resolves_each_type_in_one_query_and_marks_missing_rows(self):
        taxa_list = TaxaList.objects.create(name="Kept species")
        algorithm = Algorithm.objects.create(name="Classifier", key="ref-test-classifier")
        wanted = [("taxa_list", taxa_list.pk), ("algorithm", algorithm.pk), ("taxa_list", 999999)]
        with no_query_cache(), self.assertNumQueries(2):
            refs = resolve_references(wanted)
        self.assertEqual(refs[("taxa_list", taxa_list.pk)], Ref("taxa_list", taxa_list.pk, "Kept species"))
        self.assertEqual(refs[("algorithm", algorithm.pk)].name, "Classifier")
        self.assertEqual(refs[("taxa_list", 999999)], Ref("taxa_list", 999999, None))

    def test_job_settings_yield_only_known_integer_references(self):
        config = {"taxa_list_id": 3, "source_image_collection_id": 5, "size_threshold": 0.01, "algorithm_id": "x"}
        self.assertEqual(
            sorted(job_setting_references(config)),
            [("source_image_collection_id", "capture_set", 5), ("taxa_list_id", "taxa_list", 3)],
        )
        self.assertEqual(job_setting_references(None), [])
        self.assertEqual(job_setting_references(["not", "a", "dict"]), [])  # type: ignore[arg-type]


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
        """Per round: a size filter result with the classification it created, and an identification."""
        for i in range(rounds):
            at = start + datetime.timedelta(hours=4 * i)
            result = AlgorithmResult.objects.record(
                occurrence=self.occurrence,
                algorithm=self.size_filter,
                job=self.job,
                kind=SIZE_FILTER,
                value=0.001,
                data={
                    "relative_size": 0.001,
                    "determination_before_id": self.other_taxon.pk,
                    "determination_after_id": self.taxon.pk,
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

    def test_entries_are_merged_newest_first_and_a_result_carries_the_classifications_it_created(self):
        # Predictions are stamped with created_at (now), so the history rows sit in the past.
        self._add_history(datetime.datetime.now() - datetime.timedelta(days=2))
        data = self.get()

        types = [entry["type"] for entry in data]
        self.assertEqual(types[-2:], ["identification", "algorithm_result"])
        # The fixture's detections share one tied top prediction, shown once; the result's
        # classification is shown inside the result, not as a prediction of its own.
        self.assertEqual(types[:-2], ["prediction"])
        self.assertIsNone(data[0]["algorithm"])
        timestamps = [entry["timestamp"] for entry in data]
        self.assertEqual(timestamps, sorted(timestamps, reverse=True))

        identification, result = data[-2:]
        self.assertEqual(set(identification["user"]), {"id", "name", "image"})
        self.assertEqual(identification["user"]["id"], self.reader.pk)
        self.assertEqual(identification["taxon"]["id"], self.other_taxon.pk)
        self.assertEqual(identification["payload"]["comment"], "round 0")
        self.assertEqual(result["subtype"], "size_filter")
        self.assertTrue(result["is_current"])
        self.assertEqual(result["algorithm"]["key"], self.size_filter.key)
        self.assertEqual(result["job"], {"id": self.job.pk, "name": self.job.name, "config": {"size_threshold": 0.01}})
        self.assertEqual(result["taxon"]["id"], self.taxon.pk)
        self.assertEqual(result["taxon_before"]["id"], self.other_taxon.pk)
        self.assertEqual(result["score"], 0.001)
        self.assertEqual(result["payload"]["relative_size"], 0.001)
        self.assertIsNone(result["original_taxon"])
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
        taxa_list = TaxaList.objects.create(name="Kept species")
        job = Job.objects.create(
            project=self.project,
            name="Masking run",
            job_type_key="post_processing",
            params={"task": "class_masking", "config": {"taxa_list_id": taxa_list.pk, "algorithm_id": classifier.pk}},
        )
        original = Classification.objects.get(detection=self.detections[1])
        Classification.objects.filter(pk=original.pk).update(terminal=False, algorithm=classifier)
        # A second classifier on the same detection that the run did not re-score.
        bystander_algorithm = Algorithm.objects.create(name="Second classifier", key="bystander-history-test")
        bystander = Classification.objects.create(
            detection=self.detections[1],
            taxon=self.taxon,
            score=0.99,
            terminal=True,
            algorithm=bystander_algorithm,
            timestamp=datetime.datetime.now(),
        )
        result = AlgorithmResult.objects.record(
            occurrence=self.occurrence,
            algorithm=masker,
            job=job,
            kind=CLASS_MASKING,
            value=0.4,
            data={
                "excluded_probability": 0.4,
                "new_winner_original_rank": 2,
                "determination_before_id": self.taxon.pk,
                "determination_after_id": self.other_taxon.pk,
            },
        )
        masked = Classification.objects.create(
            detection=self.detections[1],
            taxon=self.other_taxon,
            score=0.95,
            algorithm=masker,
            timestamp=datetime.datetime.now(),
            applied_to=original,
            job=job,
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
        self.assertEqual(set(predictions), {None, classifier.key, bystander_algorithm.key})
        self.assertEqual(predictions[bystander_algorithm.key]["id"], bystander.pk)
        self.assertIsNone(predictions[bystander_algorithm.key]["payload"]["superseded_by_result_id"])
        demoted = predictions[classifier.key]
        self.assertEqual(demoted["id"], original.pk)
        self.assertEqual(demoted["payload"]["superseded_by_result_id"], result.pk)
        self.assertFalse(demoted["payload"]["terminal"])
        self.assertIsNone(predictions[None]["payload"]["superseded_by_result_id"])
        self.assertEqual(result_entry["taxa_list"], {"id": taxa_list.pk, "name": "Kept species"})
        self.assertEqual(result_entry["source_algorithm"]["key"], classifier.key)
        self.assertEqual(result_entry["score"], 0.4)

    def test_a_terminal_prediction_outranked_on_its_detection_is_superseded(self):
        """The size filter does not demote the prediction it outranks, so the link is the shared detection."""
        # The fixture's tied predictions resolve to the latest one, on the last detection.
        outranked = self.detections[3].classifications.get()
        result = AlgorithmResult.objects.record(
            occurrence=self.occurrence,
            algorithm=self.size_filter,
            job=self.job,
            kind=SIZE_FILTER,
            data={"relative_size": 0.001},
        )
        Classification.objects.create(
            detection=self.detections[3],
            taxon=self.other_taxon,
            score=1.0,
            algorithm=self.size_filter,
            timestamp=datetime.datetime.now(),
            algorithm_result=result,
        )
        data = self.get()

        prediction = next(entry for entry in data if entry["type"] == "prediction")
        self.assertEqual(prediction["id"], outranked.pk)
        self.assertEqual(prediction["payload"]["superseded_by_result_id"], result.pk)

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
                self.assertEqual(len(response.data), 2 * total + 1)
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

    def test_a_result_lists_what_each_created_classification_replaced(self):
        classifier = Algorithm.objects.create(name="Classifier", key="replaced-test-classifier")
        masker = Algorithm.objects.create(name="Masked", key="replaced-test-masker")
        original = Classification.objects.get(detection=self.detections[1])
        Classification.objects.filter(pk=original.pk).update(terminal=False, algorithm=classifier)
        result = AlgorithmResult.objects.record(
            occurrence=self.occurrence,
            algorithm=masker,
            kind=CLASS_MASKING,
            value=0.4,
            data={"excluded_probability": 0.4},
        )
        masked = Classification.objects.create(
            detection=self.detections[1],
            taxon=self.other_taxon,
            score=0.9,
            algorithm=masker,
            timestamp=datetime.datetime.now(),
            applied_to=original,
            algorithm_result=result,
        )
        # The original was deleted (applied_to is SET_NULL until #1472), so nothing is shown as replaced.
        orphan = Classification.objects.create(
            detection=self.detections[2],
            taxon=self.other_taxon,
            score=0.8,
            algorithm=masker,
            timestamp=datetime.datetime.now(),
            applied_to=None,
            algorithm_result=result,
        )
        entry = next(e for e in occurrence_timeline(self.occurrence) if e.type == "algorithm_result")
        by_id = {c.classification.pk: c for c in entry.classifications}
        self.assertEqual(by_id[masked.pk].replaced.pk, original.pk)
        self.assertEqual(by_id[masked.pk].replaced.taxon_id, original.taxon_id)
        self.assertIsNone(by_id[orphan.pk].replaced)

    def test_classifications_link_to_a_result_only_through_algorithm_result(self):
        """A classification sharing the result's job but not linked to it stays an ordinary prediction."""
        AlgorithmResult.objects.record(
            occurrence=self.occurrence,
            algorithm=self.size_filter,
            job=self.job,
            kind=SIZE_FILTER,
            data={"relative_size": 0.001},
        )
        unlinked = Classification.objects.create(
            detection=self.detections[0],
            taxon=self.taxon,
            score=0.99,
            algorithm=self.size_filter,
            timestamp=datetime.datetime.now(),
            job=self.job,
        )
        entries = occurrence_timeline(self.occurrence)
        result_entry = next(e for e in entries if e.type == "algorithm_result")
        self.assertEqual(result_entry.classifications, [])
        self.assertIn(unlinked.pk, [e.id for e in entries if e.type == "prediction"])

    def test_predictions_carry_the_job_that_wrote_them(self):
        Classification.objects.filter(detection__occurrence=self.occurrence).update(job=self.job)
        predictions = [e for e in occurrence_timeline(self.occurrence) if e.type == "prediction"]
        self.assertTrue(predictions)
        self.assertTrue(all(e.job == self.job for e in predictions))

    def test_job_settings_are_resolved_to_references(self):
        taxa_list = TaxaList.objects.create(name="Kept species")
        self.job.params = {"config": {"taxa_list_id": taxa_list.pk, "size_threshold": 0.01}}
        self.job.save()
        AlgorithmResult.objects.record(
            occurrence=self.occurrence,
            algorithm=self.size_filter,
            job=self.job,
            kind=SIZE_FILTER,
            data={"relative_size": 0.001},
        )
        entry = next(e for e in occurrence_timeline(self.occurrence) if e.type == "algorithm_result")
        self.assertEqual(entry.job_references, {"taxa_list_id": Ref("taxa_list", taxa_list.pk, "Kept species")})

    def test_a_result_without_a_job_has_no_settings_or_references(self):
        AlgorithmResult.objects.record(
            occurrence=self.occurrence,
            algorithm=self.size_filter,
            job=None,
            kind=SIZE_FILTER,
            data={"relative_size": 0.001},
        )
        entry = next(e for e in occurrence_timeline(self.occurrence) if e.type == "algorithm_result")
        self.assertIsNone(entry.job)
        self.assertEqual(entry.job_references, {})
