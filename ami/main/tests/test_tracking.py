import logging
from collections import defaultdict

import numpy as np
from django.test import TestCase
from django.utils import timezone

from ami.main.models import Classification, Detection, Occurrence, Project
from ami.ml.models import Algorithm
from ami.ml.tracking import assign_occurrences_by_tracking_images

logger = logging.getLogger(__name__)


class TestTracking(TestCase):
    def setUp(self) -> None:
        self.project = Project.objects.first()
        self.event = self.project.events.first()
        self.source_images = list(self.event.captures.order_by("timestamp"))
        self.assign_mock_features_to_occurrence_detections(self.event)
        # Save ground truth occurrence groupings
        self.ground_truth_groups = defaultdict(set)
        for occ in Occurrence.objects.filter(event=self.event):
            det_ids = Detection.objects.filter(occurrence=occ).values_list("id", flat=True)
            for det_id in det_ids:
                self.ground_truth_groups[occ.pk].add(det_id)

        # Clear existing tracking data (next_detection + occurrence)
        Detection.objects.filter(source_image__event=self.event).update(next_detection=None)

    def assign_mock_features_to_occurrence_detections(self, event, algorithm_name="MockTrackingAlgorithm"):
        algorithm, _ = Algorithm.objects.get_or_create(name=algorithm_name)

        for occurrence in event.occurrences.all():
            base_vector = np.random.rand(2048)  # Base feature for this occurrence group

            for det in occurrence.detections.all():
                feature_vector = base_vector + np.random.normal(0, 0.001, size=2048)  # Add slight variation
                Classification.objects.update_or_create(
                    detection=det,
                    algorithm=algorithm,
                    defaults={
                        "timestamp": timezone.now(),
                        "features_2048": feature_vector.tolist(),
                        "terminal": True,
                        "score": 1.0,
                    },
                )

    def test_tracking_exactly_reproduces_occurrences(self):
        # Clear previous detection chains and occurrences
        for det in Detection.objects.filter(source_image__event=self.event):
            det.occurrence = None
            det.next_detection = None
            det.save()

        Occurrence.objects.filter(event=self.event).delete()

        # Run the tracking algorithm to regenerate occurrences
        assign_occurrences_by_tracking_images(self.source_images, logger)

        # Capture new tracking-generated occurrence groups
        new_groups = {
            occ.pk: set(Detection.objects.filter(occurrence=occ).values_list("id", flat=True))
            for occ in Occurrence.objects.filter(event=self.event)
        }

        # Assert that the number of new groups equals the number of ground truth groups
        self.assertEqual(
            len(new_groups),
            len(self.ground_truth_groups),
            f"Expected {len(self.ground_truth_groups)} groups, but got {len(new_groups)}",
        )

        # Assert each new group exactly matches one of the original ground truth groups
        unmatched_groups = [
            new_set for new_set in new_groups.values() if new_set not in self.ground_truth_groups.values()
        ]

        self.assertEqual(
            len(unmatched_groups),
            0,
            f"{len(unmatched_groups)} of the new groups do not exactly match any ground truth group",
        )
        logger.info(
            f"All {len(new_groups)} new groups match the ground truth groups exactly.",
        )
        logger.info(f"new groups: {new_groups}")
        # Assert that each ground truth group is present in the new tracking results
        for gt_set in self.ground_truth_groups.values():
            logger.info(
                f"Checking ground truth group: {gt_set}",
            )
            self.assertIn(
                gt_set,
                new_groups.values(),
                f"Ground truth group {gt_set} not found in new tracking results",
            )
