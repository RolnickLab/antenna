from __future__ import annotations

from django import forms

from ami.main.models import Occurrence, TaxaList
from ami.ml.models import Algorithm
from ami.ml.models.algorithm import AlgorithmTaskType
from ami.ml.post_processing.admin.forms import BasePostProcessingActionForm


class ClassMaskingActionForm(BasePostProcessingActionForm):
    """Knobs surfaced when an admin triggers Class masking.

    The operator picks the source classifier and the taxa list to keep; the
    scope (which collection or occurrence) is supplied by the admin entry point,
    not the form. Selections are model instances, so ``to_config`` hands the
    schema their primary keys (``ClassMaskingConfig`` expects ``*_id`` ints).
    """

    algorithm_id = forms.ModelChoiceField(
        queryset=Algorithm.objects.filter(task_type=AlgorithmTaskType.CLASSIFICATION.value).order_by("name"),
        label="Source classifier",
        help_text="The classification algorithm whose terminal predictions will be re-scored.",
    )
    taxa_list_id = forms.ModelChoiceField(
        queryset=TaxaList.objects.all().order_by("name"),
        label="Taxa list to keep",
        help_text=(
            "Classes whose taxon is not in this list are masked out; each "
            "classification's softmax is renormalised over the classes that remain."
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Narrow the classifier dropdown to algorithms that actually produced
        # classifications in the selected scope, so the operator cannot pick a
        # classifier whose masking would be a no-op for the chosen rows. This is
        # only done for an occurrence scope, where the lookup touches the handful
        # of classifications under the picked occurrences. A collection scope
        # keeps the full classifier list on purpose: the equivalent lookup is an
        # unbounded DISTINCT over every classification in the collection (hundreds
        # of thousands of rows on a large collection) and can time out while the
        # form renders. An over-broad option is harmless — masking a classifier
        # that produced nothing in scope changes nothing.
        if self.scope_queryset is not None and self.scope_queryset.model is Occurrence:
            self.fields["algorithm_id"].queryset = self._algorithms_for_scope(self.scope_queryset)

    @staticmethod
    def _algorithms_for_scope(scope_queryset):
        """Classification algorithms that produced classifications within the
        selected occurrences."""
        return (
            Algorithm.objects.filter(
                task_type=AlgorithmTaskType.CLASSIFICATION.value,
                classifications__detection__occurrence__in=scope_queryset,
            )
            .distinct()
            .order_by("name")
        )

    def to_config(self) -> dict:
        return {
            "algorithm_id": self.cleaned_data["algorithm_id"].pk,
            "taxa_list_id": self.cleaned_data["taxa_list_id"].pk,
        }
