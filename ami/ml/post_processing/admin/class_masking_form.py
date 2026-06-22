from __future__ import annotations

from django import forms

from ami.main.models import TaxaList
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

    def to_config(self) -> dict:
        return {
            "algorithm_id": self.cleaned_data["algorithm_id"].pk,
            "taxa_list_id": self.cleaned_data["taxa_list_id"].pk,
        }
