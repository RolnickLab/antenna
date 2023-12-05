import logging

from rest_framework.decorators import action
from rest_framework.response import Response

from ami.main.api.views import DefaultViewSet
from ami.utils.fields import url_boolean_param

from .models import Job
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
        # job.run()
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

        job: Job = serializer.save()  # type: ignore
        if url_boolean_param(self.request, "start_now", default=False):
            # job.run()
            job.enqueue()
