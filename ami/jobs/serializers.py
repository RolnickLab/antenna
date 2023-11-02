from rest_framework import serializers

from ami.main.api.serializers import (
    DefaultSerializer,
    DeploymentNestedSerializer,
    PipelineNestedSerializer,
    ProjectNestedSerializer,
    SourceImageCollectionSerializer,
    SourceImageNestedSerializer,
)
from ami.main.models import Pipeline, Project, SourceImage, SourceImageCollection

from .models import Job


class JobListSerializer(DefaultSerializer):
    project = ProjectNestedSerializer(read_only=True)
    deployment = DeploymentNestedSerializer(read_only=True)
    pipeline = PipelineNestedSerializer(read_only=True)
    source_image_collection = SourceImageCollectionSerializer(read_only=True)
    source_image_single = SourceImageNestedSerializer(read_only=True)
    source_image_single_id = serializers.PrimaryKeyRelatedField(
        label="Source Image",
        write_only=True,
        required=False,
        allow_null=True,
        # @TODO should this be filtered by project (from URL for new job?)
        queryset=SourceImage.objects.all(),
        source="source_image_single",
    )
    source_image_collection_id = serializers.PrimaryKeyRelatedField(
        label="Source Image Collection",
        write_only=True,
        required=False,
        allow_null=True,
        # @TODO should this be filtered by project (from URL for new job?)
        queryset=SourceImageCollection.objects.all(),
        source="source_image_collection",
    )
    pipeline_id = serializers.PrimaryKeyRelatedField(
        label="Pipeline",
        write_only=True,
        required=False,
        allow_null=True,
        # @TODO should this be filtered by project (from URL for new job?)
        queryset=Pipeline.objects.all(),
        source="pipeline",
    )

    class Meta:
        model = Job
        fields = [
            "id",
            "details",
            "name",
            "project",
            "deployment",
            "source_image_collection",
            "source_image_collection_id",
            "source_image_single",
            "source_image_single_id",
            "pipeline",
            "pipeline_id",
            "status",
            "progress",
            "started_at",
            "finished_at",
            # "duration",
            # "duration_label",
            # "progress",
            # "progress_label",
            # "progress_percent",
            # "progress_percent_label",
        ]

        read_only_fields = [
            "status",
            "progress",
            "result",
            "started_at",
            "finished_at",
            # "duration",
        ]


class JobSerializer(JobListSerializer):
    project = ProjectNestedSerializer(read_only=True)
    project_id = serializers.PrimaryKeyRelatedField(write_only=True, queryset=Project.objects.all(), source="project")
    config = serializers.JSONField(initial=Job.default_config(), allow_null=False, required=False)

    class Meta(JobListSerializer.Meta):
        fields = JobListSerializer.Meta.fields + [
            "config",
            "result",
            "project",
            "project_id",
        ]
