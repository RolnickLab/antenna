"""Tests for ``BasePostProcessingActionForm`` + concrete ``SmallSizeFilterActionForm``.

The knob form only declares field presentation; the valid range for
``size_threshold`` is owned by ``SmallSizeFilterConfig`` (the schema), not the
form. Bound enforcement therefore lives in ``test_base_schema.py`` and in the
admin-action flow (``test_small_size_filter_admin.py`` /
``test_action_factory.py``), not here. The happy valid-value path is likewise
covered end to end by those flows. Forms never touch the DB → SimpleTestCase.
"""
from django import forms
from django.test import SimpleTestCase

from ami.ml.post_processing.admin.forms import BasePostProcessingActionForm
from ami.ml.post_processing.admin.small_size_filter_form import SmallSizeFilterActionForm


class _OneFieldForm(BasePostProcessingActionForm):
    threshold = forms.FloatField(initial=0.5)


class TestBasePostProcessingActionForm(SimpleTestCase):
    def test_to_config_returns_cleaned_data(self):
        form = _OneFieldForm(data={"threshold": "0.25"})
        self.assertTrue(form.is_valid())
        self.assertEqual(form.to_config(), {"threshold": 0.25})


class TestSmallSizeFilterActionForm(SimpleTestCase):
    def test_default_initial_matches_config_default(self):
        form = SmallSizeFilterActionForm()
        self.assertEqual(form.fields["size_threshold"].initial, 0.0008)

    def test_non_numeric_threshold_rejected_at_form_layer(self):
        # Type coercion is still the form's job; range is not.
        form = SmallSizeFilterActionForm(data={"size_threshold": "not-a-number"})
        self.assertFalse(form.is_valid())
        self.assertIn("size_threshold", form.errors)

    def test_out_of_range_threshold_passes_form_but_is_rejected_by_schema(self):
        # The form no longer enforces the (0, 1) bound — that is the schema's job.
        # An out-of-range value is a valid float, so the form accepts it; the admin
        # action then rejects it when validating against SmallSizeFilterConfig.
        form = SmallSizeFilterActionForm(data={"size_threshold": "2.0"})
        self.assertTrue(form.is_valid())
        self.assertEqual(form.to_config(), {"size_threshold": 2.0})
