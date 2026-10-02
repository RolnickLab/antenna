"""Tracking and the small size filter leave one algorithm result per occurrence they change, and none otherwise.

Class masking's results are covered in test_class_masking.py, next to its other tests.
"""

import logging

from django.test import TestCase

from ami.jobs.models import Job
from ami.main.models import AlgorithmResult, Detection, Occurrence, SourceImage, Taxon, ValidationReview
from ami.ml.models import Algorithm
from ami.ml.post_processing.small_size_filter import SmallSizeFilterTask
from ami.ml.post_processing.tracking_task import (
    TrackingResults,
    TrackingTask,
    assign_occurrences_from_detection_chains,
)
from ami.tests.fixtures.main import create_captures, create_taxa, setup_test_project

logger = logging.getLogger(__name__)


class HistoryWriterFixture(TestCase):
    """Three consecutive captures in one session, each with dimensions, and a project taxon."""

    def setUp(self) -> None:
        self.project, self.deployment = setup_test_project(reuse=False)
        create_taxa(project=self.project)
        create_captures(deployment=self.deployment, num_nights=1, images_per_night=3, interval_minutes=1)
        self.captures = list(SourceImage.objects.filter(deployment=self.deployment).order_by("timestamp"))
        SourceImage.objects.filter(pk__in=[c.pk for c in self.captures]).update(width=1000, height=1000)
        for capture in self.captures:
            capture.width = capture.height = 1000
        self.event = self.captures[0].event
        self.taxon = Taxon.objects.filter(projects=self.project).order_by("pk").first()

    def _singleton(self, capture: SourceImage, bbox: list[int], score: float = 0.9) -> Occurrence:
        """One detection in an occurrence of its own, classified as the fixture taxon."""
        occurrence = Occurrence.objects.create(event=self.event, deployment=self.deployment, project=self.project)
        detection = Detection.objects.create(
            source_image=capture, bbox=bbox, timestamp=capture.timestamp, occurrence=occurrence
        )
        detection.classifications.create(taxon=self.taxon, score=score, timestamp=capture.timestamp)
        occurrence.save()
        return occurrence

    def records(self, kind: str):
        return AlgorithmResult.objects.filter(kind=kind).order_by("pk")


class TrackingHistoryTestCase(HistoryWriterFixture):
    def test_a_merged_track_gets_one_record_and_an_untouched_occurrence_none(self):
        track = [self._singleton(capture, [100, 100, 150, 150]) for capture in self.captures]
        loner = self._singleton(self.captures[1], [800, 800, 820, 820])

        TrackingTask(logger=logger, event_ids=[self.event.pk], require_features=False, cost_threshold=0.5).run()

        record = self.records("tracking").get()
        keeper = Occurrence.objects.get(detections__source_image=self.captures[0])
        self.assertEqual(record.occurrence_id, keeper.pk)
        self.assertNotEqual(record.occurrence_id, loner.pk)
        self.assertEqual(record.algorithm.key, "tracking")
        self.assertEqual(record.project_id, self.project.pk)
        self.assertTrue(record.is_current)
        payload = record.data
        self.assertEqual(payload["detections_count"], 3)
        self.assertEqual(payload["frames_linked"], 2)
        self.assertEqual(payload["occurrences_merged"], sorted(o.pk for o in track if o.pk != keeper.pk))
        self.assertIsNone(payload["feature_algorithm_id"])
        self.assertEqual(payload["settings"]["cost_threshold"], 0.5)
        self.assertNotIn("event_ids", payload["settings"])
        self.assertIsNotNone(payload["cost_mean"])
        self.assertLessEqual(payload["cost_mean"], payload["cost_max"])
        self.assertEqual(payload["taxon_before_id"], self.taxon.pk)
        self.assertEqual(payload["taxon_after_id"], self.taxon.pk)

    def test_two_chains_settling_on_one_occurrence_give_it_one_record(self):
        """An occurrence that already held detections of two chains keeps both; it gets one result, not two."""
        keeper = self._singleton(self.captures[0], [100, 100, 150, 150])
        first = keeper.detections.get()
        second_on_keeper = Detection.objects.create(
            source_image=self.captures[1], bbox=[500, 500, 550, 550], timestamp=self.captures[1].timestamp
        )
        Detection.objects.filter(pk=second_on_keeper.pk).update(occurrence=keeper)
        joined = [self._singleton(capture, [100, 100, 150, 150]) for capture in self.captures[1:]]
        Detection.objects.filter(pk=first.pk).update(next_detection=joined[0].detections.get())
        Detection.objects.filter(pk=second_on_keeper.pk).update(next_detection=joined[1].detections.get())
        tracking = Algorithm.objects.create(name="Tracking", key="tracking-two-chains-test")

        assign_occurrences_from_detection_chains(
            self.captures, logger, results=TrackingResults(algorithm=tracking, settings={})
        )

        record = self.records("tracking").get()
        self.assertEqual(record.occurrence_id, keeper.pk)
        self.assertEqual(record.data["detections_count"], 4)
        self.assertEqual(record.data["occurrences_merged"], sorted(o.pk for o in joined))

    def test_a_run_that_changes_nothing_writes_nothing(self):
        for capture in self.captures:
            self._singleton(capture, [100, 100, 150, 150])
        TrackingTask(logger=logger, event_ids=[self.event.pk], require_features=False, cost_threshold=0.5).run()
        self.assertEqual(self.records("tracking").count(), 1)

        TrackingTask(
            logger=logger,
            event_ids=[self.event.pk],
            require_features=False,
            require_fresh_event=False,
            skip_if_human_identifications=False,
            cost_threshold=0.5,
        ).run()
        self.assertEqual(self.records("tracking").count(), 1)

    def test_a_merged_occurrence_hands_its_results_and_reviews_to_the_keeper(self):
        first, second = (self._singleton(capture, [100, 100, 150, 150]) for capture in self.captures[:2])
        size_filter = AlgorithmResult.objects.record(
            occurrence=second,
            algorithm=Algorithm.objects.create(name="Size filter", key="size-filter-merge-test"),
            kind=AlgorithmResult.Kind.SIZE_FILTER,
            data={"size_threshold": 0.001, "detection_ids": []},
        )
        comment = ValidationReview.objects.create(occurrence=second, aspect="comment", comment="x")
        TrackingTask(logger=logger, event_ids=[self.event.pk], require_features=False, cost_threshold=0.5).run()

        size_filter.refresh_from_db()
        comment.refresh_from_db()
        self.assertEqual((size_filter.occurrence_id, size_filter.is_current), (first.pk, False))
        self.assertEqual(comment.occurrence_id, first.pk)

    def test_a_run_records_its_job_on_each_result(self):
        for capture in self.captures:
            self._singleton(capture, [100, 100, 150, 150])
        job = Job.objects.create(project=self.project, name="Tracking job", job_type_key="post_processing")
        job.progress.add_stage("Post-processing", key="post_processing")
        job.save()
        TrackingTask(job=job, event_ids=[self.event.pk], require_features=False, cost_threshold=0.5).run()
        self.assertEqual(self.records("tracking").get().job_id, job.pk)
        self.assertTrue(job.has_stored_outputs())


class SizeFilterHistoryTestCase(HistoryWriterFixture):
    def test_an_occurrence_with_a_flagged_detection_gets_one_record(self):
        occurrence = self._singleton(self.captures[0], [0, 0, 10, 10])
        Detection.objects.create(
            source_image=self.captures[1],
            bbox=[0, 0, 12, 12],
            timestamp=self.captures[1].timestamp,
            occurrence=occurrence,
        )

        SmallSizeFilterTask(logger=logger, occurrence_id=occurrence.pk, size_threshold=0.01).run()

        record = self.records("size_filter").get()
        self.assertEqual(record.occurrence_id, occurrence.pk)
        self.assertEqual(record.algorithm.key, "small_size_filter")
        self.assertEqual(record.data["detection_ids"], sorted(occurrence.detections.values_list("pk", flat=True)))
        self.assertEqual(record.data["size_threshold"], 0.01)
        self.assertEqual(record.data["taxon_before_id"], self.taxon.pk)
        self.assertEqual(record.data["taxon_after_id"], Taxon.objects.get(name="Not identifiable").pk)

    def test_a_second_run_replaces_the_current_result_and_keeps_the_first(self):
        occurrence = self._singleton(self.captures[0], [0, 0, 10, 10])
        for _ in range(2):
            SmallSizeFilterTask(logger=logger, occurrence_id=occurrence.pk, size_threshold=0.01).run()
        first, second = self.records("size_filter")
        self.assertEqual((first.is_current, second.is_current), (False, True))

    def test_an_occurrence_with_nothing_flagged_gets_no_record(self):
        occurrence = self._singleton(self.captures[0], [0, 0, 500, 500])
        SmallSizeFilterTask(logger=logger, occurrence_id=occurrence.pk, size_threshold=0.01).run()
        self.assertFalse(self.records("size_filter").exists())

    def test_a_skipped_last_detection_still_saves_the_batch_before_it(self):
        occurrence = self._singleton(self.captures[0], [0, 0, 10, 10])
        # Inserted last, so the scan reaches it last; it has no box and is skipped.
        Detection.objects.create(
            source_image=self.captures[1], bbox=None, timestamp=self.captures[1].timestamp, occurrence=occurrence
        )

        SmallSizeFilterTask(logger=logger, occurrence_id=occurrence.pk, size_threshold=0.01).run()

        occurrence.refresh_from_db()
        self.assertEqual(occurrence.determination.name, "Not identifiable")
        self.assertEqual(self.records("size_filter").get().data["taxon_after_id"], occurrence.determination_id)
