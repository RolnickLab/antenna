from __future__ import annotations

from ami.ml.post_processing.admin.forms import BasePostProcessingActionForm


class RankRollupActionForm(BasePostProcessingActionForm):
    """Knob form for Rank rollup.

    Rank rollup runs with the per-rank score thresholds and rollup order defined
    on ``RankRollupConfig``. There are no per-run knobs yet, so the form only
    confirms the selected capture set(s); the empty ``cleaned_data`` lets the
    schema apply its defaults. Threshold overrides can be added here later.
    """
