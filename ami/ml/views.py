import logging

import pydantic
from django.db import transaction
from django.db.models import Prefetch
from django.db.models.query import QuerySet
from django.http import Http404
from django.utils.text import slugify
from drf_spectacular.utils import extend_schema
from rest_framework import exceptions as api_exceptions
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from ami.base.pagination import TrainingDataPagination
from ami.base.permissions import ProjectPipelineConfigPermission
from ami.base.serializers import SingleParamSerializer
from ami.base.views import ProjectMixin
from ami.main.api.schemas import project_id_doc_param
from ami.main.api.views import DefaultViewSet
from ami.main.models import OccurrenceSet, Project, SourceImage
from ami.ml import training
from ami.ml.schemas import AlgorithmTrainingConfig, PipelineRegistrationResponse

from .models.algorithm import Algorithm, AlgorithmCategoryMap
from .models.embedding import DetectionEmbedding
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
    filterset_fields = ["name", "version", "trainable"]
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

    `occurrence_set` narrows this to one saved set. Without it the rows are every verified
    occurrence in the project, which is what a retrain does by default.

    GET /api/v2/ml/training-data/?project_id=3&algorithm=<key>
    GET /api/v2/ml/training-data/summary/?project_id=3&algorithm=<key>&occurrence_set=7
    """

    queryset = DetectionEmbedding.objects.none()
    serializer_class = TrainingDataRowSerializer
    require_project = True
    # The project permission is checked per request, in _get_project_for_training().
    # ObjectPermission's has_object_permission only runs for detail actions, and both
    # actions here are detail=False, so a viewset-level class would never see the project.
    permission_classes = [IsAuthenticated]
    filter_backends: list = []
    pagination_class = TrainingDataPagination

    def _get_project_for_training(self) -> Project:
        """
        The requested project, if this user may retrain its classifier.

        Project visibility is not enough of a gate here. A non-draft project is readable by
        anyone, and what this returns is every verified label in it together with the vector
        for each crop: the whole training set, not a page of occurrences. It is gated on the
        same permission the training job is, so the people who can start a run are the ones
        who can see what it would learn from.
        """
        project = self.get_active_project()
        if not project:
            raise Http404("Project not found.")
        if not self.request.user.has_perm(Project.Permissions.RUN_TRAIN_CLASSIFIER_JOB, project):
            raise api_exceptions.PermissionDenied("You do not have permission to retrain classifiers in this project.")
        return project

    def _get_algorithm(self) -> Algorithm:
        # Cached because the split settings fall back to this algorithm's own training
        # config, so one request asks for it from more than one place.
        if getattr(self, "_algorithm", None) is None:
            key = SingleParamSerializer[str].clean(
                "algorithm",
                serializers.CharField(
                    required=True,
                    help_text="Key of the algorithm whose embeddings to train on.",
                ),
                self.request.query_params,
            )
            algorithm = Algorithm.objects.filter(key=key).first()
            if not algorithm:
                raise api_exceptions.NotFound(f"No algorithm with key '{key}'.")
            self._algorithm = algorithm
        return self._algorithm

    def _get_occurrence_set(self, project: Project) -> OccurrenceSet | None:
        """
        The set to count, or None for every verified occurrence in the project.

        Optional, because retraining on everything verified so far is the common case and
        the form shows those numbers before anyone has chosen a set.
        """
        occurrence_set_id = SingleParamSerializer[int].clean(
            "occurrence_set",
            serializers.IntegerField(required=False, allow_null=True, default=None),
            self.request.query_params,
        )
        if not occurrence_set_id:
            return None
        # Scoped to the project: a set id from elsewhere must not report this project's
        # verified labels, or any other project's.
        occurrence_set = OccurrenceSet.objects.for_project(project).filter(pk=occurrence_set_id).first()
        if not occurrence_set:
            raise api_exceptions.NotFound(f"No occurrence set with id {occurrence_set_id} in this project.")
        return occurrence_set

    def _get_split_settings(self) -> AlgorithmTrainingConfig:
        """
        The settings these numbers are computed under.

        Defaulted to the algorithm's own training config rather than to the module defaults,
        so a form that shows the stats before anything is edited shows what an actual run
        would do. Anything the caller passes wins, which is how the form previews a changed
        split ratio without starting a job.
        """
        config = self._get_algorithm().training_config
        params = self.request.query_params
        overrides = {
            "split_salt": SingleParamSerializer[str].clean(
                "split_salt",
                serializers.CharField(required=False, allow_null=True, default=None),
                params,
            ),
            "test_fraction": SingleParamSerializer[float].clean(
                "test_fraction",
                serializers.FloatField(required=False, allow_null=True, default=None),
                params,
            ),
            "min_per_species": SingleParamSerializer[int].clean(
                "min_per_species",
                serializers.IntegerField(required=False, allow_null=True, default=None),
                params,
            ),
        }
        # A parameter that was not sent must not override the config with None.
        overrides = {name: value for name, value in overrides.items() if value is not None}
        try:
            return AlgorithmTrainingConfig.for_run(config, overrides)
        except pydantic.ValidationError as e:
            # The same bounds a job is held to, refused here rather than reported as stats
            # computed under settings no run could use.
            raise api_exceptions.ValidationError({"detail": e.errors()})

    def get_queryset(self) -> QuerySet[DetectionEmbedding]:
        project = self._get_project_for_training()
        qs = training.verified_training_rows(project, self._get_algorithm(), self._get_occurrence_set(project))

        self._split_filter = SingleParamSerializer[str].clean(
            "split",
            serializers.ChoiceField(choices=list(training.SPLITS), required=False, allow_null=True, default=None),
            self.request.query_params,
        )
        return qs

    def get_serializer_context(self):
        context = super().get_serializer_context()
        config = self._get_split_settings()
        context["split_salt"] = config.split_salt
        context["test_fraction"] = config.test_fraction
        # Not url_boolean_param: it returns `value or default`, so a default of True can
        # never be turned off.
        context["include_features"] = SingleParamSerializer[bool].clean(
            "include_features",
            serializers.BooleanField(required=False, default=True),
            self.request.query_params,
        )
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
        """
        Counts only, for what a retrain would learn from right now.

        This is what the training job form shows before anyone starts a run: how much
        verified data there is, how many species of it are usable, and how the split would
        fall. Cheap enough to re-fetch whenever the chosen set or the split ratio changes.
        """
        project = self._get_project_for_training()
        algorithm = self._get_algorithm()
        occurrence_set = self._get_occurrence_set(project)
        config = self._get_split_settings()

        counts = training.label_counts(project, algorithm, occurrence_set)
        kept = training.species_with_enough_examples(counts, config.min_per_species)
        rows = training.verified_training_rows(project, algorithm, occurrence_set)

        splits = {name: 0 for name in training.SPLITS}
        occurrences = set()
        for occurrence_id in rows.values_list("detection__occurrence_id", flat=True):
            splits[training.split_for(occurrence_id, config.split_salt, config.test_fraction)] += 1
            occurrences.add(occurrence_id)

        return Response(
            {
                "project": {"id": project.pk, "name": project.name},
                "algorithm": {"key": algorithm.key, "name": algorithm.name, "version": algorithm.version},
                # None means every verified occurrence in the project, which is what a run
                # without a set does.
                "occurrence_set": ({"id": occurrence_set.pk, "name": occurrence_set.name} if occurrence_set else None),
                "dimensions": DetectionEmbedding.objects.stored_length(algorithm.pk),
                "rows": sum(counts.values()),
                "occurrences": len(occurrences),
                "classes": len(counts),
                # What the head would actually learn, once species with too few crops are
                # dropped. Showing only the raw class count overstates the run.
                "trainable_classes": len(kept),
                "dropped_species": sorted(name for name in counts if name and name not in kept),
                "counts": dict(sorted(counts.items(), key=lambda kv: -kv[1])),
                "train": splits[training.SPLIT_TRAIN],
                "test": splits[training.SPLIT_TEST],
                "verified_detections_without_embedding": training.count_missing_embeddings(
                    project, algorithm, occurrence_set
                ),
                "settings": {
                    "min_per_species": config.min_per_species,
                    "split_salt": config.split_salt,
                    "test_fraction": config.test_fraction,
                    "split_grouped_by": "occurrence",
                },
            }
        )
