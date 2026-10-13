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
from ami.ml.models import Algorithm, AlgorithmResult, DetectionEmbedding
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
            "ml.DetectionEmbedding": self._write_detection_embedding,
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

    def _write_detection_embedding(self, occurrence, algorithm, job):
        DetectionEmbedding.objects.store(
            [
                DetectionEmbedding(
                    detection=self._make_detection(occurrence), algorithm=algorithm, vector=[0.5] * 4, job=job
                )
            ]
        )

    def _occurrences(self):
        return Occurrence.objects.filter(project=self.project)

    def test_a_writer_exists_for_every_registered_table(self):
        self.assertEqual(set(self.writers), {output.model for output in model_outputs.MODEL_OUTPUTS})

    def test_the_job_filter_finds_the_result_in_each_table(self):
        for model, (occurrence, _algorithm, job) in self.written.items():
            with self.subTest(model):
                found = set(self._occurrences().created_or_updated_by_job(job.pk).values_list("pk", flat=True))
                self.assertEqual(found, {occurrence.pk})
