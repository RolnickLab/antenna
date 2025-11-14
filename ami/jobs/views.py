import logging

from django.db.models.query import QuerySet
from django.forms import IntegerField
from django.utils import timezone
from django_filters import rest_framework as filters
from drf_spectacular.utils import extend_schema
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from ami.base.permissions import ObjectPermission
from ami.base.views import ProjectMixin

# from ami.jobs.tasks import process_pipeline_result  # TODO: Uncomment when available in main
from ami.main.api.views import DefaultViewSet
from ami.utils.fields import url_boolean_param
from ami.utils.requests import batch_param, ids_only_param, incomplete_only_param, project_id_doc_param

from .models import Job, JobState
from .serializers import JobListSerializer, JobSerializer

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
            "pipeline__slug",
            "job_type_key",
        ]


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
            ids_only_param,
            incomplete_only_param,
        ]
    )
    def list(self, request, *args, **kwargs):
        # Check if ids_only parameter is set
        ids_only = url_boolean_param(request, "ids_only", default=False)

        # Check if incomplete_only parameter is set
        incomplete_only = url_boolean_param(request, "incomplete_only", default=False)

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

        This stateless approach allows workers to communicate over HTTP without
        maintaining persistent connections to the queue system.

        NOTE: This endpoint requires NATS JetStream integration which is not yet
        available in main. Implementation coming from PR #987.
        """
        job: Job = self.get_object()
        batch = IntegerField(required=False, min_value=1).clean(request.query_params.get("batch", 1))

        # Validate that the job has a pipeline
        if not job.pipeline:
            raise ValidationError("This job does not have a pipeline configured")

        # TODO: Implement NATS JetStream task queue integration
        # This requires:
        # 1. TaskQueueManager from ami.ml.orchestration.nats_queue (PR #987)
        # 2. NATS server configuration
        # 3. Task enqueuing on job creation
        # 4. async_to_sync from asgiref.sync to handle async calls
        #
        # Example implementation (currently stubbed):
        # from asgiref.sync import async_to_sync
        # from ami.ml.orchestration.nats_queue import TaskQueueManager
        # async def get_tasks():
        #     tasks = []
        #     async with TaskQueueManager() as manager:
        #         for i in range(batch):
        #             task = await manager.reserve_task(f"job{job.pk}", timeout=0.1)
        #             if task:
        #                 tasks.append(task)
        #     return tasks
        # tasks = async_to_sync(get_tasks)()

        logger.warning(
            f"Task queue endpoint called for job {job.pk} but NATS integration not yet available. "
            "This endpoint will be functional once PR #987 is merged."
        )

        return Response(
            {
                "tasks": [],
                "message": "Task queue integration not yet available. Coming in PR #987.",
                "job_id": job.pk,
                "batch_requested": batch,
            }
        )

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

        NOTE: This endpoint requires the process_pipeline_result Celery task which is not yet
        available in main. Implementation coming from PR #987.
        """

        job = self.get_object()
        job_id = job.pk

        # Validate request data is a list
        if not isinstance(request.data, list):
            raise ValidationError("Request body must be a list of results")

        # TODO: Implement result processing with Celery task
        # This requires:
        # 1. process_pipeline_result task from ami.jobs.tasks (PR #987)
        # 2. NATS acknowledgment integration
        #
        # Example implementation (currently stubbed):
        # from ami.jobs.tasks import process_pipeline_result
        # for idx, item in enumerate(request.data):
        #     reply_subject = item.get("reply_subject")
        #     result_data = item.get("result")
        #     task = process_pipeline_result.delay(
        #         job_id=job_id, result_data=result_data, reply_subject=reply_subject
        #     )

        queued_tasks = []
        for idx, item in enumerate(request.data):
            reply_subject = item.get("reply_subject")
            result_data = item.get("result")

            if not reply_subject:
                raise ValidationError(f"Item {idx}: reply_subject is required")

            if not result_data:
                raise ValidationError(f"Item {idx}: result is required")

            # Stub: Log that we received the result but don't process it yet
            logger.warning(
                f"Result endpoint called for job {job_id} (reply_subject: {reply_subject}) "
                "but result processing not yet available. This will be functional once PR #987 is merged."
            )

            queued_tasks.append(
                {
                    "reply_subject": reply_subject,
                    "status": "pending_implementation",
                    "message": "Result processing will be available in PR #987",
                }
            )

        return Response(
            {
                "status": "received",
                "job_id": job_id,
                "results_received": len(queued_tasks),
                "tasks": queued_tasks,
                "message": "Result processing not yet implemented. Coming in PR #987.",
            }
        )
