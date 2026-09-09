import logging
from collections import defaultdict

import numpy as np
import pydantic
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from ami.jobs.models import Job
from ami.main.models import Classification, Detection, Event, Identification, Occurrence, SourceImageCollection, Taxon
from ami.ml.models import Algorithm
from ami.ml.post_processing.tracking_task import (
    TrackingConfig,
    TrackingTask,
    assign_occurrences_by_tracking_images,
    assign_occurrences_from_detection_chains,
    event_is_fresh,
)
from ami.tests.fixtures.images import generate_moth_series
from ami.tests.fixtures.main import create_captures, create_occurrences, create_taxa, setup_test_project
from ami.tests.fixtures.tracking import create_tracking_session, score_tracking_run
from ami.users.tests.factories import UserFactory

logger = logging.getLogger(__name__)


def _give_captures_dimensions(source_images) -> None:
    """The cost function needs an image diagonal; test captures have no dimensions."""
    for img in source_images:
        if not img.width or not img.height:
            img.width = 4096
            img.height = 2160
            img.save(update_fields=["width", "height"])


class TestTracking(TestCase):
    def setUp(self) -> None:
        self.project, self.deployment = setup_test_project(reuse=False)
        # 1 night, 5 captures spaced 1 minute apart so they group into one event.
        create_captures(deployment=self.deployment, num_nights=1, images_per_night=5, interval_minutes=1)
        create_taxa(self.project)
        create_occurrences(deployment=self.deployment, num=6)

        self.event = self.project.events.first()
        assert self.event is not None
        self.source_images = list(self.event.captures.order_by("timestamp"))
        _give_captures_dimensions(self.source_images)

        self.algorithm = self._assign_mock_features_to_occurrence_detections(self.event)

        # Capture ground-truth groupings so we can compare after re-tracking.
        self.ground_truth_groups = defaultdict(set)
        for occ in Occurrence.objects.filter(event=self.event):
            for det_id in Detection.objects.filter(occurrence=occ).values_list("id", flat=True):
                self.ground_truth_groups[occ.pk].add(det_id)

        Detection.objects.filter(source_image__event=self.event).update(next_detection=None)

    def _assign_mock_features_to_occurrence_detections(
        self, event, algorithm_name: str = "MockTrackingAlgorithm"
    ) -> Algorithm:
        algorithm, _ = Algorithm.objects.get_or_create(name=algorithm_name, key="mock-tracking-algo")
        rng = np.random.default_rng(seed=42)

        for occurrence in event.occurrences.all():
            base_vector = rng.random(2048)
            for det in occurrence.detections.all():
                noisy = base_vector + rng.normal(0, 0.001, size=2048)
                Classification.objects.update_or_create(
                    detection=det,
                    algorithm=algorithm,
                    defaults={
                        "timestamp": timezone.now(),
                        "features_2048": noisy.tolist(),
                        "terminal": True,
                        "score": 1.0,
                    },
                )
        return algorithm

    def _two_frame_chain(self, first_score: float, second_score: float):
        """Two singleton occurrences in consecutive captures, linked into one chain, whose
        frames predict different taxa with the given scores."""
        taxon_a, taxon_b = list(Taxon.objects.filter(projects=self.project).order_by("pk")[:2])
        det_a = self.source_images[0].detections.order_by("pk").first()
        det_b = self.source_images[1].detections.order_by("pk").first()
        for det, taxon, score in ((det_a, taxon_a, first_score), (det_b, taxon_b, second_score)):
            occurrence = Occurrence.objects.create(event=self.event, deployment=self.deployment, project=self.project)
            det.occurrence = occurrence
            det.next_detection = None
            det.save()
            Classification.objects.filter(detection=det).update(taxon=taxon, score=score)
            occurrence.save()
        det_a.next_detection = det_b
        det_a.save()
        return det_a, det_b, taxon_a, taxon_b

    def test_a_changed_determination_is_recorded_as_a_tracking_classification(self):
        """When the merge moves the determination to a later frame's prediction, one terminal
        classification attributed to the tracking algorithm points at that prediction; a
        second pass over the same chain adds nothing."""
        tracking_algorithm = Algorithm.objects.create(name="Occurrence Tracking", key="tracking")
        det_a, det_b, taxon_a, taxon_b = self._two_frame_chain(first_score=0.3, second_score=0.9)
        assign_occurrences_from_detection_chains(self.source_images[:2], logger, record_as=tracking_algorithm)

        keeper = Occurrence.objects.get(pk=det_a.occurrence_id)
        self.assertEqual(keeper.determination, taxon_b)
        recorded = Classification.objects.filter(algorithm=tracking_algorithm)
        self.assertEqual(recorded.count(), 1)
        record = recorded.get()
        self.assertEqual(
            (record.detection_id, record.taxon, record.score, record.terminal), (det_b.pk, taxon_b, 0.9, True)
        )
        # The fixture gives a detection more than one row for the same prediction, so pin the
        # lineage by content rather than by row identity.
        self.assertEqual(
            (record.applied_to.detection_id, record.applied_to.taxon, record.applied_to.score),
            (det_b.pk, taxon_b, 0.9),
        )
        self.assertNotEqual(record.applied_to.algorithm_id, tracking_algorithm.pk)

        assign_occurrences_from_detection_chains(self.source_images[:2], logger, record_as=tracking_algorithm)
        self.assertEqual(Classification.objects.filter(algorithm=tracking_algorithm).count(), 1)

    def test_an_unchanged_determination_leaves_no_tracking_classification(self):
        """A merge whose keeper already held the winning prediction records nothing."""
        tracking_algorithm = Algorithm.objects.create(name="Occurrence Tracking", key="tracking")
        det_a, det_b, taxon_a, _ = self._two_frame_chain(first_score=0.9, second_score=0.3)

        assign_occurrences_from_detection_chains(self.source_images[:2], logger, record_as=tracking_algorithm)

        keeper = Occurrence.objects.get(pk=det_a.occurrence_id)
        self.assertEqual(keeper.determination, taxon_a)
        self.assertEqual(keeper.detections.count(), 2)
        self.assertFalse(Classification.objects.filter(algorithm=tracking_algorithm).exists())

    def test_tracking_reproduces_occurrence_groups(self):
        # v1 fresh-data scenario: pipeline already created 1:1 detection/occurrence.
        # Wipe only chain links so tracking has to rebuild them; occurrences stay so
        # event_is_fresh() passes and tracking runs.
        Detection.objects.filter(source_image__event=self.event).update(next_detection=None)

        # Sanity-check the fresh invariant before running.
        orphans = Detection.objects.filter(source_image__event=self.event, occurrence__isnull=True).count()
        self.assertEqual(orphans, 0, "Test setup expects every detection to have an occurrence")

        assign_occurrences_by_tracking_images(
            event=self.event,
            logger=logger,
            algorithm=self.algorithm,
            config=TrackingConfig(event_ids=[self.event.pk]),
        )

        new_groups = {
            occ.pk: set(Detection.objects.filter(occurrence=occ).values_list("id", flat=True))
            for occ in Occurrence.objects.filter(event=self.event)
        }

        self.assertEqual(
            len(new_groups),
            len(self.ground_truth_groups),
            f"Expected {len(self.ground_truth_groups)} groups, got {len(new_groups)}",
        )

        gt_values = list(self.ground_truth_groups.values())
        for new_set in new_groups.values():
            self.assertIn(
                new_set,
                gt_values,
                f"Reconstructed group {new_set} does not match any ground-truth group",
            )


class TestTrackingWithoutFeatures(TestCase):
    """Tracking must still link detections when no embeddings were stored.

    Data processed before embeddings existed has no ``features_2048``. With
    ``require_features=False`` the appearance term is dropped and detections are
    matched on bounding-box geometry alone.
    """

    def setUp(self) -> None:
        self.project, self.deployment = setup_test_project(reuse=False)
        create_captures(deployment=self.deployment, num_nights=1, images_per_night=5, interval_minutes=1)
        create_taxa(self.project)
        # The fixture gives every detection the same bbox, so consecutive captures
        # look like one insect that never moved: geometry cost is 0.
        create_occurrences(deployment=self.deployment, num=6)

        self.event = self.project.events.first()
        assert self.event is not None
        _give_captures_dimensions(list(self.event.captures.all()))
        self.detections_in_event = Detection.objects.filter(source_image__event=self.event).count()

    def test_geometry_only_run_links_detections(self):
        self.assertFalse(
            Classification.objects.filter(
                detection__source_image__event=self.event, features_2048__isnull=False
            ).exists(),
            "This test needs detections with no embeddings",
        )

        task = TrackingTask(
            logger=logger,
            event_ids=[self.event.pk],
            require_features=False,
            cost_threshold=0.5,
        )
        task.run()

        linked = Detection.objects.filter(source_image__event=self.event, next_detection__isnull=False).count()
        self.assertGreater(linked, 0, "Geometry-only tracking should link detections in consecutive captures")

        longest_chain = max(occ.detections.count() for occ in Occurrence.objects.filter(event=self.event))
        self.assertGreater(longest_chain, 1, "At least one occurrence should span several detections")
        self.assertEqual(
            Detection.objects.filter(source_image__event=self.event, occurrence__isnull=True).count(),
            0,
            "Every detection should still belong to an occurrence after tracking",
        )

    def test_requiring_features_leaves_data_untouched(self):
        before = Occurrence.objects.filter(event=self.event).count()

        task = TrackingTask(logger=logger, event_ids=[self.event.pk], require_features=True)
        task.run()

        self.assertEqual(Occurrence.objects.filter(event=self.event).count(), before)
        self.assertEqual(
            Detection.objects.filter(source_image__event=self.event, next_detection__isnull=False).count(), 0
        )


class TestFreshEventGuard(TestCase):
    """The guard refuses already-grouped sessions, and only those.

    Real sessions carry a few detections with no occurrence; refusing those would
    put most production data out of reach of tracking.
    """

    def setUp(self) -> None:
        self.project, self.deployment = setup_test_project(reuse=False)
        create_captures(deployment=self.deployment, num_nights=1, images_per_night=3, interval_minutes=1)
        create_taxa(self.project)
        create_occurrences(deployment=self.deployment, num=3)
        event = self.project.events.first()
        assert event is not None
        self.event = event

    def test_orphan_detection_does_not_block_a_run(self):
        orphan = Detection.objects.filter(source_image__event=self.event).first()
        assert orphan is not None
        occurrence = orphan.occurrence
        orphan.occurrence = None
        orphan.save(update_fields=["occurrence"])
        if occurrence:
            occurrence.delete()

        fresh, reason = event_is_fresh(self.event)
        self.assertTrue(fresh, reason)

    def test_occurrence_spanning_two_detections_blocks_a_run(self):
        first, second = list(Detection.objects.filter(source_image__event=self.event)[:2])
        second.occurrence = first.occurrence
        second.save(update_fields=["occurrence"])

        fresh, reason = event_is_fresh(self.event)
        self.assertFalse(fresh)
        self.assertIn("already span", reason)


class TestTrackingTaskResolveEvents(TestCase):
    """Scope-resolution unit tests for ``TrackingTask._resolve_events``."""

    def setUp(self) -> None:
        self.project, self.deployment = setup_test_project(reuse=False)
        create_captures(deployment=self.deployment, num_nights=1, images_per_night=2, interval_minutes=1)
        self.event = self.project.events.first()
        assert self.event is not None

    def test_resolve_events_from_event_ids(self):
        task = TrackingTask(logger=logger, event_ids=[self.event.pk])
        events = task._resolve_events()
        self.assertEqual([e.pk for e in events], [self.event.pk])

    def test_resolve_events_from_capture_set(self):
        collection = SourceImageCollection.objects.create(name="Tracking scope", project=self.project)
        collection.images.set(self.event.captures.all())

        task = TrackingTask(logger=logger, source_image_collection_id=collection.pk)
        events = task._resolve_events()
        self.assertEqual([e.pk for e in events], [self.event.pk])

    def test_config_requires_exactly_one_scope(self):
        with self.assertRaises(pydantic.ValidationError):
            TrackingTask(logger=logger)
        with self.assertRaises(pydantic.ValidationError):
            TrackingTask(logger=logger, event_ids=[self.event.pk], source_image_collection_id=1)

    def test_resolve_events_drops_cross_project_ids(self):
        # Make a foreign event in a different project; the job project should win.
        other_project, other_deployment = setup_test_project(reuse=False)
        create_captures(deployment=other_deployment, num_nights=1, images_per_night=2, interval_minutes=1)
        foreign_event = other_project.events.first()
        assert foreign_event is not None

        job = Job.objects.create(
            name="Tracking scope test",
            project=self.project,
            job_type_key="post_processing",
            params={"task": "tracking", "config": {"event_ids": [self.event.pk, foreign_event.pk]}},
        )
        task = TrackingTask(job=job, event_ids=[self.event.pk, foreign_event.pk])
        events = task._resolve_events()
        self.assertEqual([e.pk for e in events], [self.event.pk])


class TestGeneratedMothLifespans(SimpleTestCase):
    """The generator has to offer tracking both multi-frame chains and single-frame strays.

    A series where every moth is in every frame cannot show whether tracking knows when to
    stop a chain, and one with no repeat visitors cannot show that it builds chains at all.
    """

    def test_moths_span_contiguous_runs_and_transients_appear_once(self):
        frames = generate_moth_series(
            num_frames=10,
            num_moths=3,
            num_transient_moths=2,
            min_frames_per_moth=4,
            save_images=False,
        )

        frames_by_moth = defaultdict(list)
        for frame in frames:
            for box in frame.bounding_boxes:
                frames_by_moth[box.identifier].append(frame.frame_num)

        self.assertEqual(len(frames_by_moth), 5)
        for identifier, frame_numbers in frames_by_moth.items():
            self.assertEqual(
                frame_numbers,
                list(range(min(frame_numbers), max(frame_numbers) + 1)),
                f"Moth {identifier} should be visible for one unbroken run of frames",
            )
        spans = sorted(len(frame_numbers) for frame_numbers in frames_by_moth.values())
        self.assertEqual(spans[:2], [1, 1], "Both transient moths should appear in exactly one frame")
        self.assertGreaterEqual(spans[2], 4, "Every other moth should stay for at least min_frames_per_moth")


class TestTrackingDemoSession(TestCase):
    """The demo session must reach tracking in the shape it needs, and be rebuilt from it.

    Two properties make the session trackable and both are easy to lose: the captures carry
    dimensions, without which the matching cost has no image diagonal and skips the
    transition, and every detection starts on an occurrence of its own, without which
    ``event_is_fresh`` refuses the event outright.
    """

    def setUp(self) -> None:
        self.project, self.deployment = setup_test_project(reuse=False)
        self.ground_truth = create_tracking_session(
            self.deployment,
            taxa_list=create_taxa(self.project),
            num_frames=8,
            num_moths=3,
            num_transient_moths=2,
            min_frames_per_moth=4,
            create_crops=False,
        )
        self.event = Event.objects.get(pk=self.ground_truth.event_id)

    def test_session_arrives_ready_to_track(self):
        self.assertEqual(self.event.captures.count(), self.ground_truth.capture_count)
        self.assertFalse(self.event.captures.filter(width__isnull=True).exists())
        self.assertEqual(
            Occurrence.objects.filter(event=self.event).count(),
            self.ground_truth.detection_count,
            "Every detection should start on an occurrence of its own",
        )
        fresh, reason = event_is_fresh(self.event)
        self.assertTrue(fresh, reason)

    def test_tracking_recovers_every_simulated_insect(self):
        TrackingTask(
            logger=logger,
            event_ids=[self.event.pk],
            require_features=False,
            cost_threshold=0.4,
        ).run()

        result = score_tracking_run(self.ground_truth)
        self.assertEqual(result["exactly_recovered"], result["simulated_insects"], result)


class TestIdentificationsSurviveMerging(TestCase):
    """Merging chains must not destroy a person's taxonomic work.

    ``Identification.occurrence`` cascades on delete, and consolidating a chain
    deletes every occurrence except the keeper. A session that has never been
    tracked can still have been reviewed, so identifications have to be moved to
    the keeper before the occurrences holding them are removed.
    """

    def setUp(self) -> None:
        self.project, self.deployment = setup_test_project(reuse=False)
        create_captures(deployment=self.deployment, num_nights=1, images_per_night=5, interval_minutes=1)
        create_taxa(self.project)
        create_occurrences(deployment=self.deployment, num=6)

        self.event = self.project.events.first()
        assert self.event is not None
        _give_captures_dimensions(list(self.event.captures.all()))

        self.user = UserFactory()
        taxon = Taxon.objects.filter(occurrences__event=self.event).first() or Taxon.objects.first()
        assert taxon is not None
        # Identify every occurrence in the event. The keeper is the chain's first
        # occurrence, so identifying only one would pass by luck roughly as often
        # as the chain is long.
        self.identified = list(Occurrence.objects.filter(event=self.event))
        self.assertGreater(len(self.identified), 1, "Need several occurrences for a merge to happen")
        for occurrence in self.identified:
            Identification.objects.create(user=self.user, taxon=taxon, occurrence=occurrence)
        self.identification_count = Identification.objects.filter(occurrence__event=self.event).count()

    def test_identifications_move_to_the_keeper_instead_of_being_deleted(self):
        task = TrackingTask(
            logger=logger,
            event_ids=[self.event.pk],
            require_features=False,
            cost_threshold=0.5,
            # The guard would refuse this event; the point of the test is what happens
            # when an operator turns it off, which the admin form allows.
            skip_if_human_identifications=False,
        )
        task.run()

        merged_away = Occurrence.objects.filter(pk__in=[o.pk for o in self.identified]).count()
        self.assertLess(merged_away, len(self.identified), "This test only means something if a merge occurred")

        self.assertEqual(
            Identification.objects.filter(user=self.user).count(),
            self.identification_count,
            "Every identification must survive the merge",
        )
        self.assertFalse(
            Identification.objects.filter(user=self.user, occurrence__isnull=True).exists(),
            "No identification should be left without an occurrence",
        )
        surviving = Occurrence.objects.filter(event=self.event).values_list("pk", flat=True)
        self.assertTrue(
            set(Identification.objects.filter(user=self.user).values_list("occurrence_id", flat=True))
            <= set(surviving),
            "Every identification must point at an occurrence that still exists",
        )
