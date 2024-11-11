import logging

from django.db.models.query import QuerySet
from django.forms import IntegerField
from django.utils import timezone
from rest_framework.decorators import action
from rest_framework.response import Response

from ami.main.api.views import DefaultViewSet
from ami.utils.fields import url_boolean_param

from .models import Job, JobState, MLJob
from .serializers import JobListSerializer, JobSerializer

logger = logging.getLogger(__name__)


class JobViewSet(DefaultViewSet):
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
        "project",
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
        "pipeline",
    ]
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
        if not serializer.validated_data.get("job_type_key"):
            serializer.validated_data["job_type_key"] = MLJob.key

        job: Job = serializer.save()  # type: ignore
        if url_boolean_param(self.request, "start_now", default=False):
            # job.run()
            job.enqueue()

    def get_queryset(self) -> QuerySet:
        jobs = super().get_queryset()

        cutoff_hours = IntegerField(required=False, min_value=0).clean(
            self.request.query_params.get("cutoff_hours", Job.FAILED_CUTOFF_HOURS)
        )
        # Filter out completed jobs that have not been updated in the last X hours
        cutoff_datetime = timezone.now() - timezone.timedelta(hours=cutoff_hours)
        return jobs.exclude(
            status=JobState.failed_states(),
            updated_at__lt=cutoff_datetime,
        )
