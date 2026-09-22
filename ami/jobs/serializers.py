import pydantic
from django_pydantic_field.rest_framework import SchemaField
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from ami.base.permissions import TRACKING_NOT_ENABLED_MESSAGE
from ami.exports.models import DataExport
from ami.main.api.serializers import (
    DefaultSerializer,
    DeploymentNestedSerializer,
    SourceImageCollectionNestedSerializer,
    SourceImageNestedSerializer,
)
from ami.main.models import Deployment, Event, Project, SourceImage, SourceImageCollection
from ami.ml.models import Pipeline
from ami.ml.post_processing.registry import get_postprocessing_task
from ami.ml.post_processing.tracking_task import TrackingConfig, TrackingTask
from ami.ml.schemas import PipelineProcessingTask, PipelineTaskResult, ProcessingServiceClientInfo
from ami.ml.serializers import PipelineNestedSerializer

from .models import (
    JOB_LOGS_DEFAULT_LIMIT,
    Job,
    JobProgress,
    MLJob,
    PostProcessingJob,
    _legacy_logs_shape,
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


# Post-processing tasks a project member may start through the jobs API. The others
# are staff tools started from the Django admin, and their scopes are not checked
# against the job's project here.
API_POST_PROCESSING_TASKS = {TrackingTask.key}


def _pydantic_messages(exc: pydantic.ValidationError) -> list[str]:
    messages = []
    for err in exc.errors():
        field = ".".join(str(part) for part in err.get("loc", ()) if part != "__root__")
        messages.append(f"{field}: {err['msg']}" if field else err["msg"])
    return messages


def validate_post_processing_params(project: Project | None, params) -> dict:
    """Check a post-processing job's ``{"task": ..., "config": {...}}`` before it is saved.

    Returns the params with the config normalized by the task's schema, so the stored
    job carries every default the worker will run with. Raises a 400 otherwise.
    """
    if not isinstance(params, dict) or set(params) - {"task", "config"}:
        raise serializers.ValidationError(
            {"params": 'Post-processing jobs take params of the form {"task": <key>, "config": {...}}.'}
        )
    task_key = params.get("task")
    task_cls = get_postprocessing_task(task_key) if isinstance(task_key, str) else None
    if task_cls is None:
        raise serializers.ValidationError({"params": {"task": f"Unknown post-processing task {task_key!r}."}})
    if task_key not in API_POST_PROCESSING_TASKS:
        raise serializers.ValidationError(
            {"params": {"task": f"The {task_cls.name} task cannot be started through the API."}}
        )
    if task_cls is TrackingTask and not (project and project.feature_flags.tracking):
        raise serializers.ValidationError({"project_id": TRACKING_NOT_ENABLED_MESSAGE})

    config = params.get("config") or {}
    if not isinstance(config, dict):
        raise serializers.ValidationError({"params": {"config": "Must be an object."}})
    try:
        model = task_cls.config_schema(**config)
    except pydantic.ValidationError as exc:
        raise serializers.ValidationError({"params": {"config": _pydantic_messages(exc)}})

    if isinstance(model, TrackingConfig):
        if model.event_ids:
            found = set(Event.objects.filter(pk__in=model.event_ids, project=project).values_list("pk", flat=True))
            missing = sorted(set(model.event_ids) - found)
            if missing:
                raise serializers.ValidationError(
                    {"params": {"config": [f"event_ids: Session(s) {missing} were not found in this project."]}}
                )
        if model.source_image_collection_id is not None and not (
            SourceImageCollection.objects.filter(pk=model.source_image_collection_id, project=project).exists()
        ):
            raise serializers.ValidationError(
                {
                    "params": {
                        "config": [
                            f"source_image_collection_id: Capture set {model.source_image_collection_id} "
                            "was not found in this project."
                        ]
                    }
                }
            )
    return {"task": task_key, "config": model.dict()}


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
    # Read by post-processing jobs only: {"task": <registered task key>, "config": {...}}.
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

    def validate(self, attrs: dict) -> dict:
        attrs = super().validate(attrs)
        if attrs.get("job_type_key") == PostProcessingJob.key:
            project = attrs.get("project") or getattr(self.instance, "project", None)
            attrs["params"] = validate_post_processing_params(project, attrs.get("params"))
        else:
            # Other job types do not read params, so none are stored for them.
            attrs.pop("params", None)
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
