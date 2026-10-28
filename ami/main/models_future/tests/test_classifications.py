"""Tests for which classification arrays are stored and how scores are read back."""

from django.test import SimpleTestCase

from ami.main.models import Classification
from ami.main.models_future.classifications import arrays_to_store, probabilities
from ami.utils.stats import softmax


class TestArraysToStore(SimpleTestCase):
    """Only one copy of a classification's per-class information is stored when that loses nothing."""

    def test_scores_dropped_when_they_equal_softmax_of_logits(self):
        logits = [2.0, 1.0, 5.0]
        self.assertEqual(arrays_to_store(softmax(logits).tolist(), logits), (None, logits))

    def test_logits_dropped_when_they_are_probabilities(self):
        scores = softmax([2.0, 1.0, 5.0]).tolist()
        self.assertEqual(arrays_to_store(scores, list(scores)), (scores, None))

    def test_calibrated_scores_of_a_many_class_model_are_kept(self):
        """Tiny calibrated probabilities differ from softmax(logits) by less than an absolute 1e-4."""
        logits = [0.5 * ((i * 7919) % 101) / 101 for i in range(29_000)]
        calibrated = softmax([x / 1.5 for x in logits]).tolist()
        self.assertEqual(arrays_to_store(calibrated, logits), (calibrated, logits))

    def test_scores_kept_without_logits(self):
        self.assertEqual(arrays_to_store([0.9], None), ([0.9], None))


class TestProbabilities(SimpleTestCase):
    """A classification reports its probabilities whichever array it stores."""

    def test_softmax_of_logits_when_scores_are_not_stored(self):
        clf = Classification(scores=None, logits=[1.0, 3.0, 2.0])
        top = list(clf.top_scores_with_index(2))
        self.assertEqual([index for index, _ in top], [1, 2])
        self.assertAlmostEqual(top[0][1], softmax([1.0, 3.0, 2.0])[1], places=12)

    def test_stored_scores_take_precedence(self):
        self.assertEqual(probabilities([0.7, 0.2, 0.1], [1.0, 3.0, 2.0]), [0.7, 0.2, 0.1])

    def test_logits_that_are_probabilities_are_used_as_is(self):
        self.assertEqual(probabilities(None, [0.2, 0.8]), [0.2, 0.8])
