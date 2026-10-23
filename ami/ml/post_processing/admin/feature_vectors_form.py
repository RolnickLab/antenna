from __future__ import annotations

from django import forms

from ami.ml.models import Pipeline
from ami.ml.post_processing.admin.forms import BasePostProcessingActionForm
from ami.ml.post_processing.feature_vectors import AddFeatureVectorsConfig

_FIELDS = AddFeatureVectorsConfig.__fields__


class AddFeatureVectorsActionForm(BasePostProcessingActionForm):
    """Knobs surfaced when an admin triggers Add feature vectors.

    The pipeline choice lists only pipelines with an algorithm that produces feature vectors,
    narrowed to those enabled for the projects of the selected capture sets. The valid range of
    ``batch_size`` lives on ``AddFeatureVectorsConfig``; the admin action surfaces its errors inline.
    """

    pipeline_id = forms.ModelChoiceField(
        queryset=Pipeline.objects.none(),
        label=_FIELDS["pipeline_id"].field_info.title,
        help_text=_FIELDS["pipeline_id"].field_info.description,
    )
    batch_size = forms.IntegerField(
        label=_FIELDS["batch_size"].field_info.title,
        initial=_FIELDS["batch_size"].default,
        help_text=_FIELDS["batch_size"].field_info.description,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        pipelines = Pipeline.objects.filter(algorithms__embedding_dimensions__isnull=False)
        if self.scope_queryset is not None:
            project_ids = set(self.scope_queryset.values_list("project_id", flat=True))
            pipelines = pipelines.filter(
                project_pipeline_configs__enabled=True, project_pipeline_configs__project_id__in=project_ids
            )
        self.fields["pipeline_id"].queryset = pipelines.distinct().order_by("name")

    def to_config(self) -> dict:
        return {
            "pipeline_id": self.cleaned_data["pipeline_id"].pk,
            "batch_size": self.cleaned_data["batch_size"],
        }
