from django_pydantic_field.rest_framework import SchemaField
from rest_framework import serializers

from ami.main.api.serializers import DefaultSerializer
from ami.main.models import Project

from .models.algorithm import Algorithm
from .models.backend import Backend
from .models.pipeline import Pipeline, PipelineStage


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
            "created_at",
            "updated_at",
        ]


class BackendNestedSerializer(DefaultSerializer):
    class Meta:
        model = Backend
        fields = [
            "name",
            "slug",
            "id",
            "details",
            "endpoint_url",
            "last_checked",
            "last_checked_live",
            "created_at",
            "updated_at",
        ]


class PipelineSerializer(DefaultSerializer):
    algorithms = AlgorithmSerializer(many=True, read_only=True)
    stages = SchemaField(schema=list[PipelineStage], read_only=True)
    backends = BackendNestedSerializer(many=True, read_only=True)

    class Meta:
        model = Pipeline
        fields = [
            "id",
            "details",
            "name",
            "slug",
            "description",
            "algorithms",
            "stages",
            "backends",
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
            "created_at",
            "updated_at",
        ]


class BackendSerializer(DefaultSerializer):
    pipelines = PipelineNestedSerializer(many=True, read_only=True)
    project = serializers.PrimaryKeyRelatedField(
        write_only=True,
        queryset=Project.objects.all(),
        required=False,
    )

    class Meta:
        model = Backend
        fields = [
            "id",
            "details",
            "name",
            "slug",
            "description",
            "projects",
            "project",
            "endpoint_url",
            "pipelines",
            "created_at",
            "updated_at",
            "last_checked",
            "last_checked_live",
        ]

    def create(self, validated_data):
        project = validated_data.pop("project", None)
        instance = super().create(validated_data)

        if project:
            instance.projects.add(project)

        return instance
