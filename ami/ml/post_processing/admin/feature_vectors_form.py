from __future__ import annotations

from django import forms

from ami.main.models import DEFAULT_EMBEDDING_KEY
from ami.ml.models import Pipeline
from ami.ml.models.algorithm import AlgorithmTaskType
from ami.ml.post_processing.admin.forms import BasePostProcessingActionForm
from ami.ml.post_processing.feature_vectors import AddFeatureVectorsConfig


class AddFeatureVectorsActionForm(BasePostProcessingActionForm):
    """Knobs surfaced when an admin triggers Add feature vectors.

    The pipeline choice lists only pipelines with an algorithm that produces feature vectors,
    narrowed to those enabled for the projects of the selected capture sets. The valid range of
    ``batch_size`` lives on ``AddFeatureVectorsConfig``; the admin action surfaces its errors inline.
    """

    pipeline_id = forms.ModelChoiceField(
        queryset=Pipeline.objects.none(),
        label="Pipeline",
        help_text="A pipeline with a feature extractor. Only detections that lack its vectors are sent.",
    )
    key = forms.CharField(
        label="Vector name",
        initial=DEFAULT_EMBEDDING_KEY,
        help_text="The name the vectors are stored under. Keep the default unless the extractor has several outputs.",
    )
    batch_size = forms.IntegerField(
        label="Captures per request",
        initial=AddFeatureVectorsConfig.__fields__["batch_size"].default,
        help_text="How many captures, with their missing detections, go to the processing service in one request.",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        pipelines = Pipeline.objects.filter(algorithms__task_type=AlgorithmTaskType.EMBEDDING.value)
        if self.scope_queryset is not None:
            project_ids = set(self.scope_queryset.values_list("project_id", flat=True))
            pipelines = pipelines.filter(
                project_pipeline_configs__enabled=True, project_pipeline_configs__project_id__in=project_ids
            )
        self.fields["pipeline_id"].queryset = pipelines.distinct().order_by("name")

    def to_config(self) -> dict:
        return {
            "pipeline_id": self.cleaned_data["pipeline_id"].pk,
            "key": self.cleaned_data["key"],
            "batch_size": self.cleaned_data["batch_size"],
        }
