from django.db.models.query import QuerySet
from drf_spectacular.utils import extend_schema

from ami.main.api.views import DefaultViewSet
from ami.utils.requests import get_active_project, project_id_doc_param

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

    def get_queryset(self) -> QuerySet:
        query_set: QuerySet = super().get_queryset()
        project = get_active_project(self.request)
        if project:
            query_set = query_set.filter(projects=project)
        return query_set

    @extend_schema(parameters=[project_id_doc_param])
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    # Don't enable projects filter until we can use the current users
    # membership to filter the projects.
    # filterset_fields = ["projects"]
