from rest_framework.decorators import action
from rest_framework.response import Response

from ami.main.api.views import DefaultViewSet

from .models import Job
from .serializers import JobListSerializer, JobSerializer


class JobViewSet(DefaultViewSet):
    """
    API endpoint that allows jobs to be viewed or edited.
    """

    queryset = Job.objects.all()
    serializer_class = JobSerializer
    filterset_fields = [
        "status",
        "project",
        "deployment",
        "source_image_collection",
        # "source_image_single", # This is too slow for the DRF browsable API
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
