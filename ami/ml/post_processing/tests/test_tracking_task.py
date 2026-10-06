import datetime
import logging
import typing
from unittest import mock

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from ami.jobs.models import Job
from ami.main.models import (
    Classification,
    Detection,
    Event,
    Identification,
    Occurrence,
    SourceImageCollection,
    Taxon,
    update_occurrence_determination,
)
from ami.ml.models import Algorithm, AlgorithmResult
from ami.ml.post_processing.registry import get_postprocessing_task
from ami.ml.post_processing.tracking import TrackingTask
from ami.ml.post_processing.tracking import task as task_module
from ami.tests.fixtures.main import create_taxa, setup_test_project
from ami.tests.fixtures.tracking import add_detection, create_session
from ami.users.tests.factories import UserFactory

logger = logging.getLogger(__name__)

BOX = [100, 100, 200, 200]


class _TrackingCase(TestCase):
    def setUp(self) -> None:
        self.project, self.deployment = setup_test_project(reuse=False)
        create_taxa(self.project)
        self.taxa = list(Taxon.objects.filter(projects=self.project, rank="SPECIES").order_by("name"))

    def run_task(self, event: Event, job: Job | None = None, **config) -> TrackingTask:
        task = TrackingTask(job=job, logger=logger, event_ids=[event.pk], **config)
        task.run()
        return task

    def occurrence_sizes(self, event: Event) -> list[int]:
        return sorted(o.detections.count() for o in Occurrence.objects.filter(event=event))


class TestRegistration(TestCase):
    def test_task_is_registered(self):
        self.assertIs(get_postprocessing_task("tracking"), TrackingTask)


class TestTrackingRun(_TrackingCase):
    def test_a_still_insect_is_folded_into_one_occurrence(self):
        captures = create_session(self.deployment, [[BOX], [BOX], [BOX]], self.taxa[0])
        event = captures[0].event
        self.assertEqual(Occurrence.objects.filter(event=event).count(), 3)

        self.run_task(event)

        self.assertEqual(self.occurrence_sizes(event), [3])
        self.assertEqual(Detection.objects.filter(source_image__event=event, next_detection__isnull=False).count(), 2)
        event.refresh_from_db()
        self.assertEqual(event.occurrences_count, 1)

    def test_an_unprocessed_capture_between_processed_ones_does_not_break_the_chain(self):
        captures = create_session(self.deployment, [[BOX], None, [BOX]], self.taxa[0])
        event = captures[0].event

        self.run_task(event)

        self.assertEqual(self.occurrence_sizes(event), [2])

    def test_a_processed_capture_with_no_insects_is_part_of_the_sequence(self):
        """A null-bbox marker row makes a capture processed, so the empty capture separates its neighbours."""
        captures = create_session(self.deployment, [[BOX], [], [BOX]], self.taxa[0])
        event = captures[0].event

        self.run_task(event)

        self.assertEqual(self.occurrence_sizes(event), [1, 1])

    def test_the_interval_limit_stops_links_across_a_long_gap(self):
        captures = create_session(self.deployment, [[BOX], [BOX], [BOX]], self.taxa[0], interval_seconds=60)
        event = captures[0].event
        job = Job.objects.create(name="t", project=self.project, job_type_key="post_processing")
        job.progress.add_stage("Post-processing", key="post_processing")
        job.save()

        self.run_task(event, job=job, max_capture_interval_seconds=30)

        self.assertEqual(self.occurrence_sizes(event), [1, 1, 1])
        job.refresh_from_db()
        params = {p.name: p.value for p in job.progress.get_stage("post_processing").params}
        self.assertEqual(params["Capture pairs too far apart to compare"], 2)

    def test_a_chain_stops_at_a_session_boundary(self):
        """A link stored between two sessions never merges their occurrences."""
        day = datetime.datetime(2026, 7, 1, 22, 0, 0)
        first = create_session(self.deployment, [[BOX], [BOX]], self.taxa[0], start=day)
        second = create_session(self.deployment, [[BOX], [BOX]], self.taxa[0], start=day + datetime.timedelta(hours=6))
        self.assertNotEqual(first[0].event_id, second[0].event_id)
        last_of_first = first[1].detections.get()
        first_of_second = second[0].detections.get()
        last_of_first.next_detection = first_of_second
        last_of_first.save(update_fields=["next_detection"])

        for event in (first[0].event, second[0].event):
            self.run_task(event)

        self.assertEqual(self.occurrence_sizes(first[0].event), [2])
        self.assertEqual(self.occurrence_sizes(second[0].event), [2])
        first_of_second.refresh_from_db()
        self.assertNotEqual(first_of_second.occurrence_id, first[0].detections.get().occurrence_id)

    def test_a_session_with_a_single_processed_capture_is_skipped_with_a_reason(self):
        captures = create_session(self.deployment, [[BOX], None], self.taxa[0])
        job = Job.objects.create(name="t", project=self.project, job_type_key="post_processing")
        job.progress.add_stage("Post-processing", key="post_processing")
        job.save()

        self.run_task(captures[0].event, job=job)

        job.refresh_from_db()
        params = {p.name: p.value for p in job.progress.get_stage("post_processing").params}
        self.assertEqual(params["Sessions skipped"], 1)
        self.assertIn("fewer than two processed captures", params["Result"])


class TestGuards(_TrackingCase):
    def test_a_session_that_was_already_tracked_is_skipped_unless_the_guard_is_off(self):
        # The third capture is processed after the first run, with an insect that follows the others.
        captures = create_session(self.deployment, [[BOX], [BOX], None], self.taxa[0])
        event = captures[0].event
        self.run_task(event)
        add_detection(captures[2], BOX, self.taxa[0])
        self.assertEqual(self.occurrence_sizes(event), [1, 2])

        self.run_task(event)
        self.assertEqual(self.occurrence_sizes(event), [1, 2])

        self.run_task(event, require_fresh_event=False)
        self.assertEqual(self.occurrence_sizes(event), [3])

    def test_human_identifications_skip_the_session_unless_the_guard_is_off(self):
        captures = create_session(self.deployment, [[BOX], [BOX]], self.taxa[0])
        event = captures[0].event
        occurrence = Occurrence.objects.filter(event=event).first()
        Identification.objects.create(user=UserFactory(), taxon=self.taxa[1], occurrence=occurrence)

        self.run_task(event)
        self.assertEqual(self.occurrence_sizes(event), [1, 1])

        self.run_task(event, skip_if_human_identifications=False)
        self.assertEqual(self.occurrence_sizes(event), [2])


class TestMerging(_TrackingCase):
    def test_identifications_move_onto_the_keeper_instead_of_being_deleted(self):
        captures = create_session(self.deployment, [[BOX], [BOX], [BOX]], self.taxa[0])
        event = captures[0].event
        user = UserFactory()
        for occurrence in Occurrence.objects.filter(event=event):
            Identification.objects.create(user=user, taxon=self.taxa[1], occurrence=occurrence)

        self.run_task(event, skip_if_human_identifications=False)

        keeper = Occurrence.objects.get(event=event)
        self.assertEqual(keeper.detections.count(), 3)
        self.assertEqual(Identification.objects.filter(user=user).count(), 3)
        self.assertEqual(set(Identification.objects.values_list("occurrence_id", flat=True)), {keeper.pk})

    def _two_detection_chain(self, first_score: float, second_score: float):
        captures = create_session(self.deployment, [[BOX], [BOX]], self.taxa[0])
        first, second = (c.detections.get() for c in captures)
        for det, taxon, score in ((first, self.taxa[0], first_score), (second, self.taxa[1], second_score)):
            Classification.objects.filter(detection=det).update(taxon=taxon, score=score)
            det.occurrence.save()
        first.next_detection = second
        first.save(update_fields=["next_detection"])
        return captures, first, second

    def test_class_masking_after_tracking_still_changes_the_determination(self):
        """A later re-scoring replaces a merged occurrence's determination, because tracking adds no classification."""
        captures, first, second = self._two_detection_chain(first_score=0.3, second_score=0.9)
        self.run_task(captures[0].event)
        occurrence = Occurrence.objects.get(pk=first.occurrence_id)
        self.assertEqual(occurrence.determination, self.taxa[1])
        self.assertFalse(Classification.objects.filter(algorithm__key="tracking").exists())

        # What class masking does: demote the source rows and add a terminal row naming another taxon.
        masker = Algorithm.objects.create(name="Test masking", key="test-masking")
        for source in Classification.objects.filter(detection__occurrence=occurrence, terminal=True):
            source.terminal = False
            source.save(update_fields=["terminal"])
            Classification.objects.create(
                detection=source.detection,
                taxon=self.taxa[2],
                score=0.5,
                terminal=True,
                algorithm=masker,
                applied_to=source,
                timestamp=source.timestamp,
            )
        occurrence = Occurrence.objects.get(pk=occurrence.pk)
        update_occurrence_determination(occurrence, save=True)

        occurrence.refresh_from_db()
        self.assertEqual(occurrence.determination, self.taxa[2])


class TestTrackingResults(_TrackingCase):
    def make_job(self) -> Job:
        job = Job.objects.create(name="t", project=self.project, job_type_key="post_processing")
        job.progress.add_stage("Post-processing", key="post_processing")
        job.save()
        return job

    def test_each_linked_occurrence_gets_a_result_with_its_figures(self):
        moving, still, lone = [100, 100, 200, 200], [700, 700, 800, 800], [400, 800, 420, 820]
        captures = create_session(
            self.deployment,
            [[moving, still], [[110, 100, 210, 200], still], [[120, 100, 220, 200], still, lone]],
            self.taxa[0],
        )
        event = captures[0].event
        job = self.make_job()

        task = self.run_task(event, job=job)

        results = {r.occurrence_id: r for r in AlgorithmResult.objects.filter(kind="tracking")}
        self.assertEqual(len(results), 2)
        self.assertNotIn(captures[2].detections.get(bbox=lone).occurrence_id, results)
        by_motion = sorted(results.values(), key=lambda r: r.value)
        still_result, moving_result = by_motion
        self.assertEqual(still_result.value, 0.0)
        self.assertEqual(still_result.data["path_length"], 0.0)
        # The box centre moves 10 px per step on a 1,000 x 1,000 capture.
        self.assertEqual(moving_result.value, 0.0071)
        self.assertEqual(moving_result.data["path_length"], 0.0141)
        for result in by_motion:
            self.assertEqual(
                (result.job_id, result.algorithm_id, result.is_current), (job.pk, task.algorithm.pk, True)
            )
            self.assertEqual(result.project_id, self.project.pk)
            self.assertEqual(result.data["detection_count"], 3)
            self.assertEqual(result.data["size_change"], 1.0)
            self.assertEqual(result.data["distinct_taxa"], 1)
            self.assertEqual(result.data["label_agreement"], 1.0)
            self.assertEqual(len(result.data["link_costs"]), 2)
            self.assertEqual(result.data["determination_after_id"], self.taxa[0].pk)
            self.assertEqual(len(result.data["merged_occurrence_ids"]), 2)
        job.refresh_from_db()
        params = {p.name: p.value for p in job.progress.get_stage("post_processing").params}
        self.assertEqual(params["Occurrences recorded"], 2)

    def test_figures_follow_the_labels_and_boxes_of_the_merged_detections(self):
        captures = create_session(self.deployment, [[[100, 100, 400, 400]], [[100, 100, 390, 400]]], self.taxa[0])
        second = captures[1].detections.get()
        Classification.objects.filter(detection=second).update(taxon=self.taxa[1], score=0.6)
        second.occurrence.save()

        self.run_task(captures[0].event)

        result = AlgorithmResult.objects.get(kind="tracking")
        self.assertEqual(result.data["distinct_taxa"], 2)
        self.assertEqual(result.data["size_change"], round(300 * 300 / (290 * 300), 4))
        self.assertEqual(result.data["label_agreement"], 0.5)
        self.assertEqual(result.data["determination_before_id"], self.taxa[0].pk)

    def test_the_result_records_the_determination_before_and_after_without_a_classification(self):
        captures = create_session(self.deployment, [[BOX], [BOX]], self.taxa[0])
        for capture, taxon, score in zip(captures, self.taxa, (0.3, 0.9)):
            Classification.objects.filter(detection__source_image=capture).update(taxon=taxon, score=score)
            capture.detections.get().occurrence.save()
        job = self.make_job()

        task = self.run_task(captures[0].event, job=job)

        result = AlgorithmResult.objects.get(kind="tracking")
        self.assertEqual(result.data["determination_after_id"], self.taxa[1].pk)
        self.assertEqual(result.data["determination_before_id"], self.taxa[0].pk)
        self.assertFalse(Classification.objects.filter(algorithm=task.algorithm).exists())

    def test_machine_labels_leave_out_post_processing_classifications(self):
        """A size filter's terminal row on a frame is not another vote on the taxon."""
        captures = create_session(self.deployment, [[BOX], [BOX]], self.taxa[0])
        size_filter = Algorithm.objects.create(
            name="Test size filter", key="test-size-filter", task_type="post_processing"
        )
        second = captures[1].detections.get()
        Classification.objects.create(
            detection=second,
            taxon=self.taxa[1],
            score=1.0,
            terminal=True,
            algorithm=size_filter,
            timestamp=second.timestamp,
        )

        self.run_task(captures[0].event)

        result = AlgorithmResult.objects.get(kind="tracking")
        self.assertEqual(result.data["distinct_taxa"], 1)
        # The filter's row wins the determination, and no machine label names that taxon.
        self.assertEqual(result.data["determination_after_id"], self.taxa[1].pk)
        self.assertEqual(result.data["label_agreement"], 0.0)

    def test_each_links_cost_is_recorded_in_chain_order(self):
        captures = create_session(
            self.deployment, [[BOX], [[110, 100, 210, 200]], [[130, 100, 230, 200]]], self.taxa[0]
        )

        self.run_task(captures[0].event)

        costs = AlgorithmResult.objects.get(kind="tracking").data["link_costs"]
        self.assertEqual(len(costs), 2)
        self.assertTrue(all(isinstance(cost, float) and cost > 0 for cost in costs))
        self.assertLess(costs[0], costs[1])

    def test_results_of_merged_occurrences_move_onto_the_keeper(self):
        captures = create_session(self.deployment, [[BOX], [BOX]], self.taxa[0])
        first, second = (c.detections.get().occurrence for c in captures)
        filter_algorithm = Algorithm.objects.create(name="Test filter", key="test-filter")
        earlier = AlgorithmResult.objects.record(
            occurrence=second, algorithm=filter_algorithm, kind="size_filter", data={"relative_size": 0.01}
        )

        self.run_task(captures[0].event)

        earlier.refresh_from_db()
        self.assertEqual((earlier.occurrence_id, earlier.is_current), (first.pk, True))
        self.assertFalse(Occurrence.objects.filter(pk=second.pk).exists())
        tracking = AlgorithmResult.objects.get(kind="tracking")
        self.assertEqual(tracking.occurrence_id, first.pk)
        self.assertEqual(tracking.data["merged_occurrence_ids"], [second.pk])

    def test_a_session_without_links_records_no_results(self):
        captures = create_session(self.deployment, [[[0, 0, 50, 50]], [[900, 900, 950, 950]]], self.taxa[0])

        self.run_task(captures[0].event)

        self.assertFalse(AlgorithmResult.objects.exists())


class TestTrackingJobMetrics(_TrackingCase):
    def test_result_line_says_what_was_tracked(self):
        captures = create_session(self.deployment, [[BOX], [BOX]], self.taxa[0])
        job = Job.objects.create(name="t", project=self.project, job_type_key="post_processing")
        job.progress.add_stage("Post-processing", key="post_processing")
        job.save()

        self.run_task(captures[0].event, job=job)

        job.refresh_from_db()
        params: dict[str, typing.Any] = {p.name: p.value for p in job.progress.get_stage("post_processing").params}
        self.assertEqual(params["Sessions tracked"], 1)
        self.assertEqual(params["Detection links created"], 1)
        self.assertEqual(params["Result"], "Tracked 1 session(s).")


class TestTrackingScope(_TrackingCase):
    def test_a_capture_set_tracks_every_processed_capture_of_the_sessions_it_touches(self):
        captures = create_session(self.deployment, [[BOX], [BOX], [BOX]], self.taxa[0])
        collection = SourceImageCollection.objects.create(name="Sampled", project=self.project)
        collection.images.add(captures[0])

        task = TrackingTask(job=None, logger=logger, source_image_collection_id=collection.pk)
        task.run()

        self.assertEqual(self.occurrence_sizes(captures[0].event), [3])

    def test_a_session_of_another_project_is_not_tracked_for_a_job(self):
        captures = create_session(self.deployment, [[BOX], [BOX]], self.taxa[0])
        other_project, _ = setup_test_project(reuse=False)
        job = Job.objects.create(name="t", project=other_project, job_type_key="post_processing")
        job.progress.add_stage("Post-processing", key="post_processing")
        job.save()

        self.run_task(captures[0].event, job=job)

        self.assertEqual(self.occurrence_sizes(captures[0].event), [1, 1])


class TestTrackingFailures(_TrackingCase):
    def make_job(self) -> Job:
        job = Job.objects.create(name="t", project=self.project, job_type_key="post_processing")
        job.progress.add_stage("Post-processing", key="post_processing")
        job.save()
        return job

    def test_a_failing_session_is_counted_and_the_others_are_still_tracked(self):
        day = datetime.datetime(2026, 7, 1, 22, 0, 0)
        first = create_session(self.deployment, [[BOX], [BOX]], self.taxa[0], start=day)
        second = create_session(self.deployment, [[BOX], [BOX]], self.taxa[0], start=day + datetime.timedelta(hours=6))
        failing, working = first[0].event, second[0].event
        self.assertNotEqual(failing.pk, working.pk)
        job = self.make_job()
        real = task_module.assign_occurrences_by_tracking_images

        def fail_for_the_first_session(event, *args, **kwargs):
            if event.pk == failing.pk:
                # Written before the failure, so the rollback of this session is visible.
                Occurrence.objects.filter(event=event).update(determination_score=0.123)
                raise ValueError("boom")
            return real(event, *args, **kwargs)

        with mock.patch.object(task_module, "assign_occurrences_by_tracking_images", fail_for_the_first_session):
            with self.assertRaisesMessage(RuntimeError, "Tracking failed for 1 of 2 session(s)"):
                TrackingTask(job=job, logger=logger, event_ids=[failing.pk, working.pk]).run()

        self.assertEqual(self.occurrence_sizes(working), [2])
        self.assertEqual(self.occurrence_sizes(failing), [1, 1])
        self.assertFalse(Occurrence.objects.filter(event=failing, determination_score=0.123).exists())
        working.refresh_from_db()
        self.assertEqual(working.occurrences_count, 1)
        job.refresh_from_db()
        params = {p.name: p.value for p in job.progress.get_stage("post_processing").params}
        self.assertEqual((params["Sessions tracked"], params["Sessions failed"]), (1, 1))
        self.assertIn("failed for 1 of 2", params["Result"])

    def test_progress_is_saved_between_sessions_not_inside_their_transactions(self):
        day = datetime.datetime(2026, 7, 1, 22, 0, 0)
        first = create_session(self.deployment, [[BOX], [BOX]], self.taxa[0], start=day)
        second = create_session(self.deployment, [[BOX], [BOX]], self.taxa[0], start=day + datetime.timedelta(hours=6))
        job = self.make_job()
        depths = []

        def record_depth(progress: float) -> None:
            depths.append((round(progress, 2), len(connection.savepoint_ids)))

        task = TrackingTask(job=job, logger=logger, event_ids=[first[0].event_id, second[0].event_id])
        baseline = len(connection.savepoint_ids)
        with mock.patch.object(task, "update_progress", record_depth):
            task.run()

        self.assertEqual(depths, [(0.5, baseline), (1.0, baseline), (1.0, baseline)])


class TestTrackingQueries(_TrackingCase):
    def count_queries(self, boxes_per_capture: list[list[list[int]] | None], start: datetime.datetime) -> int:
        from cachalot.api import cachalot_disabled

        captures = create_session(self.deployment, boxes_per_capture, self.taxa[0], start=start)
        disabled = cachalot_disabled()
        disabled.__enter__()
        try:
            with CaptureQueriesContext(connection) as queries:
                self.run_task(captures[0].event)
        finally:
            # cachalot_disabled() does not restore itself when the block raises.
            disabled.__exit__(None, None, None)
        self.assertEqual(self.occurrence_sizes(captures[0].event), [len(boxes_per_capture)])
        return len(queries)

    def test_queries_grow_by_a_constant_per_capture_not_per_detection(self):
        """Each extra capture adds a fixed number of queries; reassigning a chain's detections is one update."""
        self.count_queries([[BOX]] * 3, datetime.datetime(2026, 6, 30))  # warms per-process caches
        counts = [
            self.count_queries([[BOX]] * n, datetime.datetime(2026, 7, day)) for day, n in ((1, 3), (2, 6), (3, 9))
        ]
        self.assertEqual(counts[2] - counts[1], counts[1] - counts[0])
        per_capture = (counts[1] - counts[0]) // 3
        self.assertLessEqual(per_capture, 4)
