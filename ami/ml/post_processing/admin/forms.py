"""Form base for admin actions that trigger post-processing tasks.

Each post-processing task surfaces its tunable knobs as a Django form. The
form's ``cleaned_data`` becomes the ``config`` payload on the resulting Job
(after validation against the task's pydantic ``config_schema``).

Algorithm scope (which queryset/events/collection the action runs against)
lives outside the form because it varies per admin entry-point.
"""
from __future__ import annotations

from django import forms


class BasePostProcessingActionForm(forms.Form):
    """Marker base for post-processing admin action forms.

    Subclasses declare task-specific fields. Override ``to_config()`` if the
    1:1 ``cleaned_data → config`` mapping needs adjustment (e.g. drop empty
    optional fields, derive computed values, rename keys).
    """

    def to_config(self) -> dict:
        """Return ``cleaned_data`` shaped for ``Job.params['config']``."""
        return dict(self.cleaned_data)
