from __future__ import annotations

from django import forms

from ami.ml.post_processing.admin.forms import BasePostProcessingActionForm
from ami.ml.post_processing.small_size_filter import SmallSizeFilterConfig


class SmallSizeFilterActionForm(BasePostProcessingActionForm):
    """Knobs surfaced when an admin triggers Small Size Filter.

    The valid range for ``size_threshold`` lives on ``SmallSizeFilterConfig``
    (the single source of truth); this form only declares the field's
    presentation. The admin action validates submitted values against the
    schema and surfaces any error inline on this field.
    """

    size_threshold = forms.FloatField(
        label="Size threshold",
        initial=SmallSizeFilterConfig.__fields__["size_threshold"].default,
        help_text=(
            "Minimum bounding-box area as a fraction of the source image area "
            "(width × height). Detections smaller than this are flagged as "
            "'Not identifiable'. Must be between 0 and 1 (exclusive). "
            "Default 0.0008 ≈ 0.08% of frame area."
        ),
    )
