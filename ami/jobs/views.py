from rest_framework.decorators import action
from rest_framework.response import Response

from ami.main.api.views import DefaultViewSet
from ami.utils.fields import url_boolean_param

from .models import Job
from .serializers import JobListSerializer, JobSerializer


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

    queryset = Job.objects.all()
    serializer_class = JobSerializer
    filterset_fields = [
        "status",
        "project",
        "deployment",
    ]
    ordering_fields = [
        "created_at",
        "updated_at",
        "status",
        "started_at",
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
        job = self.get_object()
        job.enqueue()
        job.refresh_from_db()
        return Response(self.get_serializer(job).data)

    @action(detail=True, methods=["post"], name="cancel")
    def cancel(self, request, pk=None):
        """
        Cancel a job (terminate the background task)
        """
        job = self.get_object()
        job.cancel()
        job.refresh_from_db()
        return Response(self.get_serializer(job).data)

    def perform_create(self, serializer):
        """
        If the ``start_now`` parameter is passed, enqueue the job immediately.
        """
        job = serializer.save()
        if url_boolean_param(self.request, "start_now", default=False):
            job.enqueue()  # type: ignore
