import logging
from collections import defaultdict

import numpy as np
import pydantic
from django.test import TestCase
from django.utils import timezone

from ami.jobs.models import Job
from ami.main.models import Classification, Detection, Occurrence, SourceImageCollection
from ami.ml.models import Algorithm
from ami.ml.post_processing.tracking_task import TrackingConfig, TrackingTask, assign_occurrences_by_tracking_images
from ami.tests.fixtures.main import create_captures, create_occurrences, create_taxa, setup_test_project

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
