from __future__ import annotations

from django import forms

from ami.main.models import Occurrence, SourceImageCollection, TaxaList
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
        # When the admin hands us the selected scope, only offer classifiers that
        # actually produced classifications there — masking any other algorithm is
        # a no-op for the selected rows. Without a scope (e.g. used standalone) the
        # field keeps its full classifier list.
        if self.scope_queryset is not None:
            self.fields["algorithm_id"].queryset = self._algorithms_for_scope(self.scope_queryset)

    @staticmethod
    def _algorithms_for_scope(scope_queryset):
        """Classification algorithms that produced classifications within the
        selected scope (the chosen occurrences or collections)."""
        algorithms = Algorithm.objects.filter(task_type=AlgorithmTaskType.CLASSIFICATION.value)
        model = scope_queryset.model
        if model is Occurrence:
            algorithms = algorithms.filter(classifications__detection__occurrence__in=scope_queryset)
        elif model is SourceImageCollection:
            algorithms = algorithms.filter(classifications__detection__source_image__collections__in=scope_queryset)
        return algorithms.distinct().order_by("name")

    def to_config(self) -> dict:
        return {
            "algorithm_id": self.cleaned_data["algorithm_id"].pk,
            "taxa_list_id": self.cleaned_data["taxa_list_id"].pk,
        }
