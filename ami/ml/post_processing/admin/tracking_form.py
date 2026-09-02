from __future__ import annotations

from django import forms

from ami.ml.models import Algorithm
from ami.ml.models.algorithm import AlgorithmTaskType
from ami.ml.post_processing.admin.forms import BasePostProcessingActionForm


class TrackingActionForm(BasePostProcessingActionForm):
    """Knobs surfaced when an admin triggers Occurrence Tracking.

    The scope (which capture set or events to track) comes from the admin entry
    point, not the form. Everything here tunes how detections are matched.
    """

    cost_threshold = forms.FloatField(
        initial=0.2,
        min_value=0.0,
        label="Matching cost threshold",
        help_text=(
            "Two detections in consecutive captures are linked when their matching cost "
            "falls below this. Cost rises with appearance difference, distance moved and "
            "change in box size, so a higher threshold links more detections and risks "
            "merging different insects. Without embeddings, start around 0.5."
        ),
    )
    require_features = forms.BooleanField(
        required=False,
        initial=True,
        label="Require feature embeddings",
        help_text=(
            "Only match detections that carry a model embedding. Turn this off to track "
            "captures processed before embeddings were stored; matching then uses bounding-box "
            "position and size alone, which is more permissive."
        ),
    )
    feature_extraction_algorithm_id = forms.ModelChoiceField(
        queryset=Algorithm.objects.filter(task_type=AlgorithmTaskType.CLASSIFICATION.value).order_by("name"),
        required=False,
        label="Feature extractor",
        help_text=(
            "Whose embeddings to compare. Leave blank to detect it automatically; set it when "
            "more than one classifier has run on the same session."
        ),
    )
    skip_if_human_identifications = forms.BooleanField(
        required=False,
        initial=True,
        label="Skip sessions with human identifications",
        help_text="Protects reviewed sessions: merging occurrences there would discard identifications.",
    )
    require_fresh_event = forms.BooleanField(
        required=False,
        initial=True,
        label="Only track untracked sessions",
        help_text=(
            "Skip sessions whose detections have already been grouped. Re-tracking grouped "
            "data is not supported yet, so leaving this on is the safe choice."
        ),
    )

    def to_config(self) -> dict:
        algorithm = self.cleaned_data["feature_extraction_algorithm_id"]
        return {
            "cost_threshold": self.cleaned_data["cost_threshold"],
            "require_features": self.cleaned_data["require_features"],
            "feature_extraction_algorithm_id": algorithm.pk if algorithm else None,
            "skip_if_human_identifications": self.cleaned_data["skip_if_human_identifications"],
            "require_fresh_event": self.cleaned_data["require_fresh_event"],
        }
