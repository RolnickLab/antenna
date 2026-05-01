from __future__ import annotations

from django import forms

from ami.ml.post_processing.admin.forms import BasePostProcessingActionForm
from ami.ml.post_processing.small_size_filter import SmallSizeFilterConfig


class SmallSizeFilterActionForm(BasePostProcessingActionForm):
    """Knobs surfaced when an admin triggers Small Size Filter."""

    size_threshold = forms.FloatField(
        label="Size threshold",
        initial=SmallSizeFilterConfig.__fields__["size_threshold"].default,
        min_value=0.0,
        max_value=1.0,
        help_text=(
            "Minimum bounding-box area as a fraction of the source image area "
            "(width × height). Detections smaller than this are flagged as "
            "'Not identifiable'. Default 0.0008 ≈ 0.08% of frame area."
        ),
    )

    def clean_size_threshold(self) -> float:
        v = self.cleaned_data["size_threshold"]
        if not (0.0 < v < 1.0):
            raise forms.ValidationError("size_threshold must be in (0, 1) exclusive.")
        return v
