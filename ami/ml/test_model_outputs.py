"""The registry of algorithm output tables (ami/ml/model_outputs.py) and the queries built from it.

Each query that asks "did this algorithm or job produce results" must find a row in every registered
table, and a new output table must be registered or explicitly exempted. See #1462.
"""

import datetime

from django.apps import apps
from django.test import SimpleTestCase, TestCase

from ami.jobs.models import Job
from ami.main.models import Classification, Deployment, Detection, Event, Occurrence, Project, SourceImage, Taxon
from ami.ml import model_outputs
from ami.ml.models import Algorithm, AlgorithmResult
from ami.ml.post_processing.small_size_filter import SizeFilterResultData


class TestModelOutputsRegistry(SimpleTestCase):
    def test_every_model_with_an_algorithm_and_a_job_is_registered_or_exempt(self):
        """A table that records which algorithm and job wrote its rows is an output table, so the
        filters and the algorithm list must know it. A new one fails here until someone registers it
        or says in ``EXEMPT_MODELS`` why it does not count."""
        candidates = set()
        for model in apps.get_models():
            related = {field.related_model for field in model._meta.get_fields() if field.many_to_one}
            if Algorithm in related and Job in related:
                candidates.add(model._meta.label)

        registered = {output.model for output in model_outputs.MODEL_OUTPUTS}
        self.assertEqual(candidates - registered - set(model_outputs.EXEMPT_MODELS), set())
        self.assertEqual(registered & set(model_outputs.EXEMPT_MODELS), set(), "A model is registered or exempt")
        self.assertEqual(registered - candidates, set(), "A registered model has no algorithm and job")

    def test_folded_outputs_point_at_registered_outputs(self):
        registered = {output.model for output in model_outputs.MODEL_OUTPUTS if not output.folded_into}
        for output in model_outputs.MODEL_OUTPUTS:
            if output.folded_into:
                self.assertIn(output.folded_into, registered, output.model)


class TestModelOutputQueries(TestCase):
    """Writes one output row in each registered table, each for its own occurrence, algorithm and job,
    then checks that every query finds exactly that table's row. The writers are keyed by table, so a
    registered table without a writer fails ``test_a_writer_exists_for_every_registered_table``."""

    def setUp(self):
        self.project = Project.objects.create(name="Model Outputs Project")
        self.deployment = Deployment.objects.create(project=self.project, name="dep")
        self.event = Event.objects.create(
            project=self.project,
            deployment=self.deployment,
            group_by="2024-01-01",
            start=datetime.datetime(2024, 1, 1, 0, 0),
        )
        self.source_image = SourceImage.objects.create(
            deployment=self.deployment, project=self.project, event=self.event, path="model-outputs.jpg"
        )
        self.taxon = Taxon.objects.create(name="Model Outputs Taxon")
        self.writers = {
            "main.Detection": self._write_detection,
            "main.Classification": self._write_classification,
            "ml.AlgorithmResult": self._write_algorithm_result,
        }
        # model label -> (occurrence, algorithm, job) for the one row written in that table.
        self.written = {}
        for index, output in enumerate(model_outputs.MODEL_OUTPUTS):
            occurrence = self._make_occurrence()
            algorithm = Algorithm.objects.create(name=f"Output algorithm {index}", version=1)
            job = Job.objects.create(project=self.project, name=f"Output job {index}")
            self.writers[output.model](occurrence, algorithm, job)
            self.written[output.model] = (occurrence, algorithm, job)
        self.unused_algorithm = Algorithm.objects.create(name="Never run", version=1)
        self.untouched = self._make_occurrence()

    def _make_occurrence(self) -> Occurrence:
        return Occurrence.objects.create(
            project=self.project,
            event=self.event,
            deployment=self.deployment,
            determination=self.taxon,
            determination_score=0.9,
        )

    def _make_detection(self, occurrence, **fields) -> Detection:
        return Detection.objects.create(
            source_image=self.source_image, bbox=[0.0, 0.0, 1.0, 1.0], occurrence=occurrence, **fields
        )

    def _write_detection(self, occurrence, algorithm, job):
        self._make_detection(occurrence, detection_algorithm=algorithm, job=job)

    def _write_classification(self, occurrence, algorithm, job):
        Classification.objects.create(
            detection=self._make_detection(occurrence),
            taxon=self.taxon,
            algorithm=algorithm,
            score=0.9,
            timestamp=datetime.datetime.now(),
            job=job,
        )

    def _write_algorithm_result(self, occurrence, algorithm, job):
        AlgorithmResult.objects.record(
            occurrence=occurrence,
            algorithm=algorithm,
            job=job,
            kind=SizeFilterResultData.kind,
            data={"relative_size": 0.001},
        )

    def _occurrences(self):
        return Occurrence.objects.filter(project=self.project)

    def test_a_writer_exists_for_every_registered_table(self):
        self.assertEqual(set(self.writers), {output.model for output in model_outputs.MODEL_OUTPUTS})

    def test_the_algorithm_filter_finds_the_result_in_each_table(self):
        everything = set(self._occurrences().values_list("pk", flat=True))
        for model, (occurrence, algorithm, _job) in self.written.items():
            with self.subTest(model):
                found = set(self._occurrences().processed_by_algorithm([algorithm.pk]).values_list("pk", flat=True))
                self.assertEqual(found, {occurrence.pk})
                left = set(self._occurrences().not_processed_by_algorithm([algorithm.pk]).values_list("pk", flat=True))
                self.assertEqual(left, everything - {occurrence.pk})

    def test_the_job_filter_finds_the_result_in_each_table(self):
        for model, (occurrence, _algorithm, job) in self.written.items():
            with self.subTest(model):
                found = set(self._occurrences().created_or_updated_by_job(job.pk).values_list("pk", flat=True))
                self.assertEqual(found, {occurrence.pk})

    def test_used_in_project_lists_the_algorithm_that_wrote_to_each_table(self):
        used = set(Algorithm.objects.used_in_project(self.project).values_list("pk", flat=True))
        expected = {algorithm.pk for _occurrence, algorithm, _job in self.written.values()}
        self.assertEqual(used, expected)
        self.assertNotIn(self.unused_algorithm.pk, used)

    def _algorithm_sql(self, *algorithm_ids) -> str:
        return str(self._occurrences().processed_by_algorithm(list(algorithm_ids)).query)

    def test_a_classifier_selection_builds_one_exists_over_detections_and_classifications(self):
        """The common case, one classifier, is a single EXISTS so Postgres can plan a semi-join;
        ORed EXISTS cannot, and make it collect every match in the table before the first page."""
        _occurrence, classifier, _job = self.written["main.Classification"]
        sql = self._algorithm_sql(classifier.pk)
        self.assertEqual(sql.count("EXISTS"), 1)
        self.assertIn("main_classification", sql)
        self.assertNotIn("ml_algorithmresult", sql)

    def test_a_detector_selection_does_not_join_classifications(self):
        _occurrence, detector, _job = self.written["main.Detection"]
        sql = self._algorithm_sql(detector.pk)
        self.assertEqual(sql.count("EXISTS"), 1)
        self.assertNotIn("main_classification", sql)

    def test_an_algorithm_result_only_selection_builds_only_that_exists(self):
        _occurrence, post_processor, _job = self.written["ml.AlgorithmResult"]
        sql = self._algorithm_sql(post_processor.pk)
        self.assertEqual(sql.count("EXISTS"), 1)
        self.assertIn("ml_algorithmresult", sql)
        self.assertNotIn("main_classification", sql)

    def test_an_algorithm_holding_rows_in_two_tables_gets_both_terms(self):
        """Which tables an algorithm wrote to is read from the data: an algorithm that wrote both a
        classification and an algorithm result matches through both tables."""
        occurrence, classifier, job = self.written["main.Classification"]
        extra = self._make_occurrence()
        self._write_algorithm_result(extra, classifier, job)
        sql = self._algorithm_sql(classifier.pk)
        self.assertEqual(sql.count("EXISTS"), 2)
        found = set(self._occurrences().processed_by_algorithm([classifier.pk]).values_list("pk", flat=True))
        self.assertEqual(found, {occurrence.pk, extra.pk})

    def test_a_mixed_selection_ors_the_terms_it_needs(self):
        classified, classifier, _ = self.written["main.Classification"]
        recorded, post_processor, _ = self.written["ml.AlgorithmResult"]
        queryset = self._occurrences().processed_by_algorithm([classifier.pk, post_processor.pk])
        self.assertEqual(set(queryset.values_list("pk", flat=True)), {classified.pk, recorded.pk})
        self.assertEqual(self._algorithm_sql(classifier.pk, post_processor.pk).count("EXISTS"), 2)

    def test_an_algorithm_without_results_matches_nothing(self):
        everything = set(self._occurrences().values_list("pk", flat=True))
        ids = [self.unused_algorithm.pk]
        self.assertEqual(list(self._occurrences().processed_by_algorithm(ids)), [])
        self.assertEqual(
            set(self._occurrences().not_processed_by_algorithm(ids).values_list("pk", flat=True)), everything
        )

    def test_the_algorithm_filter_costs_one_lookup_beside_the_list_query(self):
        """One query finds which tables hold rows for the algorithms; none of the list or count
        queries repeats it. An algorithm without rows needs no query on the occurrences at all.
        Cachalot is off so every query counts."""
        from ami.tests.fixtures.queries import no_query_cache

        _occurrence, classifier, _job = self.written["main.Classification"]

        def filtered(ids):
            return self._occurrences().processed_by_algorithm(ids)

        with no_query_cache():
            with self.assertNumQueries(2):
                list(filtered([classifier.pk]))
            with self.assertNumQueries(2):
                filtered([classifier.pk]).count()
            with self.assertNumQueries(1):
                list(filtered([self.unused_algorithm.pk]))
