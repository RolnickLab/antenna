import logging

from asgiref.sync import async_to_sync
from django.db.models.query import QuerySet
from django.forms import IntegerField
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from ami.base.permissions import ObjectPermission
from ami.base.views import ProjectMixin
from ami.jobs.tasks import process_pipeline_result
from ami.main.api.views import DefaultViewSet
from ami.utils.fields import url_boolean_param
from ami.utils.requests import project_id_doc_param

from .models import Job, JobState
from .serializers import JobListSerializer, JobSerializer

logger = logging.getLogger(__name__)


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
    filterset_fields = [
        "status",
        "project",
        "deployment",
        "source_image_collection",
        "source_image_single",
        "pipeline",
        "job_type_key",
    ]
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
            OpenApiParameter(
                name="pipeline",
                description="Filter jobs by pipeline ID",
                required=False,
                type=OpenApiTypes.INT,
            ),
            OpenApiParameter(
                name="ids_only",
                description="Return only job IDs instead of full job objects",
                required=False,
                type=OpenApiTypes.BOOL,
            ),
            OpenApiParameter(
                name="incomplete_only",
                description="Filter to only show incomplete jobs (excludes SUCCESS, FAILURE, REVOKED)",
                required=False,
                type=OpenApiTypes.BOOL,
            ),
        ]
    )
    def list(self, request, *args, **kwargs):
        # Check if ids_only parameter is set
        ids_only = request.query_params.get("ids_only", "false").lower() in ["true", "1", "yes"]

        # Check if incomplete_only parameter is set
        incomplete_only = request.query_params.get("incomplete_only", "false").lower() in ["true", "1", "yes"]

        # Get the base queryset
        queryset = self.filter_queryset(self.get_queryset())

        # Filter to incomplete jobs if requested (checks "results" stage status)
        if incomplete_only:
            from django.db.models import Q

            # Create filters for each final state to exclude
            final_states = JobState.final_states()
            exclude_conditions = Q()

            # Exclude jobs where the "results" stage has a final state status
            for state in final_states:
                # JSON path query to check if results stage status is in final states
                exclude_conditions |= Q(progress__stages__contains=[{"key": "results", "status": state}])

            queryset = queryset.exclude(exclude_conditions)

        if ids_only:
            # Return only IDs
            job_ids = list(queryset.values_list("id", flat=True))
            return Response({"job_ids": job_ids, "count": len(job_ids)})

        # Override the queryset for the list view
        self.queryset = queryset
        return super().list(request, *args, **kwargs)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="batch",
                description="Number of tasks to pull in the batch",
                required=False,
                type=OpenApiTypes.INT,
            ),
        ],
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

        This stateless approach allows workers to communicate over HTTP without
        maintaining persistent connections to the queue system.
        """
        job: Job = self.get_object()
        batch = IntegerField(required=False, min_value=1).clean(request.query_params.get("batch", 1))
        job_id = f"job{job.pk}"

        # Validate that the job has a pipeline
        if not job.pipeline:
            raise ValidationError("This job does not have a pipeline configured")

        # Get tasks from NATS JetStream
        from ami.utils.nats_queue import TaskQueueManager

        async def get_tasks():
            tasks = []
            async with TaskQueueManager() as manager:
                for i in range(batch):
                    task = await manager.reserve_job(job_id, timeout=0.1)
                    if task:
                        tasks.append(task)
            return tasks

        # Use async_to_sync to properly handle the async call
        tasks = async_to_sync(get_tasks)()

        return Response({"tasks": tasks})

    @action(detail=True, methods=["post"], name="result")
    def result(self, request, pk=None):
        """
        Submit pipeline results for asynchronous processing.

        This endpoint accepts a list of pipeline results and queues them for
        background processing. Each result will be validated, saved to the database,
        and acknowledged via NATS in a Celery task.

        The request body should be a list of results:
        [
            {
                "reply_subject": "string",  # Required: from the task response
                "result": {  # Required: PipelineResultsResponse (kept as JSON)
                    "pipeline": "string",
                    "algorithms": {},
                    "total_time": 0.0,
                    "source_images": [...],
                    "detections": [...],
                    "errors": null
                }
            },
            ...
        ]
        """

        job_id = pk if pk else self.kwargs.get("pk")
        if not job_id:
            raise ValidationError("Job ID is required")
        job_id = int(job_id)

        # Validate request data is a list
        if not isinstance(request.data, list):
            raise ValidationError("Request body must be a list of results")

        # Queue each result for background processing
        queued_tasks = []

        for idx, item in enumerate(request.data):
            reply_subject = item.get("reply_subject")
            result_data = item.get("result")

            if not reply_subject:
                raise ValidationError(f"Item {idx}: reply_subject is required")

            if not result_data:
                raise ValidationError(f"Item {idx}: result is required")

            try:
                # Queue the background task
                task = process_pipeline_result.delay(
                    job_id=job_id, result_data=result_data, reply_subject=reply_subject
                )

                queued_tasks.append(
                    {
                        "reply_subject": reply_subject,
                        "status": "queued",
                        "task_id": task.id,
                    }
                )

                logger.info(
                    f"Queued pipeline result processing for job {job_id}, "
                    f"task_id: {task.id}, reply_subject: {reply_subject}"
                )

            except Exception as e:
                logger.error(f"Failed to queue result {idx} for job {job_id}: {e}")
                queued_tasks.append(
                    {
                        "reply_subject": reply_subject,
                        "status": "error",
                        "error": str(e),
                    }
                )

        return Response(
            {
                "status": "accepted",
                "job_id": job_id,
                "results_queued": len([t for t in queued_tasks if t["status"] == "queued"]),
                "tasks": queued_tasks,
            }
        )
