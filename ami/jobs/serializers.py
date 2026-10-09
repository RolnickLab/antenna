from django_pydantic_field.rest_framework import SchemaField
from drf_spectacular.utils import extend_schema_field
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
from ami.ml.schemas import PipelineProcessingTask, PipelineTaskResult, ProcessingServiceClientInfo, TrainingResult
from ami.ml.serializers import PipelineNestedSerializer

from .models import (
    JOB_LOGS_DEFAULT_LIMIT,
    Job,
    JobProgress,
    MLJob,
    _legacy_logs_shape,
    get_job_type_by_key,
    serialize_job_logs,
)
from .schemas import QueuedTaskAcknowledgment


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
    logs = serializers.SerializerMethodField()
    job_type = JobTypeSerializer(read_only=True)
    # All jobs created from the Jobs UI are ML jobs (datasync, etc. are created for the user)
    # @TODO Remove this when the UI is updated pass a job type. This should be a required field.
    job_type_key = serializers.SlugField(write_only=True, default=MLJob.key)
    # Settings a job type reads from its own params, such as which algorithm to retrain and
    # what split to hold out. Kept as one field rather than a column per type: only the type
    # knows what its params mean, and it is the type that validates them when it runs.
    params = serializers.JSONField(required=False, allow_null=True)

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
        label="Capture Set",
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
            "params",
            "data_export",
            "dispatch_mode",
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
            "dispatch_mode",
        ]

    def validate(self, attrs):
        """
        Refuse a job its type could not run, while it is still being created.

        A missing setting is otherwise found minutes later by the worker, which leaves a
        failed job in the list and a person wondering what they got wrong. Only creation is
        checked: an existing job's type cannot be changed.
        """
        attrs = super().validate(attrs)
        if self.instance is not None:
            return attrs

        job_type_key = attrs.get("job_type_key") or MLJob.key
        job_type = get_job_type_by_key(job_type_key)
        if not job_type:
            raise serializers.ValidationError({"job_type_key": f"Unknown job type '{job_type_key}'."})
        # ``user_creatable`` is not enforced here: several types the platform creates as a
        # side effect are also posted directly by existing clients. It says which types a
        # job form should offer as a choice, which is the UI's question, not the API's.

        missing_fields = [name for name in job_type.required_fields if not attrs.get(name)]
        if missing_fields:
            raise serializers.ValidationError(
                {f"{name}_id": f"A {job_type.name} job needs this." for name in missing_fields}
            )

        params = attrs.get("params") or {}
        missing_params = [name for name in job_type.required_params if not params.get(name)]
        if missing_params:
            raise serializers.ValidationError(
                {"params": f"A {job_type.name} job needs {', '.join(missing_params)} in its params."}
            )
        return attrs

    @extend_schema_field(
        {
            "type": "object",
            "properties": {
                "stdout": {"type": "array", "items": {"type": "string"}, "title": "All messages"},
                "stderr": {"type": "array", "items": {"type": "string"}, "title": "Error messages"},
            },
            "required": ["stdout", "stderr"],
        }
    )
    def get_logs(self, obj: Job) -> dict[str, list[str]]:
        # List responses skip the JobLog query to avoid N+1 — the UI only renders
        # logs on the detail page, so returning the (typically empty for new jobs)
        # legacy JSON shape is acceptable. Detail responses go to the joined table
        # and fall back to the legacy shape for pre-migration jobs.
        view = self.context.get("view")
        if getattr(view, "action", None) == "list":
            return _legacy_logs_shape(obj)
        # ``JobViewSet.get_serializer_context`` validates ``?logs_limit=`` and
        # puts the cleaned int (or ``None`` when unset) on context, so a bad
        # value already 400'd before we got here.
        limit = self.context.get("logs_limit") or JOB_LOGS_DEFAULT_LIMIT
        return serialize_job_logs(obj, limit=limit)


class JobSerializer(JobListSerializer):
    # progress = serializers.JSONField(initial=Job.default_progress(), allow_null=False, required=False)

    class Meta(JobListSerializer.Meta):
        fields = JobListSerializer.Meta.fields + [
            "result",
        ]


class MinimalJobSerializer(DefaultSerializer):
    """Minimal serializer returning only essential job fields."""

    pipeline_slug = serializers.CharField(source="pipeline.slug", read_only=True, allow_null=True)

    class Meta:
        model = Job
        fields = ["id", "pipeline_slug"]


class JobChoiceSerializer(DefaultSerializer):
    """What a job dropdown needs to name a job.

    The job counterpart of ``SourceImageCollectionNestedSerializer``, which serves the capture
    set choices: no counts or nested objects, so the choices query stays cheap.
    """

    def get_permissions(self, instance, instance_data):
        # A picker needs no per-job permissions, and resolving them costs several queries per row.
        instance_data["user_permissions"] = []
        return instance_data

    class Meta:
        model = Job
        fields = ["id", "name", "details", "job_type_key", "created_at"]


class MLJobTasksRequestSerializer(serializers.Serializer):
    """POST /jobs/{id}/tasks/ — request body sent by a processing service to fetch work.

    The processing service polls this endpoint to get tasks (images) to process.
    Each task is a PipelineProcessingTask with an image URL and a NATS reply subject.
    """

    batch_size = serializers.IntegerField(min_value=1, required=True)
    client_info = SchemaField(schema=ProcessingServiceClientInfo, required=False, default=None)


class MLJobTasksResponseSerializer(serializers.Serializer):
    """POST /jobs/{id}/tasks/ — response body returned to the processing service.

    Contains a list of tasks (PipelineProcessingTask dicts) for the worker to process.
    Each task includes an image URL, task ID, and reply_subject for result correlation.
    Returns an empty list when no tasks are available or the job is not active.
    """

    tasks = SchemaField(schema=list[PipelineProcessingTask], default=[])


class MLJobResultsRequestSerializer(serializers.Serializer):
    """POST /jobs/{id}/result/ — request body sent by a processing service to deliver results.

    "Request" here refers to the HTTP request to Antenna, not a request for work.
    The processing service has finished processing tasks and is posting its results
    (successes or errors) back. Each PipelineTaskResult contains a reply_subject
    (correlating back to the original task) and a result payload that is either a
    PipelineResultsResponse (success) or PipelineResultsError (failure).
    """

    results = SchemaField(schema=list[PipelineTaskResult])
    client_info = SchemaField(schema=ProcessingServiceClientInfo, required=False, default=None)


class TrainingResultRequestSerializer(serializers.Serializer):
    """POST /jobs/{id}/training-result/ — the body a processing service posts when a run finishes.

    The counterpart of MLJobResultsRequestSerializer for a retraining job: one result for
    one job, rather than a list of per-item results.

    ``result`` is validated, since it is what the new algorithm version is built from.
    ``dataset`` is the metadata the service echoes back from the training set file and is
    taken as it comes: a service that echoes an older shape should still have its result
    recorded, and the cost is a version that cannot say which occurrence set it learned
    from. It is parsed, leniently, where it is read.
    """

    result = SchemaField(schema=TrainingResult)
    dataset = serializers.JSONField(required=False, allow_null=True, default=None)
    dataset_url = serializers.CharField(required=False, allow_null=True, default=None)
    job_id = serializers.IntegerField(required=False, allow_null=True, default=None)
    algorithm_key = serializers.CharField(required=False, allow_null=True, default=None)


class TrainingResultResponseSerializer(serializers.Serializer):
    """POST /jobs/{id}/training-result/ — acknowledgment returned to the processing service."""

    status = serializers.CharField()
    job_id = serializers.IntegerField()
    algorithm = serializers.CharField(allow_null=True, help_text="Key of the version registered, if one was.")


class TrainingProgressRequestSerializer(serializers.Serializer):
    """POST /jobs/{id}/training-progress/ — how far through its epochs a run has got."""

    epoch = serializers.IntegerField(min_value=0)
    total_epochs = serializers.IntegerField(required=False, allow_null=True, default=None, min_value=1)


class MLJobResultsResponseSerializer(serializers.Serializer):
    """POST /jobs/{id}/result/ — acknowledgment returned to the processing service.

    Confirms receipt and indicates how many results were queued for background
    processing via Celery. Individual task entries include their Celery task_id
    for traceability.
    """

    status = serializers.CharField()
    job_id = serializers.IntegerField()
    results_queued = serializers.IntegerField()
    tasks = SchemaField(schema=list[QueuedTaskAcknowledgment], default=[])
