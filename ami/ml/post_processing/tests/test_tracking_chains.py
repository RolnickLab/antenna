"""The merge plan a tracking run works out from links and the current grouping, without a database."""

from unittest import TestCase

from ami.ml.post_processing.tracking.chains import merge_groups


class TestMergeGroups(TestCase):
    def test_a_linked_chain_merges_into_the_first_occurrence(self):
        groups = merge_groups([1, 2, 3], {1: 10, 2: 20, 3: 30}, {1: 2, 2: 3}, {1: 0.1, 2: 0.2})

        self.assertEqual(len(groups), 1)
        group = groups[0]
        self.assertEqual((group.detection_ids, group.keeper_id), ([1, 2, 3], 10))
        self.assertEqual(group.previous_occurrence_ids, [10, 20, 30])
        self.assertEqual(group.absorbed_ids, [20, 30])
        self.assertEqual(group.link_costs, [0.1, 0.2])

    def test_a_group_already_held_by_one_occurrence_is_left_out(self):
        self.assertEqual(merge_groups([1, 2], {1: 10, 2: 10}, {1: 2}, {}), [])

    def test_detections_sharing_an_occurrence_stay_together(self):
        """Linking one detection of an occurrence brings the whole occurrence, so nothing is split."""
        groups = merge_groups([1, 2, 3], {1: 10, 2: 20, 3: 10}, {2: 3}, {2: 0.5})

        self.assertEqual(len(groups), 1)
        self.assertEqual((groups[0].detection_ids, groups[0].keeper_id), ([1, 2, 3], 10))

    def test_a_group_without_an_occurrence_has_no_keeper(self):
        groups = merge_groups([1, 2], {1: None, 2: None}, {1: 2}, {1: 0.3})

        self.assertEqual([(g.detection_ids, g.keeper_id) for g in groups], [([1, 2], None)])

    def test_the_keeper_is_the_first_occurrence_in_capture_order(self):
        groups = merge_groups([5, 1], {5: 50, 1: 10}, {5: 1}, {5: 0.1})

        self.assertEqual(groups[0].keeper_id, 50)

    def test_a_link_to_a_detection_outside_the_plan_is_ignored(self):
        self.assertEqual(merge_groups([1], {1: 10}, {1: 99}, {}), [])
