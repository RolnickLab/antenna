"""What the small size filter writes: a "Not identifiable" classification per flagged detection, in batches."""

import logging
from unittest import mock

from django.test import TestCase

from ami.jobs.models import Job, PostProcessingJob
from ami.main.models import Detection, Occurrence, SourceImage, Taxon
from ami.ml.models import AlgorithmResult
from ami.ml.post_processing.small_size_filter import SmallSizeFilterTask
from ami.ml.results.schemas import SizeFilterResultData
from ami.tests.fixtures.main import create_captures, create_taxa, setup_test_project

logger = logging.getLogger(__name__)


class SizeFilterTestCase(TestCase):
    def setUp(self) -> None:
        self.project, self.deployment = setup_test_project(reuse=False)
        create_taxa(project=self.project)
        create_captures(deployment=self.deployment, num_nights=1, images_per_night=3, interval_minutes=1)
        self.captures = list(SourceImage.objects.filter(deployment=self.deployment).order_by("timestamp"))
        SourceImage.objects.filter(pk__in=[c.pk for c in self.captures]).update(width=1000, height=1000)
        self.event = self.captures[0].event
        self.taxon = Taxon.objects.filter(projects=self.project).order_by("pk").first()

    def _singleton(self, capture: SourceImage, bbox: list[int]) -> Occurrence:
        """One detection in an occurrence of its own, classified as the fixture taxon."""
        occurrence = Occurrence.objects.create(event=self.event, deployment=self.deployment, project=self.project)
        detection = Detection.objects.create(
            source_image=capture, bbox=bbox, timestamp=capture.timestamp, occurrence=occurrence
        )
        detection.classifications.create(taxon=self.taxon, score=0.9, timestamp=capture.timestamp)
        occurrence.save()
        return occurrence

    def run_filter(self, occurrence: Occurrence, **kwargs) -> None:
        SmallSizeFilterTask(logger=logger, occurrence_id=occurrence.pk, size_threshold=0.01, **kwargs).run()


class SizeFilterBatchTestCase(SizeFilterTestCase):
    def test_a_skipped_last_detection_still_saves_the_batch_before_it(self):
        """A detection the scan skips (no box) must not swallow the flagged ones gathered before it."""
        occurrence = self._singleton(self.captures[0], [0, 0, 10, 10])
        # Inserted last, so the scan reaches it last; it has no box and is skipped.
        Detection.objects.create(
            source_image=self.captures[1], bbox=None, timestamp=self.captures[1].timestamp, occurrence=occurrence
        )

        self.run_filter(occurrence)

        occurrence.refresh_from_db()
        self.assertEqual(occurrence.determination.name, "Not identifiable")

    def test_a_detection_above_the_threshold_is_left_alone(self):
        occurrence = self._singleton(self.captures[0], [0, 0, 500, 500])
        self.run_filter(occurrence)
        occurrence.refresh_from_db()
        self.assertEqual(occurrence.determination, self.taxon)
        self.assertEqual(occurrence.detections.get().classifications.count(), 1)


class SizeFilterJobTestCase(SizeFilterTestCase):
    def _job(self, occurrence: Occurrence, **config) -> Job:
        return Job.objects.create(
            project=self.project,
            name="Size filter",
            job_type_key="post_processing",
            params={"task": "small_size_filter", "config": {"occurrence_id": occurrence.pk, **config}},
        )

    def test_the_job_stores_the_settings_the_run_used_with_their_defaults(self):
        occurrence = self._singleton(self.captures[0], [0, 0, 10, 10])
        job = self._job(occurrence)

        PostProcessingJob.run(job)

        job.refresh_from_db()
        self.assertEqual(
            job.params["config"],
            {"occurrence_id": occurrence.pk, "source_image_collection_id": None, "size_threshold": 0.0008},
        )
        self.assertEqual(job.status, "SUCCESS")

    def test_a_run_records_its_job_on_each_classification_it_writes(self):
        occurrence = self._singleton(self.captures[0], [0, 0, 10, 10])
        job = self._job(occurrence, size_threshold=0.01)

        PostProcessingJob.run(job)

        classification = occurrence.detections.get().classifications.get(taxon__name="Not identifiable")
        self.assertEqual(classification.job_id, job.pk)
        self.assertEqual(job.classifications.get().pk, classification.pk)
        self.assertEqual(job.algorithm_results.get().pk, classification.algorithm_result_id)


class SizeFilterResultsTestCase(SizeFilterTestCase):
    """The size filter leaves one algorithm result per occurrence it flags, written with the batch that flags it."""

    def records(self):
        return AlgorithmResult.objects.filter(kind=SizeFilterResultData.kind).order_by("pk")

    def test_a_flagged_occurrence_gets_one_result_linked_to_the_classifications_it_created(self):
        occurrence = self._singleton(self.captures[0], [0, 0, 10, 10])
        Detection.objects.create(
            source_image=self.captures[1],
            bbox=[0, 0, 12, 12],
            timestamp=self.captures[1].timestamp,
            occurrence=occurrence,
        )

        self.run_filter(occurrence)

        result = self.records().get()
        detection_ids = sorted(occurrence.detections.values_list("pk", flat=True))
        self.assertEqual((result.occurrence_id, result.project_id), (occurrence.pk, self.project.pk))
        self.assertEqual(result.algorithm.key, "small_size_filter")
        self.assertIn(result.kind, {model.kind for model in SmallSizeFilterTask.result_models})
        # The smallest flagged detection, 10 by 10 pixels on a 1000 by 1000 image, represents the occurrence.
        self.assertAlmostEqual(result.value, 0.0001)
        self.assertAlmostEqual(result.data.pop("relative_size"), 0.0001)
        self.assertEqual(
            result.data,
            {
                "determination_before_id": self.taxon.pk,
                "determination_after_id": Taxon.objects.get(name="Not identifiable").pk,
                "extra": {},
            },
        )
        self.assertEqual(sorted(result.classifications.values_list("detection_id", flat=True)), detection_ids)

    def test_a_second_run_replaces_the_current_result_and_keeps_the_first(self):
        occurrence = self._singleton(self.captures[0], [0, 0, 10, 10])
        for _ in range(2):
            self.run_filter(occurrence)
        first, second = self.records()
        self.assertEqual((first.is_current, second.is_current), (False, True))

    def test_an_occurrence_with_nothing_flagged_gets_no_result(self):
        occurrence = self._singleton(self.captures[0], [0, 0, 500, 500])
        self.run_filter(occurrence)
        self.assertFalse(self.records().exists())

    def test_a_batch_that_fails_leaves_neither_its_classifications_nor_its_result(self):
        occurrence = self._singleton(self.captures[0], [0, 0, 10, 10])

        with mock.patch.object(Occurrence, "save", side_effect=RuntimeError("determination update failed")):
            with self.assertRaises(RuntimeError):
                self.run_filter(occurrence)

        self.assertFalse(self.records().exists())
        self.assertFalse(occurrence.detections.get().classifications.filter(taxon__name="Not identifiable").exists())
