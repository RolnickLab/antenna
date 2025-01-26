from django_pydantic_field.rest_framework import SchemaField
from rest_framework import serializers

from ami.main.api.serializers import DefaultSerializer
from ami.main.models import Project

from .models.algorithm import Algorithm
from .models.pipeline import Pipeline, PipelineStage
from .models.processing_service import ProcessingService


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


class ProcessingServiceNestedSerializer(DefaultSerializer):
    class Meta:
        model = ProcessingService
        fields = [
            "name",
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
    processing_services = ProcessingServiceNestedSerializer(many=True, read_only=True)

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
            "processing_services",
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


class ProcessingServiceSerializer(DefaultSerializer):
    pipelines = PipelineNestedSerializer(many=True, read_only=True)
    project = serializers.PrimaryKeyRelatedField(
        write_only=True,
        queryset=Project.objects.all(),
        required=False,
    )

    class Meta:
        model = ProcessingService
        fields = [
            "id",
            "details",
            "name",
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
