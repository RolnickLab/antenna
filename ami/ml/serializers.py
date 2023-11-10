from ami.main.api.serializers import DefaultSerializer

from .models.pipeline import Pipeline


class PipelineNestedSerializer(DefaultSerializer):
    class Meta:
        model = Pipeline
        fields = [
            "id",
            "name",
            "details",
            "created_at",
            "updated_at",
        ]
