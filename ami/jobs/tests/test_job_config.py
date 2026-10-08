from django.test import TestCase

from ami.base.references import Ref, unmapped_reference_types
from ami.jobs.job_config import JobConfigField, job_config_fields
from ami.jobs.models import Job
from ami.main.models import TaxaList
from ami.ml.models import Algorithm
from ami.ml.post_processing.registry import POSTPROCESSING_TASKS
from ami.tests.fixtures.main import setup_test_project


class JobConfigFieldsTestCase(TestCase):
    """A job's config as labelled rows, in its task's schema order, with the records it names resolved."""

    @classmethod
    def setUpTestData(cls) -> None:
        cls.project, _ = setup_test_project(reuse=False)

    def _fields(self, params) -> list[JobConfigField]:
        job = Job.objects.create(project=self.project, name="Run", job_type_key="post_processing", params=params)
        return job_config_fields([job])[job.pk]

    def test_labels_order_and_references_come_from_the_task_config_schema(self):
        taxa_list = TaxaList.objects.create(name="Kept species")
        classifier = Algorithm.objects.create(name="Classifier", key="config-test-classifier")
        config = {
            "reweight": True,
            "algorithm_id": classifier.pk,
            "taxa_list_id": taxa_list.pk,
            "occurrence_id": True,
            "source_image_collection_id": None,
        }
        self.assertEqual(
            self._fields({"task": "class_masking", "config": config}),
            [
                JobConfigField("source_image_collection_id", "Capture set", None, None),
                # A value that is not an id names no record, whatever the schema declares.
                JobConfigField("occurrence_id", "Occurrence", True, None),
                JobConfigField(
                    "taxa_list_id", "Species list", taxa_list.pk, Ref("taxa_list", taxa_list.pk, "Kept species")
                ),
                JobConfigField(
                    "algorithm_id", "Classifier", classifier.pk, Ref("algorithm", classifier.pk, "Classifier")
                ),
                JobConfigField("reweight", "Re-weighted scores", True, None),
            ],
        )

    def test_a_job_without_a_registered_task_shows_its_config_by_key_with_no_references(self):
        self.assertEqual(
            self._fields({"config": {"taxa_list_id": 3, "size_threshold": 0.01}}),
            [
                JobConfigField("taxa_list_id", "taxa_list_id", 3, None),
                JobConfigField("size_threshold", "size_threshold", 0.01),
            ],
        )

    def test_a_job_whose_params_are_not_an_object_has_no_config(self):
        self.assertEqual(self._fields(["not", "an", "object"]), [])

    def test_every_reference_a_task_declares_can_be_resolved(self):
        self.assertEqual(unmapped_reference_types(task.config_schema for task in POSTPROCESSING_TASKS.values()), set())
