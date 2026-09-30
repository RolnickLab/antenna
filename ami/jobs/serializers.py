from django_pydantic_field.rest_framework import SchemaField
from drf_spectacular.utils import extend_schema_field
from guardian.shortcuts import get_perms
from rest_framework import exceptions, serializers

from ami.exports.models import DataExport
from ami.main.api.serializers import (
    DefaultSerializer,
    DeploymentNestedSerializer,
    SourceImageCollectionNestedSerializer,
    SourceImageNestedSerializer,
)
from ami.main.models import Deployment, Project, SourceImage, SourceImageCollection
from ami.ml.models import Pipeline
from ami.ml.schemas import PipelineProcessingTask, PipelineTaskResult, ProcessingServiceClientInfo
from ami.ml.serializers import PipelineNestedSerializer

from .descriptors import describe_docstring, normalize_config_schema
from .models import (
    JOB_LOGS_DEFAULT_LIMIT,
    VALID_JOB_TYPES,
    Job,
    JobProgress,
    JobType,
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


def describe_job_types(project: Project, user) -> list[dict]:
    """Describe every job type ``user`` may pick in the Create Job dialog for ``project``.

    ``allowed`` says whether the user may run a job of that type here; the dialog disables
    rather than hides a type the user may not run, so they can see it exists. Permissions are
    read once for the whole list.
    """
    perms = set(get_perms(user, project))
    described = []
    for job_type in VALID_JOB_TYPES:
        if not job_type.user_creatable:
            continue
        allowed = user.is_superuser or f"run_{job_type.key}_job" in perms
        variants = job_type.variants(user=user)
        for variant in variants:
            allowed_for_members = variant.pop("allowed_for_members")
            variant["allowed"] = allowed and (user.is_superuser or allowed_for_members)
        described.append(
            {
                "key": job_type.key,
                "name": job_type.name,
                "description": describe_docstring(job_type),
                "allowed": allowed,
                "scope": [field.as_dict() for field in job_type.scope_fields],
                "required_fields": list(job_type.required_fields),
                "required_params": list(job_type.required_params),
                "config_schema": (normalize_config_schema(job_type.config_schema) if job_type.config_schema else None),
                "variant_key": job_type.variant_key,
                "variants": variants,
            }
        )
    return described


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

    # A job's settings, checked by its job type when the job is created and fixed after that:
    # a later update cannot swap in settings that were never validated. See JobType.validate_params.
    params = serializers.JSONField(required=False, allow_null=True)

    class Meta(JobListSerializer.Meta):
        fields = JobListSerializer.Meta.fields + [
            "result",
            "params",
        ]

    def validate_job_type_key(self, value: str) -> str:
        job_type = get_job_type_by_key(value)
        if not job_type:
            known = sorted(t.key for t in VALID_JOB_TYPES if t.user_creatable)
            raise serializers.ValidationError(f"Unknown job type '{value}'. Known types: {known}")
        if self.instance is None and not job_type.user_creatable:
            raise serializers.ValidationError(
                f"{job_type.name} jobs are created by the platform, not through this API."
            )
        return value

    def validate(self, attrs: dict) -> dict:
        attrs = super().validate(attrs)
        if self.instance is not None:
            # Settings are fixed once the job exists.
            attrs.pop("params", None)
            return attrs

        job_type = get_job_type_by_key(attrs.get("job_type_key", MLJob.key))
        if job_type is None:  # validate_job_type_key refuses unknown keys; this guards the default
            raise serializers.ValidationError({"job_type_key": "Unknown job type."})
        project = attrs.get("project")
        self._check_scope_in_project(attrs, project)

        missing_fields = [name for name in job_type.required_fields if not attrs.get(name)]
        if missing_fields:
            raise serializers.ValidationError(
                {f"{name}_id": f"{job_type.name} jobs need a {name}." for name in missing_fields}
            )
        params = attrs.get("params") or {}
        missing_params = [name for name in job_type.required_params if not params.get(name)]
        if missing_params:
            raise serializers.ValidationError(
                {"params": f"{job_type.name} jobs need {', '.join(missing_params)} in their params."}
            )

        request = self.context.get("request")
        user = getattr(request, "user", None)
        attrs["params"] = job_type.validate_params(project, user, attrs.get("params"))
        if job_type.variant_key:
            self._check_may_run(job_type, project, attrs["params"], user)
        return attrs

    def _check_scope_in_project(self, attrs: dict, project: Project | None) -> None:
        errors = {}
        for field in ("deployment", "source_image_collection", "source_image_single"):
            obj = attrs.get(field)
            if obj is not None and obj.project_id != getattr(project, "pk", None):
                errors[f"{field}_id"] = "Not found in this project."
        if errors:
            raise serializers.ValidationError(errors)

    def _check_may_run(self, job_type: type[JobType], project: Project | None, params: dict, user) -> None:
        # Creating a job whose type runs registered methods (post-processing) takes the
        # permission to run it, so a role that cannot start one is refused before a job it
        # could never run is stored.
        if user is None:
            return
        job = Job(job_type_key=job_type.key, project=project, params=params)
        if not job.check_custom_permission(user, "run"):
            raise exceptions.PermissionDenied(
                f"You do not have permission to run {job_type.name} jobs in this project."
            )


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
