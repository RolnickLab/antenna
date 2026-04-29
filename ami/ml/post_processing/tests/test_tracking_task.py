import logging
from collections import defaultdict

import numpy as np
from django.test import TestCase
from django.utils import timezone

from ami.main.models import Classification, Detection, Occurrence
from ami.ml.models import Algorithm
from ami.ml.post_processing.tracking_task import DEFAULT_TRACKING_PARAMS, assign_occurrences_by_tracking_images
from ami.tests.fixtures.main import create_captures, create_occurrences, create_taxa, setup_test_project

logger = logging.getLogger(__name__)


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

        # Source images need dimensions for the cost function.
        for img in self.source_images:
            if not img.width or not img.height:
                img.width = 4096
                img.height = 2160
                img.save(update_fields=["width", "height"])

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
            params=DEFAULT_TRACKING_PARAMS,
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
