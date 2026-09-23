"""Forms for triggering post-processing tasks from the Django admin.

Each form is the single source of truth for the human-readable labels,
help-text, and validation rules of one task's tunable parameters. The form's
`cleaned_data` becomes the ``config`` dict on the resulting Job.

Algorithm scope (which events / collection / queryset) lives outside the form
because it varies per admin entry-point — see the per-action helpers in
``ami/main/admin.py``.
"""
from __future__ import annotations

from django import forms
from django.db.models import QuerySet

from ami.main.models import Classification, Event
from ami.ml.models import Algorithm
from ami.ml.post_processing.tracking_task import DEFAULT_TRACKING_PARAMS


def _feature_algorithm_choices_for_events(events: QuerySet[Event]) -> list[tuple[int, str]]:
    """Algorithms that produced ``features_2048`` on the given events.

    Scoped to the operator's selection so the dropdown stays bounded on
    production-sized DBs and never reveals algorithms from other projects.
    """
    algorithm_ids = (
        Classification.objects.filter(
            detection__source_image__event__in=events,
            features_2048__isnull=False,
            algorithm_id__isnull=False,
        )
        .values_list("algorithm_id", flat=True)
        .distinct()
    )
    return [
        (a.pk, f"{a.name} (#{a.pk})") for a in Algorithm.objects.filter(pk__in=list(algorithm_ids)).order_by("name")
    ]


class TrackingActionForm(forms.Form):
    """Knobs surfaced when an admin triggers Occurrence Tracking.

    Pass the events the action will run on as ``events`` so the
    feature-extraction-algorithm dropdown is scoped correctly. The class is
    constructed once for the GET (rendering defaults) and once for the POST
    (validating submitted values); pass the same queryset both times.
    """

    cost_threshold = forms.FloatField(
        label="Cost threshold",
        initial=DEFAULT_TRACKING_PARAMS.cost_threshold,
        min_value=0.0,
        help_text=(
            "Maximum sum of (1 - cosine similarity) + (1 - IoU) + (1 - box ratio) + "
            "(distance / image diagonal) for two detections to be considered the "
            "same individual. Lower = stricter matching, fewer false links. "
            "Default 0.2 is calibrated against synthetic features; tune per dataset."
        ),
    )

    skip_if_human_identifications = forms.BooleanField(
        label="Skip events with human identifications",
        initial=DEFAULT_TRACKING_PARAMS.skip_if_human_identifications,
        required=False,
        help_text=(
            "If checked, events that already have any user-confirmed identification "
            "are skipped to preserve manual review work. Recommended on."
        ),
    )

    require_fresh_event = forms.BooleanField(
        label="Require fresh event (v1)",
        initial=DEFAULT_TRACKING_PARAMS.require_fresh_event,
        required=False,
        help_text=(
            "v1 only handles events where every detection has its own auto-created "
            "occurrence (1:1) and no chain links exist. Skip already-tracked events. "
            "Re-tracking lands in v2."
        ),
    )

    feature_extraction_algorithm_id = forms.ChoiceField(
        label="Feature extraction algorithm",
        required=False,
        help_text=(
            "Override the algorithm whose embeddings are used for matching. Leave "
            "blank to auto-detect (works when only one feature-extracting algorithm "
            "ran on the event). Required when multiple algorithms have produced "
            "embeddings on the same event."
        ),
    )

    def __init__(self, *args, events: QuerySet[Event] | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        choices: list[tuple[str, str]] = [("", "— auto-detect —")]
        if events is not None:
            choices.extend((str(pk), label) for pk, label in _feature_algorithm_choices_for_events(events))
        self.fields["feature_extraction_algorithm_id"].choices = choices

    def to_config(self) -> dict:
        """Return the ``cleaned_data`` shape the TrackingTask expects in ``Job.params['config']``.

        Drops the algorithm override when blank so ``_params()`` falls through to
        auto-detection rather than logging an "unknown key" warning.
        """
        if not self.is_valid():
            raise ValueError(f"TrackingActionForm has errors: {self.errors.as_text()}")
        config = {
            "cost_threshold": self.cleaned_data["cost_threshold"],
            "skip_if_human_identifications": self.cleaned_data["skip_if_human_identifications"],
            "require_fresh_event": self.cleaned_data["require_fresh_event"],
        }
        algo_id_str = self.cleaned_data.get("feature_extraction_algorithm_id") or ""
        if algo_id_str:
            config["feature_extraction_algorithm_id"] = int(algo_id_str)
        return config
