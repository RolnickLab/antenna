import logging

import pydantic
from django.db.models import Q
from django.db.models.query import QuerySet
from django.forms import IntegerField
from django.utils import timezone
from django_filters import rest_framework as filters
from drf_spectacular.utils import extend_schema
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.filters import BaseFilterBackend
from rest_framework.response import Response

from ami.base.permissions import ObjectPermission
from ami.base.views import ProjectMixin
from ami.jobs.schemas import batch_param, ids_only_param, incomplete_only_param
from ami.main.api.schemas import project_id_doc_param

# from ami.jobs.tasks import process_pipeline_result  # TODO: Uncomment when available in main
from ami.main.api.views import DefaultViewSet
from ami.ml.schemas import PipelineProcessingTask, PipelineTaskResult
from ami.utils.fields import url_boolean_param

from .models import Job, JobState
from .serializers import JobListSerializer, JobSerializer, MinimalJobSerializer

logger = logging.getLogger(__name__)


class JobFilterSet(filters.FilterSet):
    """Custom filterset to enable pipeline name filtering."""

    pipeline__slug = filters.CharFilter(field_name="pipeline__slug", lookup_expr="exact")

    class Meta:
        model = Job
        fields = [
            "status",
            "project",
            "deployment",
            "source_image_collection",
            "source_image_single",
            "pipeline",
            "job_type_key",
        ]


class IncompleteJobFilter(BaseFilterBackend):
    """Filter backend to filter jobs by incomplete status based on results stage."""

    def filter_queryset(self, request, queryset, view):
        # Check if incomplete_only parameter is set
        incomplete_only = url_boolean_param(request, "incomplete_only", default=False)
        # Filter to incomplete jobs if requested (checks "results" stage status)
        if incomplete_only:
            # Create filters for each final state to exclude
            final_states = JobState.final_states()
            exclude_conditions = Q()

            # Exclude jobs where the "results" stage has a final state status
            for state in final_states:
                # JSON path query to check if results stage status is in final states
                # @TODO move to a QuerySet method on Job model if/when this needs to be reused elsewhere
                exclude_conditions |= Q(progress__stages__contains=[{"key": "results", "status": state}])

            queryset = queryset.exclude(exclude_conditions)
        return queryset


class JobViewSet(DefaultViewSet, ProjectMixin):
    """
    API endpoint that allows jobs to be viewed or edited.

    Pass the ``start_now`` url parameter to the ``POST`` method to enqueue the job immediately.

    Use the `delay` field to create a test job with fake duration of work (in seconds).

    ## Actions

    ### `/jobs/{id}/run/` (`POST`)

    Run a job (add it to the queue).

    ### `/jobs/{id}/cancel/` (`POST`)

    Cancel a job (terminate the background task)
    """

    queryset = Job.objects.select_related(
        "deployment",
        "pipeline",
        "source_image_collection",
        "source_image_single",
    )
    serializer_class = JobSerializer
    filterset_class = JobFilterSet
    filter_backends = [*DefaultViewSet.filter_backends, IncompleteJobFilter]
    search_fields = ["name", "pipeline__name"]
    ordering_fields = [
        "name",
        "created_at",
        "updated_at",
        "status",
        "started_at",
        "finished_at",
        "project",
        "deployment",
        "source_image_collection",
        "pipeline",
    ]

    permission_classes = [ObjectPermission]

    def get_serializer_class(self):
        """
        Return different serializers for list and detail views.
        """
        if self.action == "list":
            # Use MinimalJobSerializer when ids_only parameter is set
            if url_boolean_param(self.request, "ids_only", default=False):
                return MinimalJobSerializer
            return JobListSerializer
        else:
            return JobSerializer

    @action(detail=True, methods=["post"], name="run")
    def run(self, request, pk=None):
        """
        Run a job (add it to the queue).
        """
        job: Job = self.get_object()

        no_async = url_boolean_param(request, "no_async", default=False)
        if no_async:
            job.run()
        else:
            job.enqueue()
        job.refresh_from_db()
        return Response(self.get_serializer(job).data)

    @action(detail=True, methods=["post"], name="retry")
    def retry(self, request, pk=None):
        """
        Re-run a job
        """
        job: Job = self.get_object()
        no_async = url_boolean_param(request, "no_async", default=False)
        if no_async:
            job.retry(async_task=False)
        else:
            job.retry(async_task=True)
        job.refresh_from_db()
        return Response(self.get_serializer(job).data)

    @action(detail=True, methods=["post"], name="cancel")
    def cancel(self, request, pk=None):
        """
        Cancel a job (terminate the background task)
        """
        job: Job = self.get_object()
        job.cancel()
        job.refresh_from_db()
        return Response(self.get_serializer(job).data)

    def perform_create(self, serializer):
        """
        If the ``start_now`` parameter is passed, enqueue the job immediately.
        """
        # All jobs created from the Jobs UI are ML jobs.
        # @TODO Remove this when the UI is updated pass a job type
        # Get an instance for the model without saving
        obj = serializer.Meta.model(**serializer.validated_data)
        # Check permissions before saving
        self.check_object_permissions(self.request, obj)

        job: Job = serializer.save()  # type: ignore
        if url_boolean_param(self.request, "start_now", default=False):
            if job.check_custom_permission(self.request.user, "run"):
                # If the user has permission, enqueue the job
                job.enqueue()
            else:
                # If the user does not have permission, raise an error
                raise PermissionDenied("You do not have permission to run this job.")

    def get_queryset(self) -> QuerySet:
        jobs = super().get_queryset()
        project = self.get_active_project()
        if project:
            jobs = jobs.filter(project=project)
        cutoff_hours = IntegerField(required=False, min_value=0).clean(
            self.request.query_params.get("cutoff_hours", Job.FAILED_CUTOFF_HOURS)
        )
        # Filter out completed jobs that have not been updated in the last X hours
        cutoff_datetime = timezone.now() - timezone.timedelta(hours=cutoff_hours)
        return jobs.exclude(
            status=JobState.failed_states(),
            updated_at__lt=cutoff_datetime,
        )

    @extend_schema(
        parameters=[
            project_id_doc_param,
            ids_only_param,
            incomplete_only_param,
        ]
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        parameters=[batch_param],
        responses={200: dict},
    )
    @action(detail=True, methods=["get"], name="tasks")
    def tasks(self, request, pk=None):
        """
        Get tasks from the job queue.

        Returns task data with reply_subject for acknowledgment. External workers should:
        1. Call this endpoint to get tasks
        2. Process the tasks
        3. POST to /jobs/{id}/result/ with the reply_subject to acknowledge
        """
        job: Job = self.get_object()
        try:
            batch = IntegerField(required=True, min_value=1).clean(request.query_params.get("batch"))
        except Exception as e:
            raise ValidationError({"batch": str(e)}) from e

        # Validate that the job has a pipeline
        if not job.pipeline:
            raise ValidationError("This job does not have a pipeline configured")

        # TODO: Implement task queue integration
        logger.warning(f"Task queue endpoint called for job {job.pk} but the implementation is not yet available.")

        dummy_task = PipelineProcessingTask(
            id="1",
            image_id="1",
            image_url="http://example.com/image1",
            queue_timestamp=timezone.now().isoformat(),
        )

        # @TODO when this gets fully implemented, use a Serializer or Pydantic schema
        # for the full repsponse structure.
        return Response({"tasks": [task.dict() for task in [dummy_task] * batch]})

    @action(detail=True, methods=["post"], name="result")
    def result(self, request, pk=None):
        """
        Submit pipeline results for asynchronous processing.

        This endpoint accepts a list of pipeline results and queues them for
        background processing. Each result will be validated and saved.

        The request body should be a list of results: list[PipelineTaskResult]
        """

        job = self.get_object()
        job_id = job.pk

        # Validate request data is a list
        if isinstance(request.data, list):
            results = request.data
        else:
            results = [request.data]

        try:
            queued_tasks = []
            for item in results:
                task_result = PipelineTaskResult(**item)
                # Stub: Log that we received the result but don't process it yet
                logger.warning(
                    f"Result endpoint called for job {job_id} (reply_subject: {task_result.reply_subject}) "
                    "but result processing not yet available."
                )

                # TODO: Implement result storage and processing
                queued_tasks.append(
                    {
                        "reply_subject": task_result.reply_subject,
                        "status": "pending_implementation",
                        "message": "Result processing not yet implemented.",
                    }
                )
        except pydantic.ValidationError as e:
            raise ValidationError(f"Invalid result data: {e}") from e

        return Response(
            {
                "status": "received",
                "job_id": job_id,
                "results_received": len(queued_tasks),
                "tasks": queued_tasks,
                "message": "Result processing not yet implemented.",
            }
        )
