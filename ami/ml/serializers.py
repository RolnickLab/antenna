from django_pydantic_field.rest_framework import SchemaField

from ami.main.api.serializers import DefaultSerializer

from .models.algorithm import Algorithm, AlgorithmCategoryMap
from .models.pipeline import Pipeline, PipelineStage


class AlgorithmCategoryMapSerializer(DefaultSerializer):
    class Meta:
        model = AlgorithmCategoryMap
        fields = [
            "id",
            "labels",
            "data",
            "algorithms",
            "version",
            "url",
            "created_at",
            "updated_at",
        ]


class AlgorithmSerializer(DefaultSerializer):
    class Meta:
        model = Algorithm
        fields = [
            "id",
            "details",
            "name",
            "key",
            "description",
            "url",
            "version",
            "version_name",
            "task_type",
            "category_map",
            "created_at",
            "updated_at",
        ]


class AlgorithmNestedSerializer(DefaultSerializer):
    class Meta:
        model = Algorithm
        fields = [
            "id",
            "details",
            "name",
            "key",
            "version",
            "version_name",
            "task_type",
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
            "slug",
            "description",
            "version",
            "version_name",
            "algorithms",
            "stages",
            "endpoint_url",
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
            "slug",
            "description",
            "version",
            "version_name",
        ]
