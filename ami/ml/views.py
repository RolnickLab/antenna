import logging

from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response

from ami.main.api.views import DefaultViewSet
from ami.main.models import SourceImage

from .models.algorithm import Algorithm
from .models.backend import Backend
from .models.pipeline import Pipeline
from .serializers import AlgorithmSerializer, BackendSerializer, PipelineSerializer

logger = logging.getLogger(__name__)


class AlgorithmViewSet(DefaultViewSet):
    """
    API endpoint that allows algorithm (ML models) to be viewed or edited.
    """

    queryset = Algorithm.objects.all()
    serializer_class = AlgorithmSerializer
    filterset_fields = ["name", "version"]
    ordering_fields = [
        "created_at",
        "updated_at",
        "name",
        "version",
    ]
    search_fields = ["name"]


class PipelineViewSet(DefaultViewSet):
    """
    API endpoint that allows pipelines to be viewed or edited.
    """

    queryset = Pipeline.objects.prefetch_related("algorithms").all()
    serializer_class = PipelineSerializer
    ordering_fields = [
        "id",
        "name",
        "created_at",
        "updated_at",
    ]
    # Don't enable projects filter until we can use the current users
    # membership to filter the projects.
    # filterset_fields = ["projects"]

    @action(detail=True, methods=["post"])
    def test_process(self, request: Request, pk=None) -> Response:
        """
        Process images using the pipeline.
        """
        pipeline = Pipeline.objects.get(pk=pk)
        # @TODO: Create function to backend from the current project and most recently responded OK to a status check
        backend_id = pipeline.backends.first().pk
        random_image = (
            SourceImage.objects.all().order_by("?").first()
        )  # TODO: Filter images by projects user has access to
        results = pipeline.process_images(images=[random_image], backend_id=backend_id, job_id=None)
        # @TODO: Add error or info messages to the response if image already processed or no detections returned
        return Response(results.dict())


class BackendViewSet(DefaultViewSet):
    """
    API endpoint that allows ML processing backends to be viewed or edited.
    """

    queryset = Backend.objects.all()
    serializer_class = BackendSerializer
    filterset_fields = ["projects"]
    ordering_fields = ["id", "created_at", "updated_at"]

    @action(detail=True, methods=["get"])
    def status(self, request: Request, pk=None) -> Response:
        """
        Test the connection to the processing backend.
        """
        backend = Backend.objects.get(pk=pk)
        response = backend.get_status()
        return Response(response.dict())

    @action(detail=True, methods=["post"])
    def register_pipelines(self, request: Request, pk=None) -> Response:
        backend = Backend.objects.get(pk=pk)
        response = backend.create_pipelines()
        return Response(response.dict())
