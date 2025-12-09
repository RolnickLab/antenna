import logging

from django.db.models import Prefetch
from django.db.models.query import QuerySet
from django.utils.text import slugify
from drf_spectacular.utils import extend_schema
from rest_framework import exceptions as api_exceptions
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response

from ami.base.views import ProjectMixin
from ami.main.api.schemas import project_id_doc_param
from ami.main.api.views import DefaultViewSet
from ami.main.models import SourceImage

from .models.algorithm import Algorithm, AlgorithmCategoryMap
from .models.pipeline import Pipeline
from .models.processing_service import ProcessingService
from .models.project_pipeline_config import ProjectPipelineConfig
from .serializers import (
    AlgorithmCategoryMapSerializer,
    AlgorithmSerializer,
    PipelineSerializer,
    ProcessingServiceSerializer,
)

logger = logging.getLogger(__name__)


class AlgorithmViewSet(DefaultViewSet, ProjectMixin):
    """
    API endpoint that allows algorithm (ML models) to be viewed or edited.
    """

    queryset = Algorithm.objects.all()
    serializer_class = AlgorithmSerializer
    filterset_fields = ["name", "version"]
    ordering_fields = [
        "id",
        "created_at",
        "updated_at",
        "name",
        "task_type",
        "category_count",
        "description",
        "version",
    ]
    search_fields = ["name"]

    def get_queryset(self) -> QuerySet["Algorithm"]:
        qs: QuerySet["Algorithm"] = super().get_queryset()
        qs = qs.with_category_count()  # type: ignore[union-attr] # Custom queryset method
        return qs


class AlgorithmCategoryMapViewSet(DefaultViewSet):
    """
    API endpoint that allows algorithm category maps to be viewed or edited.
    """

    queryset = AlgorithmCategoryMap.objects.all()
    serializer_class = AlgorithmCategoryMapSerializer
    filterset_fields = ["algorithms"]
    ordering_fields = [
        "algorithms",
        "created_at",
        "updated_at",
        "version",
    ]


class PipelineViewSet(DefaultViewSet, ProjectMixin):
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
        qs: QuerySet = super().get_queryset()
        project = self.get_active_project()
        if project:
            qs = qs.filter(projects=project).prefetch_related(
                Prefetch(
                    "processing_services",
                    queryset=ProcessingService.objects.filter(projects=project.pk),
                )
            )
            qs = qs.prefetch_related(
                Prefetch(
                    "project_pipeline_configs",
                    queryset=ProjectPipelineConfig.objects.filter(pipeline__in=qs, project=project.id),
                )
            )

            qs = qs.filter(projects=project.id, project_pipeline_configs__enabled=True)

        return qs

    @extend_schema(parameters=[project_id_doc_param])
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    # Don't enable projects filter until we can use the current users
    # membership to filter the projects.
    # filterset_fields = ["projects"]

    @action(detail=True, methods=["post"])
    def test_process(self, request: Request, pk=None) -> Response:
        """
        Process images using the pipeline.
        """
        pipeline = Pipeline.objects.get(pk=pk)
        random_image = (
            SourceImage.objects.all().order_by("?").first()
        )  # TODO: Filter images by projects user has access to
        if not random_image:
            return Response({"error": "No image found to process."}, status=status.HTTP_404_NOT_FOUND)

        project = pipeline.projects.first()
        if not project:
            raise api_exceptions.ValidationError("Pipeline has no project associated with it.")
        results = pipeline.process_images(
            images=[random_image],
            project_id=project.pk,
            job_id=None,
            reprocess_all_images=project.feature_flags.reprocess_all_images,
        )
        return Response(results.dict())


class ProcessingServiceViewSet(DefaultViewSet, ProjectMixin):
    """
    API endpoint that allows processing services to be viewed or edited.
    """

    queryset = ProcessingService.objects.all()
    serializer_class = ProcessingServiceSerializer
    filterset_fields = ["projects"]
    ordering_fields = ["id", "created_at", "updated_at"]

    def get_queryset(self) -> QuerySet:
        qs: QuerySet = super().get_queryset()
        project = self.get_active_project()
        if project:
            qs = qs.filter(projects=project)
        return qs

    @extend_schema(parameters=[project_id_doc_param])
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        data = request.data.copy()
        data["slug"] = slugify(data["name"])
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        # immediately get status after creating a processing service
        instance: ProcessingService | None = serializer.instance
        assert instance is not None
        status_response = instance.get_status()
        return Response(
            {"instance": serializer.data, "status": status_response.dict()}, status=status.HTTP_201_CREATED
        )

    @action(detail=True, methods=["get"])
    def status(self, request: Request, pk=None) -> Response:
        """
        Test the connection to the processing service.
        """
        processing_service = ProcessingService.objects.get(pk=pk)
        response = processing_service.get_status()
        return Response(response.dict())

    @action(detail=True, methods=["post"])
    def register_pipelines(self, request: Request, pk=None) -> Response:
        processing_service = ProcessingService.objects.get(pk=pk)
        response = processing_service.create_pipelines()
        processing_service.save()
        return Response(response.dict())
