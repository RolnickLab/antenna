from django_pydantic_field.rest_framework import SchemaField

from ami.main.api.serializers import DefaultSerializer

from .models.algorithm import Algorithm
from .models.pipeline import Pipeline, PipelineStage


class AlgorithmSerializer(DefaultSerializer):
    class Meta:
        model = Algorithm
        fields = [
            "id",
            "name",
            "version",
            "details",
            "created_at",
        ]


class PipelineSerializer(DefaultSerializer):
    algorithms = AlgorithmSerializer(many=True, read_only=True)
    stages = SchemaField(schema=list[PipelineStage], read_only=True)

    class Meta:
        model = Pipeline
        fields = [
            "id",
            "details",
            "name",
            "description",
            "version",
            "algorithms",
            "stages",
            "created_at",
            "updated_at",
        ]


class PipelineNestedSerializer(DefaultSerializer):
    class Meta:
        model = Pipeline
        fields = [
            "id",
            "details",
            "name",
            "created_at",
            "updated_at",
        ]
