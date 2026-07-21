import logging

from django.db import transaction
from django.db.models import Prefetch
from django.db.models.query import QuerySet
from django.utils.text import slugify
from drf_spectacular.utils import extend_schema
from rest_framework import exceptions as api_exceptions
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response

from ami.base.permissions import ProjectPipelineConfigPermission
from ami.base.views import ProjectMixin
from ami.main.api.schemas import project_id_doc_param
from ami.main.api.views import DefaultViewSet
from ami.main.models import Classification, Project, SourceImage
from ami.ml.schemas import PipelineRegistrationResponse

from .models.algorithm import Algorithm, AlgorithmCategoryMap
from .models.pipeline import Pipeline
from .models.processing_service import ProcessingService
from .models.project_pipeline_config import ProjectPipelineConfig
from .serializers import (
    AlgorithmCategoryMapSerializer,
    AlgorithmSerializer,
    PipelineRegistrationSerializer,
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
        # Only scope the list by project. Detail stays unscoped so links from historical
        # classifications whose pipeline is no longer enabled still resolve.
        if getattr(self, "action", None) == "list":
            project = self.get_active_project()
            if project:
                # Algorithms reach the list two ways. An enabled pipeline configures most of
                # them, and that join alone covers detectors, which never author a
                # Classification and so cannot be found by their results at all.
                configured_for_project = Algorithm.objects.filter(
                    pipelines__project_pipeline_configs__project=project,
                    pipelines__project_pipeline_configs__enabled=True,
                ).values_list("pk", flat=True)

                # Post-processing algorithms (e.g. class masking) are created standalone with
                # no pipeline, so they are found by their classifications instead. This is done
                # in two steps on purpose. Collecting the unpipelined algorithm ids first, as an
                # explicit list, lets the classification lookup filter on `algorithm_id IN (...)`,
                # which the planner answers from the algorithm_id index. Expressing the same thing
                # as a single join (`pipelines__isnull=True, classifications__...`) hides those ids
                # behind an anti-join at plan time, so the planner sequentially scans the whole
                # classification table instead — a cost that grows with the platform's total
                # classification count rather than with this project. The first query is also
                # cheap to cache: it only changes when algorithms or pipeline links change, not on
                # every classification write.
                #
                # An algorithm attached to a pipeline that is not enabled for this project is
                # absent even when it owns determinations here. That matches the behaviour on the
                # pipeline join alone; widening the second lookup to cover it costs several times
                # the runtime and is left as a follow-up.
                # Sorted for the same reason as the outer id list below: this list is rendered
                # verbatim into the IN clause, and Algorithm's (name, version) ordering would
                # otherwise vary the id order — and so the SQL string and its cachalot key —
                # for identical membership.
                unpipelined_algorithm_ids = sorted(
                    Algorithm.objects.filter(pipelines__isnull=True).values_list("pk", flat=True)
                )
                # `.order_by()` clears Classification's default ordering before `.distinct()`.
                # Without it the ordering columns join the SELECT and widen the DISTINCT, so it
                # would return one row per classification rather than one per algorithm.
                post_processing_used_in_project = (
                    Classification.objects.filter(
                        algorithm_id__in=unpipelined_algorithm_ids,
                        detection__source_image__project=project,
                    )
                    .order_by()
                    .values_list("algorithm_id", flat=True)
                    .distinct()
                )
                # Sorted so the generated SQL is stable for a given result: cachalot keys its
                # cache on the query string, and an unordered set would vary it.
                relevant_ids = set(configured_for_project) | set(post_processing_used_in_project)
                qs = qs.filter(pk__in=sorted(relevant_ids))
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
