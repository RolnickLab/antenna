import datetime
import logging
import typing
from unittest import mock

from django.db import connection
from django.test import SimpleTestCase, TestCase
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
    @classmethod
    def setUpTestData(cls) -> None:
        cls.project, cls.deployment = setup_test_project(reuse=False)
        create_taxa(cls.project)
        cls.taxa = list(Taxon.objects.filter(projects=cls.project, rank="SPECIES").order_by("name"))

    def run_task(self, event: Event, job: Job | None = None, **config) -> TrackingTask:
        task = TrackingTask(job=job, logger=logger, event_ids=[event.pk], **config)
        task.run()
        return task

    def occurrence_sizes(self, event: Event) -> list[int]:
        return sorted(o.detections.count() for o in Occurrence.objects.filter(event=event))

    def links(self, event: Event):
        return Detection.objects.filter(source_image__event=event, next_detection__isnull=False)

    def make_job(self, project=None) -> Job:
        job = Job.objects.create(name="t", project=project or self.project, job_type_key="post_processing")
        job.progress.add_stage("Post-processing", key="post_processing")
        job.save()
        return job

    def job_params(self, job: Job) -> dict[str, typing.Any]:
        job.refresh_from_db()
        return {p.name: p.value for p in job.progress.get_stage("post_processing").params}


class TestRegistration(SimpleTestCase):
    def test_task_is_registered(self):
        self.assertIs(get_postprocessing_task("tracking"), TrackingTask)


class TestTrackingSessions(_TrackingCase):
    """What a run links and merges in a session, and which sessions it leaves alone."""

    def test_a_still_insect_is_folded_into_one_occurrence(self):
        captures = create_session(self.deployment, [[BOX], [BOX], [BOX]], self.taxa[0])
        event = captures[0].event
        detections = [c.detections.get() for c in captures]
        job = self.make_job()

        self.run_task(event, job=job)

        self.assertEqual(self.occurrence_sizes(event), [3])
        self.assertEqual(self.links(event).count(), 2)
        event.refresh_from_db()
        self.assertEqual(event.occurrences_count, 1)
        params = self.job_params(job)
        self.assertEqual((params["Sessions tracked"], params["Detection links created"]), (1, 2))
        # The result records the grouping before the run.
        result = AlgorithmResult.objects.get(kind="tracking")
        self.assertEqual(result.data["detection_ids"], [d.pk for d in detections])
        self.assertEqual(result.data["previous_occurrence_ids"], [d.occurrence_id for d in detections])
        self.assertEqual(result.data["merged_occurrence_ids"], sorted(d.occurrence_id for d in detections[1:]))

    def test_an_unprocessed_capture_between_processed_ones_does_not_break_the_chain(self):
        captures = create_session(self.deployment, [[BOX], None, [BOX]], self.taxa[0])

        self.run_task(captures[0].event)

        self.assertEqual(self.occurrence_sizes(captures[0].event), [2])

    def test_a_processed_capture_with_no_insects_is_part_of_the_sequence(self):
        """A null-bbox marker row makes a capture processed, so the empty capture separates its neighbours."""
        captures = create_session(self.deployment, [[BOX], [], [BOX]], self.taxa[0])

        self.run_task(captures[0].event)

        self.assertEqual(self.occurrence_sizes(captures[0].event), [1, 1])

    def test_a_capture_without_a_timestamp_is_left_out(self):
        captures = create_session(self.deployment, [[BOX], [BOX], [BOX]], self.taxa[0])
        type(captures[1]).objects.filter(pk=captures[1].pk).update(timestamp=None)

        self.run_task(captures[0].event)

        self.assertEqual(self.occurrence_sizes(captures[0].event), [1, 2])
        self.assertIsNone(captures[1].detections.get().next_detection_id)

    def test_the_interval_limit_stops_links_across_a_long_gap(self):
        captures = create_session(self.deployment, [[BOX], [BOX], [BOX]], self.taxa[0], interval_seconds=60)
        job = self.make_job()

        self.run_task(captures[0].event, job=job, max_capture_interval_seconds=30)

        self.assertEqual(self.occurrence_sizes(captures[0].event), [1, 1, 1])
        self.assertEqual(self.job_params(job)["Capture pairs too far apart to compare"], 2)

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

        # The stored link marks both sessions as tracked, so the guard is turned off.
        for event in (first[0].event, second[0].event):
            self.run_task(event, require_fresh_event=False)

        self.assertEqual(self.occurrence_sizes(first[0].event), [2])
        self.assertEqual(self.occurrence_sizes(second[0].event), [2])
        first_of_second.refresh_from_db()
        self.assertNotEqual(first_of_second.occurrence_id, first[0].detections.get().occurrence_id)

    def test_a_session_with_nothing_to_compare_is_skipped_with_a_reason(self):
        day = datetime.datetime(2026, 7, 1, 22, 0, 0)
        cases = [
            ([[BOX], None], "fewer than two processed captures"),
            ([[], []], "have no detections"),
        ]
        for offset, (boxes, reason) in enumerate(cases):
            with self.subTest(reason=reason):
                captures = create_session(
                    self.deployment, boxes, self.taxa[0], start=day + datetime.timedelta(days=offset)
                )
                job = self.make_job()

                self.run_task(captures[0].event, job=job)

                params = self.job_params(job)
                self.assertEqual((params["Sessions tracked"], params["Sessions skipped"]), (0, 1))
                self.assertIn(reason, params["Result"])

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

    def test_chains_joined_through_an_earlier_grouping_become_one_occurrence(self):
        """An earlier grouping put the first and last detections in one occurrence. The run links the first
        detection to a neighbour and the last to another, so both chains and that occurrence become one.
        """
        far = [600, 500, 650, 550]
        captures = create_session(self.deployment, [[BOX], [BOX, far], [far]], self.taxa[0])
        event = captures[0].event
        first = captures[0].detections.get()
        last = captures[2].detections.get()
        emptied = last.occurrence
        last.occurrence = first.occurrence
        last.save(update_fields=["occurrence"])
        emptied.delete()

        self.run_task(event, require_fresh_event=False)

        self.assertFalse(Detection.objects.filter(source_image__event=event, occurrence__isnull=True).exists())
        self.assertEqual(self.occurrence_sizes(event), [4])

    def test_a_session_grouped_earlier_without_links_is_tracked(self):
        """Only a stored link marks a session as tracked; an occurrence of several detections does not."""
        captures = create_session(self.deployment, [[BOX], [BOX], [BOX]], self.taxa[0])
        event = captures[0].event
        first, second = (c.detections.get() for c in captures[:2])
        emptied = second.occurrence
        second.occurrence = first.occurrence
        second.save(update_fields=["occurrence"])
        emptied.delete()

        self.run_task(event)

        self.assertEqual(self.occurrence_sizes(event), [3])

    def test_a_session_with_human_identifications_is_tracked_unless_asked_to_skip_it(self):
        captures = create_session(self.deployment, [[BOX], [BOX]], self.taxa[0])
        event = captures[0].event
        occurrence = Occurrence.objects.filter(event=event).first()
        Identification.objects.create(user=UserFactory(), taxon=self.taxa[1], occurrence=occurrence)

        self.run_task(event, skip_if_human_identifications=True)
        self.assertEqual(self.occurrence_sizes(event), [1, 1])

        self.run_task(event)
        self.assertEqual(self.occurrence_sizes(event), [2])

    def two_detector_session(self) -> tuple[Event, Algorithm, Algorithm]:
        captures = create_session(self.deployment, [[BOX], [BOX]], self.taxa[0])
        first, second = (Algorithm.objects.create(name=f"Detector {n}", key=f"detector-{n}") for n in (1, 2))
        Detection.objects.filter(source_image__in=captures).update(detection_algorithm=first)
        for capture in captures:
            duplicate = add_detection(capture, [102, 102, 202, 202], self.taxa[0])
            duplicate.detection_algorithm = second
            duplicate.save(update_fields=["detection_algorithm"])
        return captures[0].event, first, second

    def test_a_session_with_two_detectors_is_skipped_with_a_reason(self):
        event, _, _ = self.two_detector_session()
        job = self.make_job()

        self.run_task(event, job=job)

        self.assertEqual(self.occurrence_sizes(event), [1, 1, 1, 1])
        self.assertIn("more than one detector", self.job_params(job)["Result"])

    def test_a_chosen_detector_links_only_its_own_detections(self):
        event, first, second = self.two_detector_session()

        self.run_task(event, detection_algorithm_id=second.pk)

        self.assertEqual(self.occurrence_sizes(event), [1, 1, 2])
        self.assertEqual(self.links(event).get().detection_algorithm_id, second.pk)

    def test_an_occurrence_that_keeps_detections_the_run_does_not_compare_is_not_merged_away(self):
        """Only the compared detection moves; the occurrence keeps the other detector's detection and its results."""
        event, first, second = self.two_detector_session()
        by_time = Detection.objects.filter(source_image__event=event).order_by("source_image__timestamp")
        shared = by_time.filter(detection_algorithm=first).last()
        compared = by_time.filter(detection_algorithm=second).last()
        assert shared is not None and compared is not None
        emptied = compared.occurrence
        compared.occurrence = shared.occurrence
        compared.save(update_fields=["occurrence"])
        emptied.delete()
        size_filter = Algorithm.objects.create(name="Test filter", key="test-filter")
        earlier = AlgorithmResult.objects.record(
            occurrence=shared.occurrence, algorithm=size_filter, kind="size_filter", data={"relative_size": 0.01}
        )

        self.run_task(event, detection_algorithm_id=second.pk)

        kept = Occurrence.objects.get(pk=shared.occurrence_id)
        self.assertEqual(list(kept.detections.values_list("pk", flat=True)), [shared.pk])
        earlier.refresh_from_db()
        self.assertEqual(earlier.occurrence_id, kept.pk)
        compared.refresh_from_db()
        self.assertNotEqual(compared.occurrence_id, kept.pk)
        self.assertEqual(self.occurrence_sizes(event), [1, 1, 2])
        self.assertEqual(AlgorithmResult.objects.get(kind="tracking").data["merged_occurrence_ids"], [])

    def test_a_preview_reports_the_counts_and_changes_nothing(self):
        captures = create_session(self.deployment, [[BOX], [BOX], [BOX]], self.taxa[0])
        event = captures[0].event
        job = self.make_job()

        self.run_task(event, job=job, preview_only=True)

        self.assertEqual(self.occurrence_sizes(event), [1, 1, 1])
        self.assertFalse(self.links(event).exists())
        self.assertFalse(AlgorithmResult.objects.exists())
        params = self.job_params(job)
        self.assertEqual(params["Detection links that would be created"], 2)
        self.assertEqual(params["Occurrences that would be merged away"], 2)
        self.assertEqual((params["Occurrences before"], params["Occurrences after the run"]), (3, 1))
        self.assertTrue(params["Result"].startswith("Preview only, nothing was changed."))

        self.run_task(event, job=job)
        self.assertEqual(self.occurrence_sizes(event), [3])

    def test_a_capture_set_tracks_every_processed_capture_of_the_sessions_it_touches(self):
        captures = create_session(self.deployment, [[BOX], [BOX], [BOX]], self.taxa[0])
        collection = SourceImageCollection.objects.create(name="Sampled", project=self.project)
        collection.images.add(captures[0])

        TrackingTask(job=None, logger=logger, source_image_collection_id=collection.pk).run()

        self.assertEqual(self.occurrence_sizes(captures[0].event), [3])

    def test_a_session_of_another_project_is_not_tracked_for_a_job(self):
        captures = create_session(self.deployment, [[BOX], [BOX]], self.taxa[0])
        other_project, _ = setup_test_project(reuse=False)

        self.run_task(captures[0].event, job=self.make_job(project=other_project))

        self.assertEqual(self.occurrence_sizes(captures[0].event), [1, 1])


class TestIdentificationsAndMerges(_TrackingCase):
    """A run keeps the occurrences people identified, never joins two whose identifications disagree, and moves
    identifications onto the occurrence it keeps."""

    def setUp(self) -> None:
        self.user = UserFactory()

    def still_insect(self, captures_count: int = 3) -> tuple[Event, list[Occurrence]]:
        captures = create_session(self.deployment, [[BOX]] * captures_count, self.taxa[0])
        return captures[0].event, [c.detections.get().occurrence for c in captures]

    def identify(self, occurrence: Occurrence, taxon: Taxon) -> Identification:
        return Identification.objects.create(user=self.user, taxon=taxon, occurrence=occurrence)

    def test_the_identified_occurrence_is_kept_when_others_merge_into_it(self):
        """The occurrence someone identified keeps its id, even when an earlier capture's occurrence would be kept."""
        event, occurrences = self.still_insect()
        identification = self.identify(occurrences[1], self.taxa[1])

        self.run_task(event)

        kept = Occurrence.objects.get(event=event)
        self.assertEqual(kept.pk, occurrences[1].pk)
        self.assertEqual(kept.detections.count(), 3)
        identification.refresh_from_db()
        self.assertFalse(identification.withdrawn)
        self.assertEqual(kept.determination, self.taxa[1])

    def test_occurrences_identified_as_different_taxa_are_not_joined(self):
        """Neither identification is withdrawn: the link that would have joined them is not made."""
        event, occurrences = self.still_insect()
        first = self.identify(occurrences[0], self.taxa[1])
        last = self.identify(occurrences[2], self.taxa[2])
        job = self.make_job()

        self.run_task(event, job=job)

        self.assertEqual(self.occurrence_sizes(event), [1, 2])
        self.assertEqual(Occurrence.objects.get(pk=occurrences[0].pk).detections.count(), 2)
        for identification, occurrence in ((first, occurrences[0]), (last, occurrences[2])):
            identification.refresh_from_db()
            self.assertFalse(identification.withdrawn)
            self.assertEqual(identification.occurrence_id, occurrence.pk)
        params = self.job_params(job)
        self.assertEqual(params["Detection links created"], 1)
        self.assertEqual(params["Detection links refused because identifications disagree"], 1)

    def assert_a_change_during_matching_stops_the_write(self, event: Event, change: typing.Callable[[], object]):
        """Matching holds no lock, so a session that changed before the write is skipped rather than written."""
        job = self.make_job()
        real = task_module.plan_session_links

        def plan_then_change(*args, **kwargs):
            plan = real(*args, **kwargs)
            change()
            return plan

        with mock.patch.object(task_module, "plan_session_links", plan_then_change):
            self.run_task(event, job=job)

        self.assertFalse(self.links(event).exists())
        self.assertIn("it changed while it was being tracked", self.job_params(job)["Result"])

    def test_a_detection_added_while_the_session_is_matched_stops_the_write(self):
        captures = create_session(self.deployment, [[BOX], [BOX]], self.taxa[0])

        self.assert_a_change_during_matching_stops_the_write(
            captures[0].event, lambda: add_detection(captures[1], [500, 500, 560, 560], self.taxa[0])
        )

        self.assertEqual(self.occurrence_sizes(captures[0].event), [1, 1, 1])

    def test_an_identification_saved_while_the_session_is_matched_stops_the_write(self):
        event, occurrences = self.still_insect(2)
        self.identify(occurrences[0], self.taxa[1])

        self.assert_a_change_during_matching_stops_the_write(
            event, lambda: self.identify(occurrences[1], self.taxa[2])
        )

        self.assertEqual(self.occurrence_sizes(event), [1, 1])

    def test_identifications_move_onto_the_keeper_instead_of_being_deleted(self):
        event, occurrences = self.still_insect()
        for occurrence in occurrences:
            self.identify(occurrence, self.taxa[1])

        self.run_task(event)

        keeper = Occurrence.objects.get(event=event)
        self.assertEqual(set(Identification.objects.values_list("occurrence_id", flat=True)), {keeper.pk})
        self.assertEqual(Identification.objects.filter(user=self.user).count(), 3)
        result = AlgorithmResult.objects.get(kind="tracking")
        self.assertEqual(len(result.data["moved_identifications"]), 2)
        self.assertEqual(len(result.data["withdrawn_identification_ids"]), 2)

    def test_class_masking_after_tracking_still_changes_the_determination(self):
        """A later re-scoring replaces a merged occurrence's determination, because tracking adds no classification."""
        captures = create_session(self.deployment, [[BOX], [BOX]], self.taxa[0])
        self.run_task(captures[0].event)
        occurrence = Occurrence.objects.get(event=captures[0].event)

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
        update_occurrence_determination(Occurrence.objects.get(pk=occurrence.pk), save=True)

        occurrence.refresh_from_db()
        self.assertEqual(occurrence.determination, self.taxa[2])


class TestTrackingResults(_TrackingCase):
    """The tracking result written for each occurrence a run changes. The figures' arithmetic is pinned by the
    tests of ``stats.py``; these check what is read from the database and how results are kept per job."""

    def test_each_linked_occurrence_gets_a_result(self):
        moving, still, lone = [100, 100, 200, 200], [700, 700, 800, 800], [400, 800, 420, 820]
        captures = create_session(
            self.deployment,
            [[moving, still], [[110, 100, 210, 200], still], [[120, 100, 220, 200], still, lone]],
            self.taxa[0],
        )
        job = self.make_job()

        task = self.run_task(captures[0].event, job=job)

        results = {r.occurrence_id: r for r in AlgorithmResult.objects.filter(kind="tracking")}
        self.assertEqual(len(results), 2)
        self.assertNotIn(captures[2].detections.get(bbox=lone).occurrence_id, results)
        still_result, moving_result = sorted(results.values(), key=lambda r: r.value)
        self.assertEqual(still_result.value, 0.0)
        self.assertGreater(moving_result.value, 0.0)
        for result in (still_result, moving_result):
            self.assertEqual((result.job_id, result.algorithm_id), (job.pk, task.algorithm.pk))
            self.assertEqual(result.project_id, self.project.pk)
            self.assertEqual(result.data["detection_count"], 3)
            self.assertEqual(len(result.data["link_costs"]), len(result.data["detection_ids"]))
            self.assertEqual(len(result.data["merged_occurrence_ids"]), 2)
        self.assertEqual(self.job_params(job)["Occurrences recorded"], 2)

    def test_the_taxa_come_from_the_labels_of_the_merged_detections(self):
        captures = create_session(self.deployment, [[BOX], [BOX]], self.taxa[0])
        second = captures[1].detections.get()
        Classification.objects.filter(detection=second).update(taxon=self.taxa[1], score=0.6)
        second.occurrence.save()

        self.run_task(captures[0].event)

        result = AlgorithmResult.objects.get(kind="tracking")
        self.assertEqual(result.data["distinct_taxa"], 2)
        self.assertEqual(result.data["label_agreement"], 0.5)
        self.assertCountEqual(
            [(t["taxon_id"], t["detection_count"]) for t in result.data["taxa"]],
            [(self.taxa[0].pk, 1), (self.taxa[1].pk, 1)],
        )

    def test_the_result_keeps_the_taxon_name_it_saw_after_a_rename(self):
        """The breakdown is a copy, so renaming or merging a taxon later does not rewrite what the run recorded."""
        captures = create_session(self.deployment, [[BOX], [BOX]], self.taxa[0])
        name = self.taxa[0].name

        self.run_task(captures[0].event)
        Taxon.objects.filter(pk=self.taxa[0].pk).update(name="Renamed later")

        result = AlgorithmResult.objects.get(kind="tracking")
        [taxon] = result.data["taxa"]
        self.assertEqual((taxon["taxon_id"], taxon["name"], taxon["detection_count"]), (self.taxa[0].pk, name, 2))

    def test_the_result_records_the_determination_before_and_after_without_a_classification(self):
        captures = create_session(self.deployment, [[BOX], [BOX]], self.taxa[0])
        for capture, taxon, score in zip(captures, self.taxa, (0.3, 0.9)):
            Classification.objects.filter(detection__source_image=capture).update(taxon=taxon, score=score)
            capture.detections.get().occurrence.save()

        task = self.run_task(captures[0].event, job=self.make_job())

        result = AlgorithmResult.objects.get(kind="tracking")
        self.assertEqual(result.data["determination_after_id"], self.taxa[1].pk)
        self.assertEqual(result.data["determination_before_id"], self.taxa[0].pk)
        self.assertFalse(Classification.objects.filter(algorithm=task.algorithm).exists())

    def test_each_detection_counts_once_with_the_label_the_determination_would_use(self):
        """A stray low-score terminal label next to a better one is not counted as another taxon."""
        captures = create_session(self.deployment, [[BOX], [BOX]], self.taxa[0])
        second = captures[1].detections.get()
        Classification.objects.create(
            detection=second, taxon=self.taxa[1], score=0.02, terminal=True, timestamp=second.timestamp
        )

        self.run_task(captures[0].event)

        result = AlgorithmResult.objects.get(kind="tracking")
        self.assertEqual(result.data["distinct_taxa"], 1)
        self.assertEqual(result.data["label_agreement"], 1.0)
        self.assertEqual([t["taxon_id"] for t in result.data["taxa"]], [self.taxa[0].pk])

    def test_a_post_processing_label_counts_when_it_is_the_detections_best(self):
        """A size filter's terminal row decides the determination, so it is the detection's label too."""
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
        self.assertEqual(result.data["determination_after_id"], self.taxa[1].pk)
        self.assertEqual(result.data["distinct_taxa"], 2)
        self.assertEqual(result.data["label_agreement"], 0.5)

    def test_a_run_that_extends_an_earlier_chain_records_only_its_own_link_costs(self):
        """An earlier run's link has no cost in the new result, so each cost still pairs with its detection."""
        captures = create_session(self.deployment, [[BOX], [BOX], None], self.taxa[0])
        event = captures[0].event
        self.run_task(event)
        add_detection(captures[2], BOX, self.taxa[0])

        self.run_task(event, require_fresh_event=False)

        latest = AlgorithmResult.objects.filter(kind="tracking").order_by("-pk").first()
        assert latest is not None
        self.assertEqual(
            latest.data["detection_ids"],
            list(
                Detection.objects.filter(source_image__event=event).order_by("timestamp").values_list("pk", flat=True)
            ),
        )
        costs = latest.data["link_costs"]
        self.assertIsNone(costs[0])
        self.assertIsInstance(costs[1], float)
        self.assertIsNone(costs[2])

    def test_a_retried_job_with_nothing_new_records_no_second_result(self):
        captures = create_session(self.deployment, [[BOX], [BOX], [BOX]], self.taxa[0])
        job = self.make_job()
        self.run_task(captures[0].event, job=job)

        self.run_task(captures[0].event, job=job, require_fresh_event=False)

        self.assertEqual(AlgorithmResult.objects.filter(kind="tracking", job=job).count(), 1)

    def test_a_retried_job_folds_what_it_adds_into_its_earlier_result(self):
        """One result per occurrence per job: a retry that extends a chain updates the result it wrote.

        The record still starts from the grouping before the job's first attempt.
        """
        captures = create_session(self.deployment, [[BOX], [BOX], None], self.taxa[0])
        event = captures[0].event
        before = list(Detection.objects.filter(source_image__event=event).order_by("timestamp"))
        original_occurrences = [d.occurrence_id for d in before]
        job = self.make_job()
        self.run_task(event, job=job)
        first = AlgorithmResult.objects.get(kind="tracking", job=job)
        added = add_detection(captures[2], BOX, self.taxa[0])

        self.run_task(event, job=job, require_fresh_event=False)

        result = AlgorithmResult.objects.get(kind="tracking", job=job)
        self.assertEqual(result.pk, first.pk)
        self.assertEqual(result.data["detection_ids"], [d.pk for d in before] + [added.pk])
        self.assertEqual(result.data["previous_occurrence_ids"], original_occurrences + [added.occurrence_id])
        self.assertEqual(result.data["detection_count"], 3)
        self.assertEqual(
            sorted(result.data["merged_occurrence_ids"]), sorted(original_occurrences[1:] + [added.occurrence_id])
        )
        costs = result.data["link_costs"]
        self.assertEqual([cost is None for cost in costs], [False, False, True])
        self.assertEqual(costs[0], first.data["link_costs"][0])

    def test_a_retry_that_joins_two_chains_leaves_one_result_of_the_job(self):
        """A retry that merges an occurrence holding its own result from the job folds that result in.

        The merge moves the absorbed occurrence's result onto the keeper, so without the fold the keeper
        would hold two results of one job. The kept result covers both chains, starts from the grouping
        before the first attempt, and has its ``updated_at`` stamped.
        """
        shifted = [120, 100, 220, 200]
        captures = create_session(self.deployment, [[BOX], [BOX], [shifted], [shifted]], self.taxa[0])
        event = captures[0].event
        before = list(Detection.objects.filter(source_image__event=event).order_by("timestamp"))
        job = self.make_job()
        self.run_task(event, job=job, cost_threshold=0.05)
        first_results = list(AlgorithmResult.objects.filter(kind="tracking", job=job).order_by("pk"))
        self.assertEqual(len(first_results), 2)

        self.run_task(event, job=job, cost_threshold=1.3, require_fresh_event=False)

        self.assertEqual(Occurrence.objects.filter(event=event).count(), 1)
        result = AlgorithmResult.objects.get(kind="tracking", job=job)
        self.assertEqual(result.pk, first_results[0].pk)
        self.assertEqual(result.occurrence_id, Occurrence.objects.get(event=event).pk)
        self.assertEqual(result.data["detection_ids"], [d.pk for d in before])
        self.assertEqual(result.data["previous_occurrence_ids"], [d.occurrence_id for d in before])
        self.assertEqual(sorted(result.data["merged_occurrence_ids"]), sorted(d.occurrence_id for d in before[1:]))
        self.assertEqual([cost is None for cost in result.data["link_costs"]], [False, False, False, True])
        self.assertGreater(result.updated_at, result.created_at)

    def test_results_of_merged_occurrences_move_onto_the_keeper(self):
        captures = create_session(self.deployment, [[BOX], [BOX]], self.taxa[0])
        first, second = (c.detections.get().occurrence for c in captures)
        filter_algorithm = Algorithm.objects.create(name="Test filter", key="test-filter")
        earlier = AlgorithmResult.objects.record(
            occurrence=second, algorithm=filter_algorithm, kind="size_filter", data={"relative_size": 0.01}
        )

        self.run_task(captures[0].event)

        earlier.refresh_from_db()
        self.assertEqual(earlier.occurrence_id, first.pk)
        self.assertFalse(Occurrence.objects.filter(pk=second.pk).exists())
        tracking = AlgorithmResult.objects.get(kind="tracking")
        self.assertEqual(tracking.occurrence_id, first.pk)
        self.assertEqual(tracking.data["merged_occurrence_ids"], [second.pk])

    def test_a_session_without_links_records_no_results(self):
        captures = create_session(self.deployment, [[[0, 0, 50, 50]], [[900, 900, 950, 950]]], self.taxa[0])

        self.run_task(captures[0].event)

        self.assertFalse(AlgorithmResult.objects.exists())


class TestTrackingRobustness(_TrackingCase):
    """Failures, progress saves and query counts."""

    def test_a_failing_session_is_counted_and_the_others_are_still_tracked(self):
        day = datetime.datetime(2026, 7, 1, 22, 0, 0)
        first = create_session(self.deployment, [[BOX], [BOX]], self.taxa[0], start=day)
        second = create_session(self.deployment, [[BOX], [BOX]], self.taxa[0], start=day + datetime.timedelta(hours=6))
        failing, working = first[0].event, second[0].event
        self.assertNotEqual(failing.pk, working.pk)
        job = self.make_job()
        real = task_module.write_session_plan

        def fail_for_the_first_session(plan, *args, **kwargs):
            if plan.source_images[0].event_id == failing.pk:
                # Written before the failure, so the rollback of this session is visible.
                Occurrence.objects.filter(event=failing).update(determination_score=0.123)
                raise ValueError("boom")
            return real(plan, *args, **kwargs)

        with mock.patch.object(task_module, "write_session_plan", fail_for_the_first_session):
            with self.assertRaisesMessage(RuntimeError, "Tracking failed for 1 of 2 session(s)"):
                TrackingTask(job=job, logger=logger, event_ids=[failing.pk, working.pk]).run()

        self.assertEqual(self.occurrence_sizes(working), [2])
        self.assertEqual(self.occurrence_sizes(failing), [1, 1])
        self.assertFalse(Occurrence.objects.filter(event=failing, determination_score=0.123).exists())
        working.refresh_from_db()
        self.assertEqual(working.occurrences_count, 1)
        params = self.job_params(job)
        self.assertEqual((params["Sessions tracked"], params["Sessions failed"]), (1, 1))
        self.assertIn("failed for 1 of 2", params["Result"])

    def test_progress_is_saved_while_a_session_is_matched_and_never_inside_a_transaction(self):
        """The stale-job reaper watches ``updated_at``, so a long session must keep saving the job while it matches."""
        captures = create_session(self.deployment, [[BOX]] * 7, self.taxa[0])
        task = TrackingTask(job=self.make_job(), logger=logger, event_ids=[captures[0].event_id])
        baseline = len(connection.savepoint_ids)
        seen = []

        def record(progress: float) -> None:
            seen.append((round(progress, 2), len(connection.savepoint_ids)))

        with mock.patch.object(task_module, "PROGRESS_EVERY_TRANSITIONS", 2), mock.patch.object(
            task, "update_progress", record
        ):
            task.run()

        # Six transitions, saved after the 2nd, 4th and 6th, then once per session and once at the end.
        self.assertEqual([p for p, _ in seen], [0.33, 0.67, 1.0, 1.0, 1.0])
        self.assertEqual({depth for _, depth in seen}, {baseline})

    def count_queries(self, captures_count: int, insects: int, start: datetime.datetime) -> int:
        from cachalot.api import cachalot_disabled

        boxes = [[x, 100, x + 100, 200] for x in range(0, 300 * insects, 300)]
        captures = create_session(self.deployment, [boxes] * captures_count, self.taxa[0], start=start)
        disabled = cachalot_disabled()
        disabled.__enter__()
        try:
            with CaptureQueriesContext(connection) as queries:
                self.run_task(captures[0].event)
        finally:
            # cachalot_disabled() does not restore itself when the block raises.
            disabled.__exit__(None, None, None)
        self.assertEqual(self.occurrence_sizes(captures[0].event), [captures_count] * insects)
        return len(queries)

    def test_queries_grow_with_captures_and_insects_but_not_with_detections(self):
        """Links and merges are written in bulk; only the determination recompute costs queries per occurrence.

        Each extra capture adds the same number of queries however many insects it holds, and each extra
        insect adds a fixed number, however many captures its chain spans.
        """
        self.count_queries(3, 1, datetime.datetime(2026, 6, 30))  # warms per-process caches
        one = [self.count_queries(n, 1, datetime.datetime(2026, 7, day)) for day, n in ((1, 3), (2, 6))]
        three = [self.count_queries(n, 3, datetime.datetime(2026, 7, day)) for day, n in ((3, 3), (4, 6))]
        self.assertEqual(one[1] - one[0], three[1] - three[0])
        self.assertEqual(three[0] - one[0], three[1] - one[1])
        # Budgets: at most 2 queries per extra capture and 3 per extra insect. Raise them deliberately.
        self.assertLessEqual((one[1] - one[0]) // 3, 2)
        self.assertLessEqual((three[0] - one[0]) // 2, 3)
