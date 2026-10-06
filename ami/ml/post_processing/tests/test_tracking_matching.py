import datetime

import pydantic
from django.test import SimpleTestCase

from ami.ml.post_processing.tracking.config import TrackingConfig
from ami.ml.post_processing.tracking.matching import captures_too_far_apart, pair_cost, select_links

BOX = [100, 100, 200, 200]
DIAG = 1000 * 2**0.5


def _config(**kwargs) -> TrackingConfig:
    return TrackingConfig(event_ids=[1], **kwargs)


class TestTrackingConfig(SimpleTestCase):
    def test_defaults_are_the_plain_sum_baseline_with_every_limit_off(self):
        config = _config()
        self.assertEqual(
            (config.cost_threshold, config.iou_weight, config.size_weight, config.distance_weight),
            (1.0, 1.0, 1.0, 1.0),
        )
        for name in ("min_iou", "min_size_ratio", "max_distance", "max_capture_interval_seconds"):
            self.assertIsNone(getattr(config, name), name)
        self.assertTrue(config.skip_if_human_identifications)
        self.assertTrue(config.require_fresh_event)

    def test_exactly_one_scope(self):
        with self.assertRaises(pydantic.ValidationError):
            TrackingConfig()
        with self.assertRaises(pydantic.ValidationError):
            TrackingConfig(source_image_collection_id=1, event_ids=[1])
        TrackingConfig(source_image_collection_id=1)

    def test_values_outside_their_range_are_rejected(self):
        for bad in (
            {"min_iou": 1.5},
            {"min_size_ratio": -0.1},
            {"max_distance": -1},
            {"max_capture_interval_seconds": 0},
            {"iou_weight": -1},
            {"cost_threshold": -1},
            {"unknown_option": 1},
        ):
            with self.subTest(bad), self.assertRaises(pydantic.ValidationError):
                _config(**bad)

    def test_every_tunable_has_a_title_and_help_text(self):
        for name, field in TrackingConfig.__fields__.items():
            if name in ("source_image_collection_id", "event_ids"):
                continue
            self.assertTrue(field.field_info.title, name)
            self.assertTrue(field.field_info.description, name)


class TestPairCost(SimpleTestCase):
    def test_default_cost_is_the_plain_sum_of_the_three_terms(self):
        shifted = [150, 100, 250, 200]
        # IoU with the +1 pixel convention: overlap 51x101, union 2*101*101 - 51*101.
        expected = (1 - 51 * 101 / (2 * 101 * 101 - 51 * 101)) + 0.0 + 50 / DIAG
        self.assertAlmostEqual(pair_cost(BOX, shifted, DIAG, _config()), expected)

    def test_identical_boxes_cost_nothing(self):
        self.assertAlmostEqual(pair_cost(BOX, BOX, DIAG, _config()), 0.0)

    def test_weights_scale_their_term(self):
        shifted = [150, 100, 250, 200]
        base = pair_cost(BOX, shifted, DIAG, _config())
        no_overlap_term = pair_cost(BOX, shifted, DIAG, _config(iou_weight=0))
        self.assertAlmostEqual(base - no_overlap_term, 1 - 51 * 101 / (2 * 101 * 101 - 51 * 101))
        self.assertAlmostEqual(pair_cost(BOX, shifted, DIAG, _config(distance_weight=2)), base + 50 / DIAG)
        smaller = [100, 100, 150, 150]
        self.assertAlmostEqual(
            pair_cost(BOX, smaller, DIAG, _config(size_weight=0)),
            pair_cost(BOX, smaller, DIAG, _config(size_weight=3)) - 3 * (1 - 51 * 51 / (101 * 101)),
        )

    def test_each_enabled_limit_rejects_a_pair_that_fails_it(self):
        shifted = [150, 100, 250, 200]  # IoU about 0.33, same size, centres 50 px apart
        smaller = [100, 100, 150, 150]  # smaller box: size ratio about 0.25
        self.assertIsNotNone(pair_cost(BOX, shifted, DIAG, _config(min_iou=0.3)))
        self.assertIsNone(pair_cost(BOX, shifted, DIAG, _config(min_iou=0.5)))
        self.assertIsNotNone(pair_cost(BOX, smaller, DIAG, _config(min_size_ratio=0.2)))
        self.assertIsNone(pair_cost(BOX, smaller, DIAG, _config(min_size_ratio=0.5)))
        self.assertIsNotNone(pair_cost(BOX, shifted, DIAG, _config(max_distance=0.05)))
        self.assertIsNone(pair_cost(BOX, shifted, DIAG, _config(max_distance=0.03)))

    def test_a_pair_failing_a_limit_is_not_a_candidate_even_at_a_huge_cutoff(self):
        links = select_links([(1, BOX)], [(2, [150, 100, 250, 200])], DIAG, _config(min_iou=0.9, cost_threshold=99))
        self.assertEqual(links, [])

    def test_links_are_one_to_one_and_lowest_cost_wins(self):
        left, right = [100, 100, 200, 200], [700, 700, 800, 800]
        links = select_links(
            [(1, left), (2, right)], [(3, [705, 700, 805, 800]), (4, [110, 100, 210, 200])], DIAG, _config()
        )
        self.assertEqual([(a, b) for a, b, _ in links], [(2, 3), (1, 4)])
        self.assertLessEqual(links[0][2], links[1][2])

        # Two detections competing for one target: only one links, and a tie goes to the lower id.
        links = select_links([(1, BOX), (2, BOX)], [(3, BOX)], DIAG, _config())
        self.assertEqual([(a, b) for a, b, _ in links], [(1, 3)])


class TestIntervalLimit(SimpleTestCase):
    def test_interval_limit(self):
        t0 = datetime.datetime(2026, 7, 1, 22, 0, 0)
        near, far = t0 + datetime.timedelta(seconds=20), t0 + datetime.timedelta(seconds=45)
        first = t0
        self.assertFalse(captures_too_far_apart(first, far, _config()))
        config = _config(max_capture_interval_seconds=30)
        self.assertFalse(captures_too_far_apart(first, near, config))
        self.assertTrue(captures_too_far_apart(first, far, config))
        self.assertTrue(captures_too_far_apart(first, None, config))
