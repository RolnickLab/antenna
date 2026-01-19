from django_pydantic_field.rest_framework import SchemaField
from rest_framework import serializers

from ami.exports.models import DataExport
from ami.main.api.serializers import (
    DefaultSerializer,
    DeploymentNestedSerializer,
    SourceImageCollectionNestedSerializer,
    SourceImageNestedSerializer,
)
from ami.main.models import Deployment, Project, SourceImage, SourceImageCollection
from ami.ml.models import Pipeline
from ami.ml.serializers import PipelineNestedSerializer

from .models import Job, JobLogs, JobProgress, MLJob


class JobProjectNestedSerializer(DefaultSerializer):
    class Meta:
        model = Project
        fields = [
            "id",
            "name",
            "details",
        ]


class DataExportNestedSerializer(serializers.ModelSerializer):
    file_url = serializers.URLField(read_only=True)

    class Meta:
        model = DataExport
        fields = ["id", "user", "project", "format", "filters", "file_url"]


class JobTypeSerializer(serializers.Serializer):
    name = serializers.CharField(read_only=True)
    key = serializers.SlugField(read_only=True)


class JobListSerializer(DefaultSerializer):
    delay = serializers.IntegerField()
    project = JobProjectNestedSerializer(read_only=True)
    deployment = DeploymentNestedSerializer(read_only=True)
    pipeline = PipelineNestedSerializer(read_only=True)
    source_image_collection = SourceImageCollectionNestedSerializer(read_only=True)
    source_image_single = SourceImageNestedSerializer(read_only=True)
    data_export = DataExportNestedSerializer(read_only=True)
    progress = SchemaField(schema=JobProgress, read_only=True)
    logs = SchemaField(schema=JobLogs, read_only=True)
    job_type = JobTypeSerializer(read_only=True)
    # All jobs created from the Jobs UI are ML jobs (datasync, etc. are created for the user)
    # @TODO Remove this when the UI is updated pass a job type. This should be a required field.
    job_type_key = serializers.SlugField(write_only=True, default=MLJob.key)

    project_id = serializers.PrimaryKeyRelatedField(
        label="Project",
        write_only=True,
        # @TODO this should be filtered by projects belonging to current user
        queryset=Project.objects.all(),
        source="project",
    )
    deployment_id = serializers.PrimaryKeyRelatedField(
        label="Deployment",
        write_only=True,
        required=False,
        allow_null=True,
        # @TODO should this be filtered by project (from URL for new job?)
        queryset=Deployment.objects.all(),
        source="deployment",
    )
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
            "delay",
            "limit",
            "shuffle",
            "project",
            "project_id",
            "deployment",
            "deployment_id",
            "source_image_collection",
            "source_image_collection_id",
            "source_image_single",
            "source_image_single_id",
            "pipeline",
            "pipeline_id",
            "status",
            "created_at",
            "updated_at",
            "started_at",
            "finished_at",
            "duration",
            "progress",
            "logs",
            "job_type",
            "job_type_key",
            "data_export",
            # "duration",
            # "duration_label",
            # "progress_label",
            # "progress_percent",
            # "progress_percent_label",
        ]

        read_only_fields = [
            "status",
            "progress",  # Make writable during testing
            "result",
            "started_at",
            "finished_at",
            "duration",
        ]


class JobSerializer(JobListSerializer):
    # progress = serializers.JSONField(initial=Job.default_progress(), allow_null=False, required=False)

    class Meta(JobListSerializer.Meta):
        fields = JobListSerializer.Meta.fields + [
            "result",
        ]


class MinimalJobSerializer(DefaultSerializer):
    """Minimal serializer returning only essential job fields."""

    class Meta:
        model = Job
        # Add other fields when needed, e.g:  "name", "status", "created_at"
        fields = ["id"]
