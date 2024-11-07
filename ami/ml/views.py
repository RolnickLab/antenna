import datetime
import logging
from urllib.parse import urljoin

import requests
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response

from ami.main.api.views import DefaultViewSet

from .models.algorithm import Algorithm
from .models.backend import Backend
from .models.pipeline import Pipeline
from .schemas import BackendResponse
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


class BackendViewSet(DefaultViewSet):
    """
    API endpoint that allows ML processing backends to be viewed or edited.
    """

    queryset = Backend.objects.all()
    serializer_class = BackendSerializer
    filterset_fields = ["projects"]
    ordering_fields = ["id"]

    @action(detail=True, methods=["get"])
    def status(self, request: Request, pk=None) -> Response:
        """
        Test the connection to the processing backend.
        """
        backend = Backend.objects.get(pk=pk)
        endpoint_url = backend.endpoint_url
        info_url = urljoin(endpoint_url, "info")

        resp = requests.get(info_url)
        if not resp.ok:
            try:
                msg = resp.json()["detail"]
            except Exception:
                msg = resp.content

            logger.error(msg)

        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        pipeline_configs = resp.json() if resp.ok else []
        error = f"{resp.status_code} - {msg}" if not resp.ok else None

        server_live = requests.get(urljoin(endpoint_url, "livez")).json().get("status")
        pipelines_online = requests.get(urljoin(endpoint_url, "readyz")).json().get("status")

        response = BackendResponse(
            timestamp=timestamp,
            success=resp.ok,
            server_online=server_live,
            pipelines_online=pipelines_online,
            pipeline_configs=pipeline_configs,
            error=error,
        )

        return Response(response.dict())
