import logging

from django.db import transaction
from django.db.models import Prefetch
from django.db.models.query import QuerySet
from django.utils.text import slugify
from drf_spectacular.utils import extend_schema
from rest_framework import exceptions as api_exceptions
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from ami.base.pagination import TrainingDataPagination
from ami.base.permissions import ProjectPipelineConfigPermission
from ami.base.views import ProjectMixin
from ami.main.api.schemas import project_id_doc_param
from ami.main.api.views import DefaultViewSet
from ami.main.models import Project, SourceImage
from ami.ml import training_data
from ami.ml.schemas import PipelineRegistrationResponse

from .models.algorithm import Algorithm, AlgorithmCategoryMap
from .models.embedding import EMBEDDING_DIMENSIONS, DetectionEmbedding
from .models.pipeline import Pipeline
from .models.processing_service import ProcessingService
from .models.project_pipeline_config import ProjectPipelineConfig
from .serializers import (
    AlgorithmCategoryMapSerializer,
    AlgorithmSerializer,
    PipelineRegistrationSerializer,
    PipelineSerializer,
    ProcessingServiceSerializer,
    TrainingDataRowSerializer,
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
        # Only scope the list by project. Detail stays unscoped so links from historical
        # classifications whose pipeline is no longer enabled still resolve.
        if getattr(self, "action", None) == "list":
            project = self.get_active_project()
            if project:
                # The project-scoped list shows the algorithms available to the project — those
                # on its enabled pipelines — so a freshly configured project sees what it can
                # run before anything has run. The algorithms that actually produced results
                # (including superseded versions) are served by /occurrences/algorithms/.
                qs = qs.filter(
                    pipelines__project_pipeline_configs__project=project,
                    pipelines__project_pipeline_configs__enabled=True,
                ).distinct()
        return qs

    @extend_schema(parameters=[project_id_doc_param])
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)


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
    require_project = True

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

    def perform_create(self, serializer):
        """
        Create a ProcessingService and automatically assign it to the active project.

        Users cannot manually assign processing services to projects for security reasons.
        A processing service is always created in the context of the active project.

        @TODO Do we need a permission check here to ensure the user can add processing services to the project?
        """
        instance = serializer.save()
        project = self.get_active_project()
        if project:
            instance.projects.add(project)

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


class ProjectPipelineViewSet(ProjectMixin, mixins.ListModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet):
    """Pipelines for a specific project. GET lists, POST registers."""

    queryset = Pipeline.objects.none()
    serializer_class = PipelineSerializer
    permission_classes = [ProjectPipelineConfigPermission]
    require_project = True

    def get_queryset(self) -> QuerySet:
        project = self.get_active_project()
        return (
            Pipeline.objects.filter(projects=project, project_pipeline_configs__enabled=True)
            .prefetch_related(
                "algorithms",
                Prefetch(
                    "processing_services",
                    queryset=ProcessingService.objects.filter(projects=project),
                ),
                Prefetch(
                    "project_pipeline_configs",
                    queryset=ProjectPipelineConfig.objects.filter(project=project),
                ),
            )
            .distinct()
        )

    def get_serializer_class(self):
        if self.action == "create":
            return PipelineRegistrationSerializer
        return PipelineSerializer

    @extend_schema(
        operation_id="projects_pipelines_list",
        summary="List pipelines for a project",
        responses={200: PipelineSerializer(many=True)},
        tags=["projects"],
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        operation_id="projects_pipelines_create",
        summary="Register pipelines for a project",
        description=(
            "Receive pipeline registrations for a project. This endpoint is called by the "
            "V2 ML processing services to register available pipelines for a project."
        ),
        request=PipelineRegistrationSerializer,
        responses={201: PipelineRegistrationResponse},
        tags=["projects"],
    )
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        project = self.get_active_project()

        with transaction.atomic():
            processing_service, _ = ProcessingService.objects.get_or_create(
                name=serializer.validated_data["processing_service_name"],
                defaults={"endpoint_url": None},
            )
            processing_service.projects.add(project)

            response = processing_service.create_pipelines(
                pipeline_configs=serializer.validated_data["pipelines"],
                projects=Project.objects.filter(pk=project.pk),
            )

        # Record that we heard from this async processing service
        processing_service.mark_seen(live=True)

        return Response(response.dict(), status=status.HTTP_201_CREATED)


class TrainingDataViewSet(ProjectMixin, mixins.ListModelMixin, viewsets.GenericViewSet):
    """
    Verified detections and their embeddings, for retraining a classifier head.

    A head is trained on embeddings, not pixels, and the backbone that produced them is
    frozen. So a trainer can pull this and fit a new head without touching the images.

    Requires `project_id` and `algorithm` (an algorithm key). Constraining to one
    algorithm is not optional: vectors from different backbones are in different spaces.

    GET /api/v2/ml/training-data/?project_id=3&algorithm=<key>
    GET /api/v2/ml/training-data/summary/?project_id=3&algorithm=<key>
    """

    queryset = DetectionEmbedding.objects.none()
    serializer_class = TrainingDataRowSerializer
    require_project = True
    permission_classes = [IsAuthenticated]
    filter_backends: list = []
    pagination_class = TrainingDataPagination

    def _get_algorithm(self) -> Algorithm:
        key = self.request.query_params.get("algorithm")
        if not key:
            raise api_exceptions.ValidationError(
                {"algorithm": "Required. The algorithm key whose embeddings to train on."}
            )
        algorithm = Algorithm.objects.filter(key=key).first()
        if not algorithm:
            raise api_exceptions.NotFound(f"No algorithm with key '{key}'.")
        return algorithm

    def _get_split_settings(self) -> tuple[str, float]:
        params = self.request.query_params
        salt = params.get("split_salt", training_data.DEFAULT_SPLIT_SALT)
        raw = params.get("test_fraction", training_data.DEFAULT_TEST_FRACTION)
        try:
            fraction = float(raw)
        except (TypeError, ValueError):
            raise api_exceptions.ValidationError({"test_fraction": "Must be a number between 0 and 1."})
        if not 0 <= fraction < 1:
            raise api_exceptions.ValidationError({"test_fraction": "Must be between 0 and 1."})
        return salt, fraction

    def get_queryset(self) -> QuerySet[DetectionEmbedding]:
        project = self.get_active_project()
        assert project  # require_project=True
        self.check_object_permissions(self.request, project)
        qs = training_data.verified_training_rows(project, self._get_algorithm())

        split = self.request.query_params.get("split")
        if split and split not in ("train", "test"):
            raise api_exceptions.ValidationError({"split": "Must be 'train' or 'test'."})
        self._split_filter = split
        return qs

    def get_serializer_context(self):
        context = super().get_serializer_context()
        salt, fraction = self._get_split_settings()
        context["split_salt"] = salt
        context["test_fraction"] = fraction
        context["include_features"] = self.request.query_params.get("include_features", "true").lower() != "false"
        return context

    @extend_schema(parameters=[project_id_doc_param])
    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        split = getattr(self, "_split_filter", None)
        if split:
            # Filtering by split in Python rather than SQL: the assignment is a hash of the
            # occurrence id, which Postgres cannot compute. Callers that need whole splits
            # should page through everything and group client-side.
            results = [row for row in response.data["results"] if row["split"] == split]
            response.data["results"] = results
        return response

    @extend_schema(parameters=[project_id_doc_param])
    @action(detail=False, methods=["get"])
    def summary(self, request, *args, **kwargs):
        """Counts only. Cheap enough to poll before deciding whether a retrain is worth it."""
        project = self.get_active_project()
        assert project
        self.check_object_permissions(request, project)
        algorithm = self._get_algorithm()
        salt, fraction = self._get_split_settings()

        counts = training_data.label_counts(project, algorithm)
        rows = training_data.verified_training_rows(project, algorithm)
        splits = {"train": 0, "test": 0}
        for occurrence_id in rows.values_list("detection__occurrence_id", flat=True):
            splits[training_data.split_for(occurrence_id, salt, fraction)] += 1

        return Response(
            {
                "project": {"id": project.pk, "name": project.name},
                "algorithm": {"key": algorithm.key, "name": algorithm.name, "version": algorithm.version},
                "dimensions": EMBEDDING_DIMENSIONS,
                "rows": sum(counts.values()),
                "classes": len(counts),
                "counts": dict(sorted(counts.items(), key=lambda kv: -kv[1])),
                "train": splits["train"],
                "test": splits["test"],
                "verified_detections_without_embedding": training_data.count_missing_embeddings(project, algorithm),
                "settings": {
                    "split_salt": salt,
                    "test_fraction": fraction,
                    "split_grouped_by": "occurrence",
                },
            }
        )
