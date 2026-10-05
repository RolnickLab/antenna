import datetime
import logging
import typing

from django.test import TestCase

from ami.jobs.models import Job
from ami.main.models import Classification, Detection, Event, Identification, Occurrence, Taxon
from ami.ml.models import Algorithm
from ami.ml.post_processing.registry import get_postprocessing_task
from ami.ml.post_processing.tracking import TrackingTask
from ami.ml.post_processing.tracking.task import assign_occurrences_from_detection_chains
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

    def test_two_insects_are_matched_one_to_one_by_lowest_cost(self):
        left, right = [100, 100, 200, 200], [700, 700, 800, 800]
        captures = create_session(
            self.deployment, [[left, right], [[110, 100, 210, 200], [705, 700, 805, 800]]], self.taxa[0]
        )
        self.run_task(captures[0].event)
        self.assertEqual(self.occurrence_sizes(captures[0].event), [2, 2])

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
        captures = create_session(self.deployment, [[BOX], [BOX]], self.taxa[0])
        event = captures[0].event
        self.run_task(event)
        add_detection(captures[1], [500, 500, 560, 560], self.taxa[0])
        self.assertEqual(self.occurrence_sizes(event), [1, 2])

        self.run_task(event)
        self.assertEqual(self.occurrence_sizes(event), [1, 2])
        self.assertEqual(Detection.objects.filter(source_image__event=event, next_detection__isnull=False).count(), 1)

        self.run_task(event, require_fresh_event=False)
        self.assertEqual(self.occurrence_sizes(event), [1, 2])

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

    def test_a_changed_determination_is_recorded_with_the_winning_prediction_as_applied_to(self):
        captures, first, second = self._two_detection_chain(first_score=0.3, second_score=0.9)
        tracking_algorithm = Algorithm.objects.create(name="Test tracking", key="test-tracking")

        assign_occurrences_from_detection_chains(captures, logger, record_as=tracking_algorithm)

        keeper = Occurrence.objects.get(pk=first.occurrence_id)
        self.assertEqual(keeper.determination, self.taxa[1])
        record = Classification.objects.get(algorithm=tracking_algorithm)
        self.assertEqual((record.detection_id, record.taxon, record.terminal), (second.pk, self.taxa[1], True))
        self.assertEqual((record.applied_to.detection_id, record.applied_to.taxon), (second.pk, self.taxa[1]))
        self.assertNotEqual(record.applied_to.algorithm_id, tracking_algorithm.pk)

        assign_occurrences_from_detection_chains(captures, logger, record_as=tracking_algorithm)
        self.assertEqual(Classification.objects.filter(algorithm=tracking_algorithm).count(), 1)

    def test_an_unchanged_determination_records_nothing(self):
        captures, first, _ = self._two_detection_chain(first_score=0.9, second_score=0.3)
        tracking_algorithm = Algorithm.objects.create(name="Test tracking", key="test-tracking")

        assign_occurrences_from_detection_chains(captures, logger, record_as=tracking_algorithm)

        self.assertEqual(Occurrence.objects.get(pk=first.occurrence_id).determination, self.taxa[0])
        self.assertFalse(Classification.objects.filter(algorithm=tracking_algorithm).exists())

    def test_a_run_records_the_determination_under_the_task_algorithm(self):
        captures = create_session(self.deployment, [[BOX], [BOX]], self.taxa[0])
        for capture, taxon, score in zip(captures, self.taxa, (0.3, 0.9)):
            Classification.objects.filter(detection__source_image=capture).update(taxon=taxon, score=score)
            capture.detections.get().occurrence.save()

        task = self.run_task(captures[0].event)

        self.assertEqual(Classification.objects.filter(algorithm=task.algorithm).count(), 1)


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
