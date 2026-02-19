from django_pydantic_field.rest_framework import SchemaField
from rest_framework import serializers

from ami.main.api.serializers import DefaultSerializer, MinimalNestedModelSerializer
from ami.main.models import Project

from .models.algorithm import Algorithm, AlgorithmCategoryMap
from .models.pipeline import Pipeline, PipelineStage
from .models.processing_service import ProcessingService
from .models.project_pipeline_config import ProjectPipelineConfig
from .schemas import PipelineConfigResponse


class AlgorithmCategoryMapSerializer(DefaultSerializer):
    class Meta:
        model = AlgorithmCategoryMap
        fields = [
            "id",
            "labels",
            "data",
            "algorithms",
            "version",
            "uri",
            "created_at",
            "updated_at",
        ]


MinimalCategoryMapNestedSerializer = MinimalNestedModelSerializer.create_for_model(AlgorithmCategoryMap)


class AlgorithmSerializer(DefaultSerializer):
    category_map = MinimalCategoryMapNestedSerializer(read_only=True, source="category_map_id")

    class Meta:
        model = Algorithm
        fields = [
            "id",
            "details",
            "name",
            "key",
            "description",
            "uri",
            "version",
            "version_name",
            "task_type",
            "category_map",
            "category_count",
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


class ProjectPipelineConfigSerializer(DefaultSerializer):
    class Meta:
        model = ProjectPipelineConfig
        fields = [
            "id",
            "project",
            "pipeline",
            "enabled",
            "config",
        ]


class PipelineSerializer(DefaultSerializer):
    algorithms = AlgorithmSerializer(many=True, read_only=True)
    stages = SchemaField(schema=list[PipelineStage], read_only=True)
    processing_services = ProcessingServiceNestedSerializer(many=True, read_only=True)
    project_pipeline_configs = ProjectPipelineConfigSerializer(many=True, read_only=True)

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
            "project_pipeline_configs",
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


class PipelineRegistrationSerializer(serializers.Serializer):
    processing_service_name = serializers.CharField()
    pipelines = SchemaField(schema=list[PipelineConfigResponse], default=[])
