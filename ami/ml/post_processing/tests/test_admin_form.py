"""Tests for ``BasePostProcessingActionForm`` + concrete ``SmallSizeFilterActionForm``."""
from django.test import TestCase

from ami.ml.post_processing.admin.forms import BasePostProcessingActionForm
from ami.ml.post_processing.admin.small_size_filter_form import SmallSizeFilterActionForm


class _OneFieldForm(BasePostProcessingActionForm):
    from django import forms

    threshold = forms.FloatField(initial=0.5)


class TestBasePostProcessingActionForm(TestCase):
    def test_to_config_returns_cleaned_data(self):
        form = _OneFieldForm(data={"threshold": "0.25"})
        self.assertTrue(form.is_valid())
        self.assertEqual(form.to_config(), {"threshold": 0.25})


class TestSmallSizeFilterActionForm(TestCase):
    def test_default_initial_matches_config_default(self):
        form = SmallSizeFilterActionForm()
        self.assertEqual(form.fields["size_threshold"].initial, 0.0008)

    def test_valid_threshold_passes(self):
        form = SmallSizeFilterActionForm(data={"size_threshold": "0.001"})
        self.assertTrue(form.is_valid())
        self.assertEqual(form.to_config(), {"size_threshold": 0.001})

    def test_threshold_above_one_rejected(self):
        form = SmallSizeFilterActionForm(data={"size_threshold": "1.5"})
        self.assertFalse(form.is_valid())
        self.assertIn("size_threshold", form.errors)

    def test_threshold_zero_rejected(self):
        # 0.0 is excluded (open interval); django's min_value=0.0 admits zero,
        # so the clean_size_threshold check is the gate.
        form = SmallSizeFilterActionForm(data={"size_threshold": "0.0"})
        self.assertFalse(form.is_valid())
        self.assertIn("size_threshold", form.errors)

    def test_threshold_at_one_rejected(self):
        form = SmallSizeFilterActionForm(data={"size_threshold": "1.0"})
        self.assertFalse(form.is_valid())
        self.assertIn("size_threshold", form.errors)
