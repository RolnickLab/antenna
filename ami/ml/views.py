from django.db.models.query import QuerySet
from drf_spectacular.utils import OpenApiParameter, extend_schema

from ami.main.api.views import DefaultViewSet
from ami.main.models import Project

from .models.algorithm import Algorithm
from .models.pipeline import Pipeline
from .serializers import AlgorithmSerializer, PipelineSerializer


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

    def get_queryset(self) -> QuerySet:  # @TBD
        query_set: QuerySet = super().get_queryset()
        project_id = self.request.query_params.get("project_id")
        if project_id is not None:
            project = Project.objects.filter(id=project_id).first()
            if project:
                query_set = query_set.filter(projects=project)
        return query_set

    # @TBD
    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="project_id",
                description="Filter by project ID",
                required=False,
                type=int,
            )
        ]
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    # Don't enable projects filter until we can use the current users
    # membership to filter the projects.
    # filterset_fields = ["projects"]
