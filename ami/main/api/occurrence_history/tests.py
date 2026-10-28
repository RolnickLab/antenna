"""Algorithm results and the occurrence history endpoint that reads them."""

import datetime
import re

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APITestCase

from ami.jobs.models import Job
from ami.main.api.occurrence_history.timeline import occurrence_timeline
from ami.main.models import (
    Classification,
    Detection,
    Identification,
    Occurrence,
    SourceImage,
    SourceImageCollection,
    TaxaList,
    Taxon,
)
from ami.ml.models import Algorithm, AlgorithmResult
from ami.ml.post_processing.class_masking import ClassMaskingResultData
from ami.ml.post_processing.small_size_filter import SizeFilterResultData
from ami.tests.fixtures.main import create_captures, create_taxa, setup_test_project
from ami.tests.fixtures.queries import no_query_cache
from ami.users.models import User
from ami.users.roles import BasicMember, ProjectManager

# Measured: two savepoints, the project, the occurrence, the results with their algorithm and job,
# their taxa, the classifications they created, the classifications those replaced, identifications,
# predictions with their jobs, and one query per type of record the entries name (here capture sets).
HISTORY_QUERIES = 11

SIZE_FILTER = SizeFilterResultData.kind
CLASS_MASKING = ClassMaskingResultData.kind


class OccurrenceHistorySchemaTestCase(TestCase):
    """The OpenAPI schema publishes the history as a oneOf of identification, prediction and result entries."""

    def test_the_history_entries_are_a_oneof_tagged_by_type(self):
        from drf_spectacular.generators import SchemaGenerator

        components = SchemaGenerator(api_version="api").get_schema(request=None, public=True)["components"]["schemas"]
        entry_names = {ref["$ref"].rsplit("/", 1)[-1] for ref in components["OccurrenceHistoryEntry"]["oneOf"]}
        self.assertEqual(entry_names, {"IdentificationEntry", "PredictionEntry", "AlgorithmResultEntry"})
        # Named enums, not drf-spectacular's hashed fallback names.
        self.assertIn("AlgorithmResultEntryTypeEnum", components)


class OccurrenceFixtureTestCase(APITestCase):
    """One occurrence of four classified detections, with a project manager and a basic member."""

    @classmethod
    def setUpTestData(cls) -> None:
        cls.project, cls.deployment = setup_test_project(reuse=False)
        create_taxa(project=cls.project)
        create_captures(deployment=cls.deployment, num_nights=1, images_per_night=4, interval_minutes=1)
        captures = list(SourceImage.objects.filter(deployment=cls.deployment).order_by("timestamp"))
        cls.taxon = Taxon.objects.filter(projects=cls.project).order_by("pk").first()

        cls.manager = User.objects.create_user(email="history-manager@insectai.org")  # type: ignore
        cls.reader = User.objects.create_user(email="history-reader@insectai.org")  # type: ignore
        ProjectManager.assign_user(cls.manager, cls.project)
        BasicMember.assign_user(cls.reader, cls.project)

        cls.occurrence = Occurrence.objects.create(
            event=captures[0].event, deployment=cls.deployment, project=cls.project
        )
        cls.detections = []
        for capture in captures[:4]:
            detection = Detection.objects.create(
                source_image=capture, timestamp=capture.timestamp, bbox=[10, 10, 40, 40], occurrence=cls.occurrence
            )
            detection.classifications.create(taxon=cls.taxon, score=0.9, timestamp=capture.timestamp)
            cls.detections.append(detection)
        cls.occurrence.save()


class OccurrenceHistoryEndpointTestCase(OccurrenceFixtureTestCase):
    """GET /occurrences/{id}/history/ merges results, identifications and predictions, newest first."""

    @classmethod
    def setUpTestData(cls) -> None:
        super().setUpTestData()
        cls.size_filter = Algorithm.objects.create(name="Small size filter", key="size-filter-history-test")
        cls.job = Job.objects.create(
            project=cls.project,
            name="Size filter run",
            job_type_key="post_processing",
            params={"task": "small_size_filter", "config": {"size_threshold": 0.01}},
        )
        cls.other_taxon = Taxon.objects.filter(projects=cls.project).exclude(pk=cls.taxon.pk).first()
        cls.superuser = User.objects.create_superuser(email="history-super@insectai.org")  # type: ignore
        cls.outsider = User.objects.create_user(email="history-outsider@insectai.org")  # type: ignore

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
        self.assertEqual(identification["details"]["comment"], "round 0")
        self.assertEqual(result["kind"], "size_filter")
        self.assertEqual(result["algorithm"]["key"], self.size_filter.key)
        self.assertEqual(
            result["job"],
            {
                "id": self.job.pk,
                "name": self.job.name,
                # The label is the title the size filter's config schema gives the setting.
                "config": [{"key": "size_threshold", "label": "Size threshold", "value": 0.01, "refs": []}],
            },
        )
        self.assertIsNone(result["taxon"])
        self.assertEqual(result["determination_after"]["id"], self.taxon.pk)
        self.assertEqual(result["determination_before"]["id"], self.other_taxon.pk)
        self.assertIsNone(result["score"])
        self.assertEqual(result["value"], 0.001)
        self.assertEqual(result["data"]["relative_size"], 0.001)
        created = Classification.objects.get(algorithm=self.size_filter)
        self.assertEqual(
            result["classifications"],
            [
                {
                    "id": created.pk,
                    "taxon": {"id": self.taxon.pk, "name": self.taxon.name, "rank": self.taxon.rank, "parents": []},
                    "score": 0.1,
                    "terminal": True,
                    "detection_id": self.detections[0].pk,
                    "replaced": None,
                }
            ],
        )
        self.assertNotIn("email", str(data))

    def test_a_masked_prediction_shows_inside_its_result_and_the_original_stays_as_a_prediction(self):
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
        # keeps its card, demoted to non-terminal.
        predictions = {
            entry["algorithm"]["key"] if entry["algorithm"] else None: entry
            for entry in data
            if entry["type"] == "prediction"
        }
        self.assertEqual(set(predictions), {None, classifier.key, bystander_algorithm.key})
        self.assertEqual(predictions[bystander_algorithm.key]["id"], bystander.pk)
        demoted = predictions[classifier.key]
        self.assertEqual(demoted["id"], original.pk)
        self.assertFalse(demoted["details"]["terminal"])
        config = {field["key"]: field for field in result_entry["job"]["config"]}
        self.assertEqual(
            config["taxa_list_id"],
            {
                "key": "taxa_list_id",
                "label": "Species list",
                "value": taxa_list.pk,
                "refs": [{"type": "taxa_list", "id": taxa_list.pk, "name": "Kept species"}],
            },
        )
        self.assertEqual(config["algorithm_id"]["label"], "Classifier")
        self.assertEqual(
            config["algorithm_id"]["refs"], [{"type": "algorithm", "id": classifier.pk, "name": classifier.name}]
        )
        # The top prediction before masking is the classification the masked one replaced.
        self.assertEqual(result_entry["classifications"][0]["replaced"]["id"], original.pk)
        self.assertEqual(result_entry["classifications"][0]["replaced"]["taxon"]["id"], self.taxon.pk)
        self.assertEqual(result_entry["value"], 0.4)

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
        # A setting that names a record, and created classifications that replaced one, so the
        # reference and replaced-classification queries are counted too.
        scope = SourceImageCollection.objects.create(project=self.project, name="Scope")
        self.job.params = {
            "task": "small_size_filter",
            "config": {"size_threshold": 0.01, "source_image_collection_id": scope.pk},
        }
        self.job.save()
        original = Classification.objects.get(detection=self.detections[0])
        now = datetime.datetime.now()
        for rounds, total in ((1, 1), (2, 3)):
            self._add_history(now - datetime.timedelta(days=3 * total), rounds=rounds)
            Classification.objects.filter(algorithm=self.size_filter).update(applied_to=original)
            with self.subTest(rounds=total), no_query_cache():
                with CaptureQueriesContext(connection) as queries, self.assertNumQueries(HISTORY_QUERIES):
                    response = self.client.get(self.url())
                self.assertEqual(response.status_code, 200)
                self.assertEqual(len(response.data), 2 * total + 1)
                self.assertFalse(
                    [q["sql"] for q in queries.captured_queries if '"main_classification"."scores"' in q["sql"]]
                )
                # A job's progress and logs can be large JSON documents; the history shows neither.
                self.assertFalse(
                    [
                        q["sql"]
                        for q in queries.captured_queries
                        if re.search(r'"jobs_job"\."(progress|logs)"', q["sql"])
                    ]
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

    def test_the_list_filters_do_not_hide_the_history(self):
        """A list filter in the query string names no occurrence, so it must not turn the history into a 404."""
        self.client.force_authenticate(user=self.reader)
        response = self.client.get(f"{self.url()}&event=0&taxon=0&search=nothing-matches")
        self.assertEqual(response.status_code, 200)

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

    def test_a_result_without_a_job_has_no_config(self):
        AlgorithmResult.objects.record(
            occurrence=self.occurrence,
            algorithm=self.size_filter,
            job=None,
            kind=SIZE_FILTER,
            data={"relative_size": 0.001},
        )
        entry = next(e for e in occurrence_timeline(self.occurrence) if e.type == "algorithm_result")
        self.assertIsNone(entry.job)
        self.assertEqual(entry.job_config, [])

    def test_a_result_of_a_kind_no_longer_registered_still_shows_in_the_history(self):
        """A row written by a branch with an extra kind, or before a kind was renamed, must not break the history."""
        result = AlgorithmResult.objects.record(
            occurrence=self.occurrence, algorithm=self.size_filter, kind=SIZE_FILTER, data={"relative_size": 0.001}
        )
        AlgorithmResult.objects.filter(pk=result.pk).update(kind="rank_rollup")
        entry = next(e for e in self.get() if e["type"] == "algorithm_result")
        self.assertEqual(entry["kind"], "rank_rollup")
