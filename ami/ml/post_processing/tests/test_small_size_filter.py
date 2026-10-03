"""What the small size filter writes: a "Not identifiable" classification per flagged detection, in batches."""

import logging

from django.test import TestCase

from ami.jobs.models import Job, PostProcessingJob
from ami.main.models import Detection, Occurrence, SourceImage, Taxon
from ami.ml.post_processing.small_size_filter import SmallSizeFilterTask
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
