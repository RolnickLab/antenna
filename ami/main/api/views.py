import datetime
import logging
from statistics import mode

from django.contrib.postgres.search import TrigramSimilarity
from django.core import exceptions
from django.db import models
from django.db.models import OuterRef, Prefetch, Q, Subquery
from django.db.models.query import QuerySet
from django.forms import BooleanField, CharField, IntegerField
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import exceptions as api_exceptions
from rest_framework import filters, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.filters import SearchFilter
from rest_framework.generics import GenericAPIView
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from ami.base.filters import NullsLastOrderingFilter, ThresholdFilter
from ami.base.models import BaseQuerySet
from ami.base.pagination import LimitOffsetPaginationWithPermissions
from ami.base.permissions import IsActiveStaffOrReadOnly, IsProjectMemberOrReadOnly, ObjectPermission
from ami.base.serializers import FilterParamsSerializer, SingleParamSerializer
from ami.base.views import ProjectMixin
from ami.main.api.schemas import limit_doc_param, project_id_doc_param
from ami.main.api.serializers import TagSerializer
from ami.main.models_future.occurrence import top_identifiers_for_project
from ami.utils.requests import get_default_classification_threshold
from ami.utils.storages import ConnectionTestResult

from ..models import (
    BEST_IDENTIFICATION_ORDER,
    BEST_MACHINE_PREDICTION_ORDER,
    NULL_DETECTIONS_FILTER,
    Classification,
    Deployment,
    Detection,
    Device,
    Event,
    Identification,
    Occurrence,
    Page,
    Project,
    ProjectQuerySet,
    S3StorageSource,
    Site,
    SourceImage,
    SourceImageCollection,
    SourceImageUpload,
    Tag,
    TaxaList,
    Taxon,
    User,
    update_detection_counts,
)
from .serializers import (
    ClassificationListSerializer,
    ClassificationSerializer,
    ClassificationWithTaxaSerializer,
    DeploymentListSerializer,
    DeploymentSerializer,
    DetectionListSerializer,
    DetectionSerializer,
    DeviceSerializer,
    EventListSerializer,
    EventSerializer,
    EventTimelineSerializer,
    IdentificationSerializer,
    OccurrenceListSerializer,
    OccurrenceSerializer,
    PageListSerializer,
    PageSerializer,
    ProjectListSerializer,
    ProjectSerializer,
    SiteSerializer,
    SourceImageCollectionSerializer,
    SourceImageListSerializer,
    SourceImageSerializer,
    SourceImageUploadSerializer,
    StorageSourceSerializer,
    StorageStatusSerializer,
    TaxaListSerializer,
    TaxaListTaxonInputSerializer,
    TaxaListTaxonSerializer,
    TaxonListSerializer,
    TaxonSearchResultSerializer,
    TaxonSerializer,
    TopIdentifiersResponseSerializer,
)

logger = logging.getLogger(__name__)

# def index(request: HttpRequest) -> HttpResponse:
#     """
#     Main (or index) view.
#
#     Returns rendered default page to the user.
#     Typed with the help of ``django-stubs`` project.
#     """
#     return render(request, "main/index.html")


class DefaultViewSetMixin:
    filter_backends = [
        DjangoFilterBackend,
        NullsLastOrderingFilter,
        SearchFilter,
    ]
    filterset_fields = []
    ordering_fields = ["created_at", "updated_at"]
    search_fields = []
    permission_classes = [IsActiveStaffOrReadOnly]


class DefaultViewSet(DefaultViewSetMixin, viewsets.ModelViewSet):
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        # Create instance but do not save
        instance = serializer.Meta.model(**serializer.validated_data)  # type: ignore
        self.check_object_permissions(request, instance)
        self.perform_create(serializer)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def get_queryset(self):
        qs: QuerySet = super().get_queryset()
        assert self.queryset is not None

        if isinstance(qs, BaseQuerySet):
            return qs.visible_for_user(self.request.user)  # type: ignore

        return qs


class DefaultReadOnlyViewSet(DefaultViewSetMixin, viewsets.ReadOnlyModelViewSet):
    pass


class ProjectPagination(LimitOffsetPaginationWithPermissions):
    default_limit = 40

    def get_count(self, queryset):
        # The recent-activity orderings annotate correlated subqueries onto the
        # queryset. They don't change the row count, so strip them (and ordering)
        # before counting to keep the pagination COUNT query cheap.
        return super().get_count(queryset.order_by().values("pk"))


class ProjectViewSet(DefaultViewSet, ProjectMixin):
    """
    API endpoint that allows projects to be viewed or edited.
    """

    queryset = Project.objects.filter(active=True).prefetch_related("deployments").all()
    serializer_class = ProjectSerializer
    pagination_class = ProjectPagination
    permission_classes = [ObjectPermission]
    ordering_fields = [
        "name",
        "created_at",
        "updated_at",
        # The three below are not Project fields; get_queryset annotates them on
        # demand (see below). last_capture_timestamp mirrors the DeploymentViewSet
        # ordering of the same name, but is a per-project rollup of capture times.
        "last_capture_timestamp",
        "last_occurrence_updated_at",
        "last_job_updated_at",
    ]

    def get_queryset(self):
        qs: ProjectQuerySet = super().get_queryset()  # type: ignore
        # Filter projects by `user_id`
        user_id = self.request.query_params.get("user_id")
        if user_id:
            user = User.objects.filter(pk=user_id).first()
            if not user == self.request.user:
                raise PermissionDenied("You can only view your projects")
            if user:
                qs = qs.filter_by_user(user)

        # Annotate "recent activity" fields only when sorting by them, so the
        # default list stays cheap. Each is a correlated subquery returning one
        # row via a covering index, and only one is ever added per request.
        ordering = {field.lstrip("-") for field in self.request.query_params.get("ordering", "").split(",") if field}
        if "last_capture_timestamp" in ordering:
            # Live max capture time per project (Index Only Scan on
            # main_source_proj_ts_desc_idx); kept live rather than reading the
            # denormalized Deployment field so the sort never lags ingestion.
            # timestamp is nullable, and DESC sorts NULLs first, so exclude them
            # explicitly — otherwise a single undated capture masks the real max.
            qs = qs.annotate(
                last_capture_timestamp=Subquery(
                    SourceImage.objects.filter(project=OuterRef("pk"), timestamp__isnull=False)
                    .order_by("-timestamp")
                    .values("timestamp")[:1]
                )
            )
        if "last_occurrence_updated_at" in ordering:
            qs = qs.annotate(
                last_occurrence_updated_at=Subquery(
                    Occurrence.objects.filter(project=OuterRef("pk")).order_by("-updated_at").values("updated_at")[:1]
                )
            )
        if "last_job_updated_at" in ordering:
            from ami.jobs.models import Job

            qs = qs.annotate(
                last_job_updated_at=Subquery(
                    Job.objects.filter(project=OuterRef("pk")).order_by("-updated_at").values("updated_at")[:1]
                )
            )
        return qs

    def get_serializer_class(self):
        """
        Return different serializers for list and detail views.
        """
        if self.action == "list":
            return ProjectListSerializer
        else:
            return ProjectSerializer

    def get_serializer_context(self):
        """
        Add with_charts flag to serializer context.
        """
        context = super().get_serializer_context()
        with_charts_default = False

        # For detail view, include charts by default
        if self.action == "retrieve":
            with_charts_default = True

        with_charts = self.request.query_params.get("with_charts", with_charts_default)
        if with_charts is not None:
            with_charts = BooleanField(required=False).clean(with_charts)

        context["with_charts"] = with_charts
        return context

    def perform_create(self, serializer):
        super().perform_create(serializer)
        # Check if user is authenticated
        if not self.request.user or not self.request.user.is_authenticated:
            raise PermissionDenied("You must be authenticated to create a project.")

        # Add current user as project owner
        serializer.save(owner=self.request.user)

    @action(detail=True, methods=["get"], name="charts")
    def charts(self, request, pk=None):
        """
        Get chart data for a project.
        """
        project = self.get_object()
        return Response({"summary_data": project.summary_data()})

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="user_id",
                description=(
                    "Filters projects to show only those associated with the specified user ID. "
                    "If omitted, no user-specific filter is applied."
                ),
                required=False,
                type=OpenApiTypes.INT,
            ),
        ]
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)


class DeploymentViewSet(DefaultViewSet, ProjectMixin):
    """
    A model viewset that uses different serializers
    for the list and detail views.
    """

    queryset = Deployment.objects.select_related("project", "device", "research_site")
    ordering_fields = [
        "created_at",
        "updated_at",
        "captures_count",
        "events_count",
        "occurrences_count",
        "taxa_count",
        "first_capture_timestamp",
        "last_capture_timestamp",
        "name",
    ]

    permission_classes = [ObjectPermission]

    def get_serializer_class(self):
        """
        Return different serializers for list and detail views.
        """
        if self.action == "list":
            return DeploymentListSerializer
        else:
            return DeploymentSerializer

    def get_queryset(self) -> QuerySet:
        qs = super().get_queryset()
        project = self.get_active_project()
        if project:
            qs = qs.filter(project=project)
        num_example_captures = 10
        if self.action == "retrieve":
            qs = qs.prefetch_related(
                Prefetch(
                    "captures",
                    queryset=SourceImage.objects.order_by("-size")[:num_example_captures],
                    to_attr="example_captures",
                )
            )

            qs = qs.prefetch_related(
                Prefetch(
                    "manually_uploaded_captures",
                    queryset=SourceImage.objects.order_by("created_at").exclude(upload=None),
                )
            )

        return qs

    @action(detail=True, methods=["post"], name="sync")
    def sync(self, _request, pk=None) -> Response:
        """
        Queue a task to sync data from the deployment's data source.
        """
        deployment: Deployment = self.get_object()
        if deployment and deployment.data_source:
            # queued_task = tasks.sync_source_images.delay(deployment.pk)
            from ami.jobs.models import DataStorageSyncJob, Job

            job = Job.objects.create(
                name=f"Sync captures for deployment {deployment.pk}",
                deployment=deployment,
                project=deployment.project,
                job_type_key=DataStorageSyncJob.key,
            )
            job.enqueue()
            msg = f"Syncing captures for deployment {deployment.pk} from {deployment.data_source_uri} in background."
            logger.info(msg)
            assert deployment.project
            return Response({"job_id": job.pk, "project_id": deployment.project.pk})
        else:
            raise api_exceptions.ValidationError(detail="Deployment must have a data source to sync captures from")

    @extend_schema(parameters=[project_id_doc_param])
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)


class EventViewSet(DefaultViewSet, ProjectMixin):
    """
    API endpoint that allows events to be viewed or edited.
    """

    queryset = Event.objects.all()
    serializer_class = EventSerializer
    filterset_fields = ["deployment"]
    ordering_fields = [
        "created_at",
        "updated_at",
        "deployment",
        "start",
        "start__time",
        "captures_count",
        "detections_count",
        "occurrences_count",
        "taxa_count",
        "duration",
    ]

    def get_serializer_class(self):
        """
        Return different serializers for list and detail views.
        """
        if self.action == "list":
            return EventListSerializer
        else:
            return EventSerializer

    def get_queryset(self) -> QuerySet:
        qs: QuerySet = super().get_queryset()
        project = self.get_active_project()
        if project:
            qs = qs.filter(project=project)
        qs = qs.filter(deployment__isnull=False)
        qs = qs.annotate(
            duration=models.F("end") - models.F("start"),
        ).select_related("deployment", "project")

        if self.action == "list":
            num_example_captures = 1
            qs = qs.prefetch_related(
                Prefetch(
                    "captures",
                    queryset=SourceImage.objects.order_by("-size").select_related(
                        "deployment",
                        "deployment__data_source",
                    )[:num_example_captures],
                    to_attr="example_captures",
                )
            )

            qs = qs.with_taxa_count(project=project, request=self.request)  # type: ignore

        return qs

    @action(detail=True, methods=["get"], name="timeline")
    def timeline(self, request, pk=None):
        """
        Return a list of time intervals and the number of detections for each interval,
        including intervals where no source images were captured, along with meta information.
        """
        event = self.get_object()
        resolution_minutes = IntegerField(required=False, min_value=1).clean(
            request.query_params.get("resolution_minutes", 1)
        )
        resolution = datetime.timedelta(minutes=resolution_minutes)

        qs = SourceImage.objects.filter(event=event).with_was_processed()  # type: ignore

        # Bulk update all source images where detections_count is null
        update_detection_counts(qs=qs, null_only=True)

        # Fetch aggregated data for efficiency
        aggregates = qs.aggregate(
            min_detections=models.Min("detections_count"),
            max_detections=models.Max("detections_count"),
            total_detections=models.Sum("detections_count"),
            first_capture=models.Min("timestamp"),
            last_capture=models.Max("timestamp"),
        )

        start_time = event.start
        end_time = event.end or timezone.now()

        # Adjust start and end times based on actual captures
        if aggregates["first_capture"]:
            start_time = max(start_time, aggregates["first_capture"])
        if aggregates["last_capture"]:
            end_time = min(end_time, aggregates["last_capture"])

        source_images = list(
            qs.filter(timestamp__range=(start_time, end_time))
            .order_by("timestamp")
            .values("id", "timestamp", "detections_count", "was_processed")
        )

        timeline = []
        current_time = start_time
        image_index = 0

        while current_time <= end_time:
            interval_end = min(current_time + resolution, end_time)
            interval_data = {
                "start": current_time,
                "end": interval_end,
                "first_capture": None,
                "top_capture": None,
                "captures_count": 0,
                "detections_count": 0,
                "detection_counts": [],
                "was_processed": False,
            }

            while image_index < len(source_images) and source_images[image_index]["timestamp"] <= interval_end:
                image = source_images[image_index]
                if interval_data["first_capture"] is None:
                    interval_data["first_capture"] = SourceImage(pk=image["id"])
                interval_data["captures_count"] += 1
                interval_data["detections_count"] += image["detections_count"] or 0
                interval_data["detection_counts"] += [image["detections_count"]]
                if image["detections_count"] >= max(interval_data["detection_counts"]):
                    interval_data["top_capture"] = SourceImage(pk=image["id"])
                # Track if any image in this interval was processed
                if image["was_processed"]:
                    interval_data["was_processed"] = True
                image_index += 1

            # Set a meaningful average detection count to display for the interval
            # Remove zero values and calculate the mode
            interval_data["detection_counts"] = [x for x in interval_data["detection_counts"] if x > 0]
            interval_data["detections_avg"] = mode(interval_data["detection_counts"] or [0])

            timeline.append(interval_data)
            current_time = interval_end

            if current_time >= end_time:
                break

        serializer = EventTimelineSerializer(
            {
                "data": timeline,
                "meta": {
                    "total_intervals": len(timeline),
                    "resolution_minutes": resolution_minutes,
                    "max_detections": aggregates["max_detections"] or 0,
                    "min_detections": aggregates["min_detections"] or 0,
                    "total_detections": aggregates["total_detections"] or 0,
                    "timeline_start": start_time,
                    "timeline_end": end_time,
                },
            },
            context={"request": request},
        )
        return Response(serializer.data)

    @extend_schema(parameters=[project_id_doc_param])
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)


class SourceImageViewSet(DefaultViewSet, ProjectMixin):
    """
    API endpoint that allows captures from monitoring sessions to be viewed or edited.

    Standard list endpoint:
    GET /captures/?event=1&limit=10&offset=0&ordering=-timestamp

    Standard detail endpoint:
    GET /captures/1/
    """

    require_project_for_list = True  # Unfiltered list scans are too expensive on this table
    queryset = SourceImage.objects.all()

    serializer_class = SourceImageSerializer
    filterset_fields = [
        "event",
        "deployment",
        "deployment__project",
        "collections",
        "project",
        "project_id",
    ]
    ordering_fields = [
        "created_at",
        "updated_at",
        "timestamp",
        "size",
        "width",
        "height",
        "detections_count",
        "occurrences_count",
        "taxa_count",
        "deployment__name",
        "event__start",
        "path",
    ]
    permission_classes = [ObjectPermission]

    def get_serializer_class(self):
        """
        Return different serializers for list and detail views.
        """
        if self.action == "list":
            return SourceImageListSerializer
        else:
            return SourceImageSerializer

    def get_serializer_context(self):
        return {"request": self.request}

    def get_queryset(self) -> QuerySet:
        queryset = super().get_queryset()
        with_detections_default = False
        with_counts_default = False
        # If this is a retrieve request or with detections or counts are explicitly requested, require project
        if (
            self.action == "retrieve"
            or "with_detections" in self.request.query_params
            or "with_counts" in self.request.query_params
        ):
            self.require_project = True
        project = self.get_active_project()

        queryset = queryset.select_related(
            "event",
            "deployment",
            "deployment__data_source",
        ).order_by("timestamp")

        if self.action == "list":
            # It's cumbersome to override the default list view, so customize the queryset here
            queryset = self.filter_by_has_detections(queryset)

        elif self.action == "retrieve":
            # For detail view, include storage info and additional prefetches
            with_counts_default = True
            queryset = queryset.prefetch_related("jobs", "collections")
            queryset = self.add_adjacent_captures(queryset)
            with_detections_default = True

        with_detections = self.request.query_params.get("with_detections", with_detections_default)
        if with_detections is not None:
            # Convert string to boolean
            with_detections = BooleanField(required=False).clean(with_detections)

        if with_detections:
            queryset = self.prefetch_detections(queryset, project)

        with_counts = self.request.query_params.get("with_counts", with_counts_default)
        if with_counts is not None:
            with_counts = BooleanField(required=False).clean(with_counts)

        if with_counts:
            queryset = queryset.with_occurrences_count(  # type: ignore
                project=project, request=self.request
            ).with_taxa_count(  # type: ignore
                project=project, request=self.request
            )

        return queryset

    def filter_by_has_detections(self, queryset: QuerySet) -> QuerySet:
        has_detections = self.request.query_params.get("has_detections")
        if has_detections is not None:
            has_detections = BooleanField(required=False).clean(has_detections)
            queryset = queryset.annotate(
                has_detections=models.Exists(Detection.objects.filter(source_image=models.OuterRef("pk"))),
            ).filter(has_detections=has_detections)
        return queryset

    def prefetch_detections(self, queryset: QuerySet, project: Project | None = None) -> QuerySet:
        """
        Return all detections for source images, but only include occurrence data
        for occurrences that pass the default filters

        Create a custom queryset that includes all detections but conditionally loads occurrence data
        We include all detections and add a flag indicating if the occurrence meets the default filters
        """

        if project is None:
            # Return a prefetch with zero detections
            logger.warning("Returning zero detections with source image because no project was specified")
            return queryset.prefetch_related(
                Prefetch(
                    "detections",
                    queryset=Detection.objects.none(),
                    to_attr="filtered_detections",
                )
            )

        qualifying_occurrence_ids = Occurrence.objects.apply_default_filters(  # type: ignore
            project, self.request
        ).values_list("id", flat=True)
        score = get_default_classification_threshold(project, self.request)

        prefetch_queryset = (
            Detection.objects.exclude(NULL_DETECTIONS_FILTER)
            .annotate(
                determination_score=models.Max("occurrence__detections__classifications__score"),
                # Store whether this occurrence should be included based on default filters
                occurrence_meets_criteria=models.Case(
                    models.When(
                        models.Q(occurrence_id__in=models.Subquery(qualifying_occurrence_ids)),
                        then=models.Value(True),
                    ),
                    default=models.Value(False),  # False for detections without occurrences
                    output_field=models.BooleanField(),
                ),
                score_threshold=models.Value(score, output_field=models.FloatField()),
            )
            .select_related("occurrence", "occurrence__determination")
        )

        related_detections = Prefetch(
            "detections",
            queryset=prefetch_queryset,
            to_attr="filtered_detections",
        )

        queryset = queryset.prefetch_related(related_detections)
        return queryset

    def add_adjacent_captures(self, queryset: QuerySet) -> QuerySet:
        """
        These are helpful for the frontend to navigate between captures in the same event.

        However they likely belong in the EventViewSet, or another endpoint.
        @TODO Consider a custom endpoint for capture details specific to the Session Detail view.
        """

        # Subquery for the next image
        next_image = (
            SourceImage.objects.filter(event=models.OuterRef("event"), timestamp__gt=models.OuterRef("timestamp"))
            .order_by("timestamp")[:1]
            .values("id")[:1]
        )

        # Subquery for the previous image
        previous_image = (
            SourceImage.objects.filter(event=models.OuterRef("event"), timestamp__lt=models.OuterRef("timestamp"))
            .order_by("-timestamp")
            .values("id")[:1]
        )

        # Subquery for the current capture's index
        index_subquery = (
            SourceImage.objects.filter(event=models.OuterRef("event"), timestamp__lte=models.OuterRef("timestamp"))
            .values("event")
            .annotate(index=models.Count("id"))
            .values("index")
        )

        # Subquery for the total captures in the event
        total_subquery = (
            SourceImage.objects.filter(event=models.OuterRef("event"))
            .values("event")
            .annotate(total=models.Count("id"))
            .values("total")
        )

        return queryset.annotate(
            event_next_capture_id=models.Subquery(next_image, output_field=models.IntegerField()),
            event_prev_capture_id=models.Subquery(previous_image, output_field=models.IntegerField()),
            event_current_capture_index=models.Subquery(index_subquery, output_field=models.IntegerField()),
            event_total_captures=models.Subquery(total_subquery, output_field=models.IntegerField()),
        )

    @action(detail=True, methods=["post"], name="star")
    def star(self, _request, pk=None) -> Response:
        """
        Add a capture to the project's starred images capture set.
        """
        source_image: SourceImage = self.get_object()
        if source_image and source_image.deployment and source_image.deployment.project:
            collection = SourceImageCollection.get_or_create_starred_collection(source_image.deployment.project)
            collection.images.add(source_image)
            return Response({"collection": collection.pk, "total_images": collection.images.count()})
        else:
            raise api_exceptions.ValidationError(detail="Source image must be associated with a project")

    @action(detail=True, methods=["post"], name="unstar")
    def unstar(self, _request, pk=None) -> Response:
        """
        Remove a capture from the project's starred images capture set.
        """
        source_image: SourceImage = self.get_object()
        if source_image and source_image.deployment and source_image.deployment.project:
            collection = SourceImageCollection.get_or_create_starred_collection(source_image.deployment.project)
            collection.images.remove(source_image)
            return Response({"collection": collection.pk, "total_images": collection.images.count()})
        else:
            raise api_exceptions.ValidationError(detail="Source image must be associated with a project")


class SourceImageCollectionViewSet(DefaultViewSet, ProjectMixin):
    """
    Endpoint for viewing capture sets or samples of captures.
    """

    queryset = (
        SourceImageCollection.objects.all()
        .with_source_images_count()  # type: ignore
        .with_source_images_with_detections_count()
        .with_source_images_processed_count()
        .prefetch_related("jobs")
    )
    serializer_class = SourceImageCollectionSerializer
    permission_classes = [
        ObjectPermission,
    ]
    filterset_fields = ["method"]
    ordering_fields = [
        "id",
        "created_at",
        "updated_at",
        "name",
        "method",
        "source_images_count",
        "source_images_with_detections_count",
        "source_images_processed_count",
        "occurrences_count",
    ]

    def get_queryset(self) -> QuerySet:
        query_set: QuerySet = super().get_queryset()
        with_counts_default = False
        # If with_counts is explicitly requested, require project
        if "with_counts" in self.request.query_params:
            self.require_project = True
        project = self.get_active_project()

        if project:
            query_set = query_set.filter(project=project)

        if self.action == "retrieve":
            # For detail view, include counts by default
            with_counts_default = True

        with_counts = self.request.query_params.get("with_counts", with_counts_default)
        if with_counts is not None:
            with_counts = BooleanField(required=False).clean(with_counts)

        if with_counts:
            classification_threshold = get_default_classification_threshold(project, self.request)
            query_set = query_set.with_occurrences_count(  # type: ignore
                classification_threshold=classification_threshold, project=project, request=self.request
            ).with_taxa_count(  # type: ignore
                classification_threshold=classification_threshold, project=project, request=self.request
            )

        return query_set

    @action(detail=True, methods=["post"], name="populate")
    def populate(self, request, pk=None):
        """
        Populate a capture set with captures using the configured sampling method and arguments.
        """
        collection: SourceImageCollection = self.get_object()

        if collection:
            from ami.jobs.models import Job, SourceImageCollectionPopulateJob

            assert collection.project, "Capture set must be associated with a project"
            job = Job.objects.create(
                name=f"Populate captures for capture set {collection.pk}",
                project=collection.project,
                source_image_collection=collection,
                job_type_key=SourceImageCollectionPopulateJob.key,
            )
            job.enqueue()
            msg = f"Populating captures for capture set {collection.pk} in background."
            logger.info(msg)
            return Response({"job_id": job.pk, "project_id": collection.project.pk})
        else:
            raise api_exceptions.ValidationError(detail="Invalid capture set requested")

    def _get_source_image(self):
        """
        Get source image from either GET query param or in the PUT/POST request body.
        """
        key = "source_image"
        source_image_id = SingleParamSerializer[int].clean(
            key,
            field=serializers.IntegerField(required=True, min_value=0),
            data=dict(self.request.data, **self.request.query_params),
        )

        try:
            return SourceImage.objects.get(id=source_image_id)
        except SourceImage.DoesNotExist:
            raise api_exceptions.NotFound(detail=f"SourceImage with id {source_image_id} not found")

    def _serialize_source_image(self, source_image):
        if source_image:
            return SourceImageListSerializer(source_image, context={"request": self.request}).data
        else:
            return None

    @action(detail=True, methods=["post"], name="add")
    def add(self, request, pk=None):
        """
        Add a capture to a capture set.
        """
        collection: SourceImageCollection = self.get_object()
        source_image = self._get_source_image()
        collection.images.add(source_image)

        return Response(
            {
                "collection": collection.pk,
                "total_images": collection.images.count(),
            }
        )

    @action(detail=True, methods=["post"], name="remove")
    def remove(self, request, pk=None):
        """
        Remove a capture from a capture set.
        """
        collection = self.get_object()
        source_image = self._get_source_image()
        collection.images.remove(source_image)
        return Response(
            {
                "collection": collection.pk,
                "total_images": collection.images.count(),
            }
        )

    @extend_schema(parameters=[project_id_doc_param])
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)


class SourceImageUploadViewSet(DefaultViewSet, ProjectMixin):
    """
    Endpoint for uploading images.
    """

    queryset = SourceImageUpload.objects.all()

    serializer_class = SourceImageUploadSerializer
    permission_classes = [ObjectPermission]
    require_project = True

    def get_queryset(self) -> QuerySet:
        # Only allow users to see their own uploads
        qs = super().get_queryset()
        if self.request.user.pk:
            qs = qs.filter(user=self.request.user)
        return qs

    pagination_class = LimitOffsetPaginationWithPermissions
    # This is the maximum limit for manually uploaded captures
    pagination_class.default_limit = 20

    def perform_create(self, serializer):
        """
        Save the SourceImageUpload with the current user and create the associated SourceImage.
        """
        from ami.base.serializers import get_current_user
        from ami.main.models import create_source_image_from_upload

        # Get current user from request
        user = get_current_user(self.request)

        # Create the SourceImageUpload object with the user
        obj = serializer.save(user=user)

        # Get process_now flag from project feature flags
        process_now = SingleParamSerializer[bool].clean(
            param_name="process_now",
            field=serializers.BooleanField(required=True),
            data=self.request.query_params,
        )

        # Create source image from the upload
        source_image = create_source_image_from_upload(
            image=obj.image,
            deployment=obj.deployment,
            request=self.request,
            process_now=process_now,
        )

        # Update the source_image reference and save
        obj.source_image = source_image
        obj.save()


class DetectionViewSet(DefaultViewSet, ProjectMixin):
    """
    API endpoint that allows detections to be viewed or edited.
    """

    require_project_for_list = True  # Unfiltered list scans are too expensive on this table
    queryset = Detection.objects.exclude(NULL_DETECTIONS_FILTER).select_related("source_image", "detection_algorithm")
    serializer_class = DetectionSerializer
    filterset_fields = ["source_image", "detection_algorithm", "source_image__project"]
    ordering_fields = ["created_at", "updated_at", "detection_score", "timestamp"]

    def get_serializer_class(self):
        """
        Return different serializers for list and detail views.
        """
        if self.action == "list":
            return DetectionListSerializer
        else:
            return DetectionSerializer

    @extend_schema(parameters=[project_id_doc_param])
    def list(self, request, *args, **kwargs):
        # Force project_id validation before pagination triggers a full-table COUNT.
        self.get_active_project()
        return super().list(request, *args, **kwargs)


class CustomTaxonFilter(filters.BaseFilterBackend):
    """
    Find a taxon and its children.
    """

    query_params = ["taxon"]

    def get_filter_taxon(self, request: Request, query_params: list[str] | None = None) -> Taxon | None:
        taxon_id = None
        for param in query_params or self.query_params:
            taxon_id = request.query_params.get(param)
            if taxon_id:
                break
        if not taxon_id:
            return None

        try:
            # @TODO In the future filter by active taxa only, or any other required criteria (use the default queryset)
            taxon = Taxon.objects.get(id=taxon_id)
        except Taxon.DoesNotExist:
            raise NotFound(f"No taxon found with id {taxon_id}")
        else:
            return taxon

    def filter_queryset(self, request, queryset, view):
        taxon = self.get_filter_taxon(request)
        if taxon:
            # Here the queryset is the Taxon queryset
            return queryset.filter(models.Q(id=taxon.pk) | models.Q(parents_json__contains=[{"id": taxon.pk}]))
        else:
            # No taxon id in the query params
            return queryset


class CustomOccurrenceDeterminationFilter(CustomTaxonFilter):
    """
    Find an occurrence that was determined to be a taxon or andy of the taxon's children.
    """

    # "determination" is what we are filtering by, but "taxon" is also a valid query param for convenience
    # and consistency with the TaxonViewSet.
    query_params = ["determination", "taxon"]

    def filter_queryset(self, request, queryset, view):
        taxon = self.get_filter_taxon(request, query_params=self.query_params)
        if taxon:
            # Here the queryset is the Occurrence queryset.
            # The literal parents_json containment (constant RHS) is what the GIN index from
            # migration 0087 serves — this hierarchical taxon filter is the index's main consumer.
            return queryset.filter(
                models.Q(determination=taxon) | models.Q(determination__parents_json__contains=[{"id": taxon.pk}])
            )
        else:
            return queryset


class OccurrenceCollectionFilter(filters.BaseFilterBackend):
    """
    Filter occurrences by the capture set their detections' captures belong to.
    """

    query_params = ["collection_id", "collection"]  # @TODO remove "collection" param when UI is updated

    def filter_queryset(self, request, queryset, view):
        collection_id = None
        for param in self.query_params:
            collection_id = IntegerField(required=False).clean(request.query_params.get(param))
            if collection_id:
                break
        if collection_id:
            # Here the queryset is the Occurrence queryset
            return queryset.filter(detections__source_image__collections=collection_id)
        else:
            return queryset


class OccurrenceAlgorithmFilter(filters.BaseFilterBackend):
    """
    Filter occurrences by the detection algorithm that detected them.

    Accepts a list of algorithm ids to filter by or exclude by.

    This filter can be both inclusive and exclusive.
    """

    query_param = "algorithm"
    query_param_exclusive = f"not_{query_param}"

    def filter_queryset(self, request, queryset, view):
        algorithm_ids = request.query_params.getlist(self.query_param)
        algorithm_ids_exclusive = request.query_params.getlist(self.query_param_exclusive)

        if algorithm_ids:
            queryset = queryset.filter(detections__classifications__algorithm__in=algorithm_ids)
        if algorithm_ids_exclusive:
            queryset = queryset.exclude(detections__classifications__algorithm__in=algorithm_ids_exclusive)

        return queryset


class OccurrenceVerified(filters.BaseFilterBackend):
    """
    Filter occurrences that have been or not been identified by any user.
    """

    query_param = "verified"

    def filter_queryset(self, request, queryset, view):
        # Check presence of the query param before attempting to cast None to a boolean
        if self.query_param in request.query_params:
            verified = BooleanField(required=False).clean(request.query_params.get(self.query_param))
            if verified:
                queryset = queryset.filter(identifications__isnull=False)
            else:
                queryset = queryset.filter(identifications__isnull=True)

        return queryset


class OccurrenceVerifiedByMeFilter(filters.BaseFilterBackend):
    """
    Filter occurrences that have been or not been identified by the current user.
    """

    query_param = "verified_by_me"

    def filter_queryset(self, request: Request, queryset, view):
        if self.query_param in request.query_params and request.user and request.user.is_authenticated:
            verified_by_me = BooleanField(required=False).clean(request.query_params.get(self.query_param))
            if verified_by_me:
                queryset = queryset.filter(identifications__user=request.user)
            else:
                queryset = queryset.exclude(identifications__user=request.user)

        return queryset


class DateRangeFilterSerializer(FilterParamsSerializer):
    date_start = serializers.DateField(required=False)
    date_end = serializers.DateField(required=False)

    def validate(self, data):
        """
        Additionally validate that the start date is before the end date.
        """
        start_date = data.get("date_start")
        end_date = data.get("date_end")
        if start_date and end_date and start_date > end_date:
            raise api_exceptions.ValidationError({"date_start": "Start date must be before end date"})
        return data


class OccurrenceDateFilter(filters.BaseFilterBackend):
    """
    Filter occurrences within a date range that their detections were observed.
    """

    def filter_queryset(self, request, queryset, view):
        # Validate and clean the query params. They should be in ISO format.
        cleaned_data = DateRangeFilterSerializer(data=request.query_params).clean()

        # Access the validated dates
        start_date = cleaned_data.get("date_start")
        end_date = cleaned_data.get("date_end")

        if start_date:
            queryset = queryset.filter(detections__timestamp__date__gte=start_date)
        if end_date:
            queryset = queryset.filter(detections__timestamp__date__lte=end_date)

        return queryset


class OccurrenceTaxaListFilter(filters.BaseFilterBackend):
    """
    Filters occurrences based on a TaxaList.

    Queries for all occurrences where the determination taxon is either:
    - Directly in the requested TaxaList.
    - A descendant (child or deeper) of any taxon in the TaxaList, recursively.

    """

    query_param = "taxa_list_id"
    query_param_exclusive = f"not_{query_param}"

    def filter_queryset(self, request, queryset, view):
        taxalist_id = IntegerField(required=False).clean(request.query_params.get(self.query_param))
        taxalist_id_exclusive = IntegerField(required=False).clean(
            request.query_params.get(self.query_param_exclusive)
        )

        if taxalist_id:
            taxa_list = TaxaList.objects.filter(id=taxalist_id).first()
            if taxa_list:
                taxa = taxa_list.taxa.all()  # Get taxa list taxon objects

                # Filter by the exact determination
                query_filter = Q(determination__in=taxa)

                # Filter by the taxon's children
                for taxon in taxa:
                    query_filter |= Q(determination__parents_json__contains=[{"id": taxon.pk}])

                queryset = queryset.filter(query_filter)

        if taxalist_id_exclusive:
            taxa_list = TaxaList.objects.filter(id=taxalist_id_exclusive).first()
            if taxa_list:
                taxa = taxa_list.taxa.all()  # Get taxa list taxon objects

                # Filter by the exact determination
                query_filter = Q(determination__in=taxa)

                # Filter by the taxon's children
                for taxon in taxa:
                    query_filter |= Q(determination__parents_json__contains=[{"id": taxon.pk}])

                queryset = queryset.exclude(query_filter)

        return queryset


class TaxonCollectionFilter(filters.BaseFilterBackend):
    """
    Filter taxa by the capture set their occurrences belong to.
    """

    query_param = "collection"

    def filter_queryset(self, request, queryset, view):
        collection_id = IntegerField(required=False).clean(request.query_params.get(self.query_param))
        if collection_id:
            # Here the queryset is the Taxon queryset
            return queryset.filter(occurrences__detections__source_image__collections=collection_id)
        else:
            return queryset


class OccurrenceViewSet(DefaultViewSet, ProjectMixin):
    """
    API endpoint that allows occurrences to be viewed or edited.
    """

    require_project_for_list = True  # Unfiltered list scans are too expensive on this table
    queryset = Occurrence.objects.all()

    serializer_class = OccurrenceSerializer
    # filter_backends = [CustomDeterminationFilter, DjangoFilterBackend, NullsLastOrderingFilter, SearchFilter]
    filter_backends = DefaultViewSetMixin.filter_backends + [
        CustomOccurrenceDeterminationFilter,
        OccurrenceCollectionFilter,
        OccurrenceAlgorithmFilter,
        OccurrenceDateFilter,
        OccurrenceVerified,
        OccurrenceVerifiedByMeFilter,
        OccurrenceTaxaListFilter,
    ]
    filterset_fields = [
        "event",
        "deployment",
        "determination__rank",
        "detections__source_image",
    ]
    ordering_fields = [
        "created_at",
        "updated_at",
        "event__start",
        "first_appearance_timestamp",
        "first_appearance_time",
        "duration",
        "deployment",
        "determination",
        "determination__name",
        "determination_score",
        "event",
        "detections_count",
    ]

    def get_serializer_class(self):
        """
        Return different serializers for list and detail views.
        """
        if self.action == "list":
            return OccurrenceListSerializer
        else:
            return OccurrenceSerializer

    def get_queryset(self) -> QuerySet["Occurrence"]:
        project = self.get_active_project()
        qs = super().get_queryset().valid()  # type: ignore
        if project:
            qs = qs.filter(project=project)
        qs = qs.select_related(
            "determination",
            "deployment",
            "event",
        )
        qs = qs.with_detections_count().with_timestamps()  # type: ignore
        qs = qs.with_identifications()  # type: ignore
        qs = qs.apply_default_filters(project, self.request)  # type: ignore
        if self.action == "list":
            qs = qs.with_list_prefetches()  # type: ignore
        else:
            qs = qs.with_detail_prefetches()  # type: ignore

        return qs

    @extend_schema(
        parameters=[
            project_id_doc_param,
            OpenApiParameter(
                name="classification_threshold",
                description="Filter occurrences by minimum determination score.",
                required=False,
                type=OpenApiTypes.FLOAT,
            ),
            OpenApiParameter(
                name="taxon",
                description="Filter occurrences by determination taxon ID. Shows occurrences determined as this taxon "
                "or any of its child taxa.",
                required=False,
                type=OpenApiTypes.INT,
            ),
            OpenApiParameter(
                name="collection_id",
                description="Filter occurrences by the capture set their detections' captures belong to.",
                required=False,
                type=OpenApiTypes.INT,
            ),
        ]
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)


class OccurrenceStatsViewSet(viewsets.GenericViewSet, ProjectMixin):
    """Aggregate stats over Occurrences. Each @action == one stats kind.

    Response shape per kind is declared via a DRF serializer + `@extend_schema`
    so drf-spectacular autodocs it. Most kinds will be small scalar dicts;
    when a kind genuinely needs `?limit / ?offset / ?ordering` rails (a paginated
    leaderboard of thousands of entities), opt into `viewsets.GenericViewSet`'s
    paginator + filter_backends on a per-action basis. See
    docs/claude/reference/api-stats-pattern.md and
    docs/claude/planning/stats-list-pattern.md.

    Conventions for every action:

    - URL: `/<entity>/stats/<kind>/?project_id=X[&...]`
    - Resolve project on the first line; we use the inline 2-line pattern below
      so visibility (draft → 404) is gated explicitly. `ProjectMixin` only
      enforces project presence (`require_project=True` → 400/404 on missing
      or unknown id), not draft visibility.
    - Query params (beyond `project_id`) go through
      `SingleParamSerializer[T].clean(...)` for strict 400 validation —
      no silent clamps.
    """

    permission_classes = [IsActiveStaffOrReadOnly]
    require_project = True

    @extend_schema(
        parameters=[project_id_doc_param, limit_doc_param],
        responses=TopIdentifiersResponseSerializer,
    )
    @action(detail=False, methods=["get"], url_path="top-identifiers")
    def top_identifiers(self, request):
        """Users ranked by distinct occurrences they identified.

        `top_identifiers_for_project` bakes in `identification_count >= 1` —
        non-configurable, so an empty / anonymous call can't leak the full
        project user list.
        """
        project = self.get_active_project()
        assert project is not None  # require_project=True guarantees this
        if not Project.objects.visible_for_user(request.user).filter(pk=project.pk).exists():
            raise NotFound("Project not found.")

        limit = SingleParamSerializer[int].clean(
            param_name="limit",
            field=serializers.IntegerField(required=False, min_value=1, max_value=50, default=5),
            data=request.query_params,
        )
        top_users = list(top_identifiers_for_project(project)[:limit])
        serializer = TopIdentifiersResponseSerializer(
            {"project_id": project.pk, "top_identifiers": top_users},
            context={"request": request},
        )
        return Response(serializer.data)


class TaxonTaxaListFilter(filters.BaseFilterBackend):
    """
    Filters taxa based on a TaxaList.

    By default, queries for taxa that are directly in the TaxaList and their descendants.
    If include_descendants=false, only taxa directly in the TaxaList are returned.

    Query parameters:
    - taxa_list_id: ID of the taxa list to filter by
    - include_descendants: Set to 'false' to exclude descendants (default: true)
    - not_taxa_list_id: ID of taxa list to exclude
    """

    query_param = "taxa_list_id"
    query_param_exclusive = f"not_{query_param}"

    def filter_queryset(self, request, queryset, view):
        taxalist_id = IntegerField(required=False).clean(request.query_params.get(self.query_param))
        taxalist_id_exclusive = IntegerField(required=False).clean(
            request.query_params.get(self.query_param_exclusive)
        )

        include_descendants_default = True
        include_descendants = request.query_params.get("include_descendants", include_descendants_default)
        if include_descendants is not None:
            include_descendants = BooleanField(required=False).clean(include_descendants)

        def _get_filter(taxa_list: TaxaList) -> models.Q:
            taxa = taxa_list.taxa.all()  # Get taxa in the taxa list
            query_filter = Q(id__in=taxa)

            # Only include descendants if explicitly requested
            if include_descendants:
                for taxon in taxa:
                    query_filter |= Q(parents_json__contains=[{"id": taxon.pk}])

            return query_filter

        if taxalist_id:
            taxa_list = TaxaList.objects.filter(id=taxalist_id).first()
            if taxa_list:
                query_filter = _get_filter(taxa_list)
                queryset = queryset.filter(query_filter)

        if taxalist_id_exclusive:
            taxa_list = TaxaList.objects.filter(id=taxalist_id_exclusive).first()
            if taxa_list:
                query_filter = _get_filter(taxa_list)
                queryset = queryset.exclude(query_filter)

        return queryset


TaxonBestScoreFilter = ThresholdFilter.create("best_determination_score")


class TaxonTagFilter(filters.BaseFilterBackend):
    """FilterBackend that allows OR-based filtering of taxa by tag ID."""

    def filter_queryset(self, request, queryset, view):
        tag_ids = request.query_params.getlist("tag_id")
        if tag_ids:
            queryset = queryset.filter(tags__id__in=tag_ids).distinct()
        return queryset


class TagInverseFilter(filters.BaseFilterBackend):
    """
    Exclude taxa that have any of the specified tag IDs using `not_tag_id`.
    Example: /api/v2/taxa/?not_tag_id=1&not_tag_id=2
    """

    def filter_queryset(self, request, queryset, view):
        not_tag_ids = request.query_params.getlist("not_tag_id")
        if not_tag_ids:
            queryset = queryset.exclude(tags__id__in=not_tag_ids)
        return queryset.distinct()


class TaxonViewSet(DefaultViewSet, ProjectMixin):
    """
    API endpoint that allows taxa to be viewed or edited.
    """

    queryset = Taxon.objects.all().defer("notes")
    serializer_class = TaxonSerializer
    filter_backends = DefaultViewSetMixin.filter_backends + [
        CustomTaxonFilter,
        TaxonCollectionFilter,
        TaxonTaxaListFilter,
        TaxonBestScoreFilter,
        TaxonTagFilter,
        TagInverseFilter,
    ]
    filterset_fields = [
        "name",
        "rank",
        "parent",
        "occurrences__event",
        "occurrences__deployment",
        "occurrences__project",
        "projects",
    ]
    ordering_fields = [
        "created_at",
        "updated_at",
        "occurrences_count",
        "verified_count",
        "last_detected",
        "best_determination_score",
        "name",
        "cover_image_url",
    ]
    search_fields = ["name", "parent__name"]

    @action(detail=False, methods=["get"], name="suggest")
    def suggest(self, request):
        """
        Return a list of taxa that match the query.
        """
        min_query_length = 2
        default_results_limit = 10
        query = CharField(required=False, min_length=0).clean(request.query_params.get("q", None))
        limit = IntegerField(required=False, min_value=0).clean(
            request.query_params.get("limit", default_results_limit)
        )

        if query and len(query) >= min_query_length:
            taxa = (
                Taxon.objects.filter(active=True)
                # .select_related("parent")
                .filter(models.Q(name__icontains=query) | models.Q(search_names__icontains=query))
                .annotate(
                    # Calculate similarity for the name field
                    name_similarity=TrigramSimilarity("name", query),
                    # Cast array to string before similarity calculation
                    search_names_similarity=TrigramSimilarity(
                        models.functions.Cast("search_names", models.TextField()), query
                    ),
                    # Take the maximum similarity between name and search_names
                    similarity=models.functions.Greatest(
                        models.F("name_similarity"), models.F("search_names_similarity")
                    ),
                )
                .order_by("-similarity")[:default_results_limit]
                .defer(
                    "notes",
                    "parent__notes",
                )[:limit]
            )

            return Response(TaxonSearchResultSerializer(taxa, many=True, context={"request": request}).data)
        else:
            return Response([])

    def get_serializer_class(self):
        """
        Return different serializers for list and detail views.
        """
        if self.action == "list":
            return TaxonListSerializer
        else:
            return TaxonSerializer

    def get_occurrence_filters(self, project: Project, accessor: str = "") -> models.Q:
        """
        Filter by when/where a taxon has occurred.

        Supports querying by occurrence, project, deployment, or event.

        ``accessor`` is the relation path to the Occurrence model. Pass "" to filter the
        Occurrence model directly, or "occurrences" to filter the Taxon model via its
        reverse relation (for conditional aggregation in annotate_taxon_counts).

        @TODO Consider using a custom filter class for this (see get_filter_name)
        @TODO Move this to a custom QuerySet manager on the Taxon model
        """

        occurrence_id = self.request.query_params.get("occurrence")
        deployment_id = self.request.query_params.get("deployment") or self.request.query_params.get(
            "occurrences__deployment"
        )
        event_id = self.request.query_params.get("event") or self.request.query_params.get("occurrences__event")
        collection_id = self.request.query_params.get("collection")

        prefix = f"{accessor}__" if accessor else ""

        def field(path: str) -> str:
            return f"{prefix}{path}"

        filters = models.Q(**{field("project"): project, field("event__isnull"): False})
        try:
            """
            Ensure that the related objects exist before filtering by them.
            This may be overkill!
            """
            if occurrence_id:
                Occurrence.objects.get(id=occurrence_id)
                # This query does not need the same filtering as the others
                filters &= models.Q(**{field("id"): occurrence_id})
            if deployment_id:
                Deployment.objects.get(id=deployment_id)
                filters &= models.Q(**{field("deployment"): deployment_id})
            if event_id:
                Event.objects.get(id=event_id)
                filters &= models.Q(**{field("event"): event_id})
            if collection_id:
                SourceImageCollection.objects.get(id=collection_id)
                filters &= models.Q(**{field("detections__source_image__collections"): collection_id})
        except exceptions.ObjectDoesNotExist as e:
            # Raise a 404 if any of the related objects don't exist
            raise NotFound(detail=str(e))

        return filters

    def get_queryset(self) -> QuerySet:
        """
        If a project is passed, only return taxa that have been observed
        and add extra data about the occurrences.
        Otherwise return all taxa that are active.
        """
        qs = super().get_queryset()
        project = self.get_active_project()
        if project:
            qs = self.attach_tags_by_project(qs, project)

        if project:
            # Allow showing detail views for unobserved taxa
            include_unobserved = True
            if self.action == "list":
                include_unobserved = self.request.query_params.get("include_unobserved", False)
                # Apply default taxa filtering (respects apply_defaults flag)
                qs = qs.filter_by_project_default_taxa(project, self.request)  # type: ignore
                qs = self.get_taxa_observed(qs, project, include_unobserved=include_unobserved)
            if self.action == "retrieve":
                qs = self.get_taxa_observed(
                    qs,
                    project,
                    include_unobserved=include_unobserved,
                    apply_default_score_filter=True,
                    apply_default_taxa_filter=False,
                )
                qs = qs.prefetch_related(
                    Prefetch(
                        "occurrences",
                        queryset=Occurrence.objects.filter(self.get_occurrence_filters(project))[:1],
                        to_attr="example_occurrences",
                    )
                )
        else:
            # Add empty occurrences list to make the response consistent
            qs = qs.annotate(example_occurrences=models.Value([], output_field=models.JSONField()))
            # Set count to null to make it clear that it's not the total count
            qs = qs.annotate(occurrences_count=models.Value(None, output_field=models.IntegerField()))
            qs = qs.annotate(events_count=models.Value(None, output_field=models.IntegerField()))
        return qs

    def get_taxa_observed(
        self,
        qs: QuerySet,
        project: Project,
        include_unobserved=False,
        apply_default_score_filter=True,
        apply_default_taxa_filter=True,
    ) -> QuerySet:
        """
        If a project is passed, only return taxa that have been observed.
        Also add the number of occurrences and the last time it was detected.

        Counts are computed by annotate_taxon_counts from one filtered occurrence set
        (occurrence_filters + the project's default filters), not per-taxon subqueries.
        """
        return self.annotate_taxon_counts(
            qs,
            project,
            apply_default_score_filter=apply_default_score_filter,
            apply_default_taxa_filter=apply_default_taxa_filter,
            restrict_to_observed=not include_unobserved,
        )

    def _include_agreement(self) -> bool:
        """Whether the heavier ``agreed_exact_count`` annotation should be computed."""
        if self.action == "retrieve":
            return True
        return bool(BooleanField(required=False).clean(self.request.query_params.get("with_agreement")))

    @staticmethod
    def _case_from_map(mapping: dict, default, output_field: models.Field) -> models.expressions.Combinable:
        """Turn a precomputed ``{taxon_id: value}`` map into a constant-time ``CASE``.

        The result is constant per row, so it is DB-sortable, paginatable, and stripped
        from the pagination ``COUNT`` — unlike a per-taxon correlated subquery, which is
        re-evaluated for every row and (in ``COUNT``) for every taxon in the project.
        """
        if not mapping:
            return models.Value(default, output_field=output_field)
        return models.Case(
            *(
                models.When(id=taxon_id, then=models.Value(value, output_field=output_field))
                for taxon_id, value in mapping.items()
            ),
            default=models.Value(default, output_field=output_field),
            output_field=output_field,
        )

    def annotate_taxon_counts(
        self,
        qs: QuerySet,
        project: Project,
        *,
        apply_default_score_filter: bool = True,
        apply_default_taxa_filter: bool = True,
        restrict_to_observed: bool,
    ) -> QuerySet:
        """Centralised per-(project, taxon) count annotations for the taxa endpoint.

        Every count comes from the same filtered occurrence set (the project's
        occurrence_filters + default filters); nothing here uses a per-taxon correlated
        subquery, which does not scale once the filters join detections
        (``?collection=<id>``): each annotation degrades to a per-row scan — 25x on the
        page, and once per taxon in the unbounded pagination ``COUNT``.

        Two count shapes, two mechanisms:

        - Direct aggregates (``occurrences_count``, ``best_determination_score``,
          ``last_detected``) are dense — one value per observed taxon — so they use
          conditional aggregation over the Taxon→occurrences reverse relation (one GROUP
          BY, constant-size SQL). ``Count(distinct)`` dedupes the detections-join fan-out
          under ``?collection=``; ``restrict_to_observed`` is then a HAVING on the count.
        - ``verified_count`` / ``agreed_*`` are sparse (only *verified* occurrences) and
          roll up to ancestors via ``parents_json``, so they are precomputed in Python and
          applied as ``CASE`` annotations — see :meth:`_annotate_verification_counts`. A
          dense map would not work there: one ``CASE`` branch per taxon blows past the SQL
          token limit on large projects.
        """
        from ami.main.models_future.filters import build_occurrence_default_filters_q

        # Filters expressed through the Taxon→occurrences reverse relation, for conditional
        # aggregation on the main query. The default *taxa* include/exclude filter is
        # deliberately omitted here: occurrences_count groups by determination = the taxon
        # row itself, so the per-occurrence taxa filter is redundant with the row already
        # being kept/dropped by filter_by_project_default_taxa (applied to the queryset for
        # list responses). Including it would add a parents_json containment join inside the
        # aggregate that the planner cannot reconcile with the detections (?collection=)
        # join — turning the page into a multi-minute scan. The score threshold is per
        # occurrence, so it is kept.
        count_filter = self.get_occurrence_filters(
            project, accessor="occurrences"
        ) & build_occurrence_default_filters_q(
            project,
            self.request,
            occurrence_accessor="occurrences",
            apply_default_score_filter=apply_default_score_filter,
            apply_default_taxa_filter=False,
        )
        qs = qs.annotate(
            occurrences_count=models.Count("occurrences", filter=count_filter, distinct=True),
            best_determination_score=models.Max("occurrences__determination_score", filter=count_filter),
            last_detected=models.Max("occurrences__detections__timestamp", filter=count_filter),
        )
        if restrict_to_observed:
            qs = qs.filter(occurrences_count__gt=0)

        # The verification rollup queries the Occurrence model directly (so no relation
        # prefix), and rolls up to ancestors via parents_json, so it does need the full
        # default filters. Its driving set is sparse (verified occurrences only), so the
        # taxa containment join here is cheap.
        base = Occurrence.objects.filter(self.get_occurrence_filters(project)).filter(
            build_occurrence_default_filters_q(
                project,
                self.request,
                occurrence_accessor="",
                apply_default_score_filter=apply_default_score_filter,
                apply_default_taxa_filter=apply_default_taxa_filter,
            )
        )
        return self._annotate_verification_counts(qs, base)

    def _annotate_verification_counts(self, qs: QuerySet, base: QuerySet) -> QuerySet:
        """
        Annotate per-taxon verification / human-model agreement counts, and apply the
        ``verified=true|false`` filter on list responses.

        ``base`` is the shared filtered occurrence set from :meth:`annotate_taxon_counts`.
        Counts roll up descendant occurrences (verifying a species also counts toward its
        genus/family rows). They only concern *verified* occurrences (those with a
        non-withdrawn Identification), which are sparse, so the hierarchical rollup is a
        single Python pass over that small subset applied as constant-time ``CASE``
        annotations. A correlated ``parents_json`` subquery per taxon does not scale: the
        GIN index can't serve a containment whose RHS is an ``OuterRef``.
        """
        include_agreement = self._include_agreement()

        # The chosen (best, non-withdrawn) identification's agreed_with_prediction FK.
        best_identification_agreed_prediction = models.Subquery(
            Identification.objects.filter(occurrence=models.OuterRef("pk"), withdrawn=False)
            .order_by(*BEST_IDENTIFICATION_ORDER)
            .values("agreed_with_prediction_id")[:1]
        )
        verified_occurrences = base.filter(
            models.Exists(Identification.objects.filter(occurrence=models.OuterRef("pk"), withdrawn=False))
        ).annotate(_agreed_prediction_id=best_identification_agreed_prediction)
        # ``pk`` is selected only so ``.distinct()`` below dedupes by occurrence: when
        # occurrence_filters joins to detections (e.g. ?collection=<id>), one Occurrence
        # yields a row per matching Detection, which would otherwise inflate the counts.
        value_fields = ["pk", "determination_id", "determination__parents_json", "_agreed_prediction_id"]
        if include_agreement:
            # Top machine prediction's taxon for the same occurrence.
            verified_occurrences = verified_occurrences.annotate(
                _best_machine_taxon_id=models.Subquery(
                    Classification.objects.filter(detection__occurrence=models.OuterRef("pk"))
                    .order_by(*BEST_MACHINE_PREDICTION_ORDER)
                    .values("taxon_id")[:1]
                )
            )
            value_fields.append("_best_machine_taxon_id")

        verified_counts: dict[int, int] = {}
        agreed_with_prediction_counts: dict[int, int] = {}
        agreed_exact_counts: dict[int, int] = {}
        for row in verified_occurrences.values(*value_fields).distinct():
            determination_id = row["determination_id"]
            # The taxon itself plus every ancestor — i.e. every row this occurrence rolls up to.
            taxon_ids: set[int] = set()
            if determination_id is not None:
                taxon_ids.add(determination_id)
            for parent in row["determination__parents_json"] or []:
                # parents_json round-trips through the pydantic schema field, so elements
                # may be dicts or ``TaxonParent`` objects depending on the query path.
                parent_id = parent.get("id") if isinstance(parent, dict) else getattr(parent, "id", None)
                if parent_id is not None:
                    taxon_ids.add(int(parent_id))

            for taxon_id in taxon_ids:
                verified_counts[taxon_id] = verified_counts.get(taxon_id, 0) + 1
            if row["_agreed_prediction_id"] is not None:
                for taxon_id in taxon_ids:
                    agreed_with_prediction_counts[taxon_id] = agreed_with_prediction_counts.get(taxon_id, 0) + 1
            if (
                include_agreement
                and determination_id is not None
                and determination_id == row["_best_machine_taxon_id"]
            ):
                for taxon_id in taxon_ids:
                    agreed_exact_counts[taxon_id] = agreed_exact_counts.get(taxon_id, 0) + 1

        int_field = models.IntegerField()
        qs = qs.annotate(
            verified_count=self._case_from_map(verified_counts, 0, int_field),
            agreed_with_prediction_count=self._case_from_map(agreed_with_prediction_counts, 0, int_field),
        )
        if include_agreement:
            qs = qs.annotate(agreed_exact_count=self._case_from_map(agreed_exact_counts, 0, int_field))

        # verified=true|false filter (list only); verified=false is the strict complement.
        if self.action == "list" and "verified" in self.request.query_params:
            verified = BooleanField(required=False).clean(self.request.query_params.get("verified"))
            verified_taxon_ids = list(verified_counts.keys())
            if verified:
                qs = qs.filter(id__in=verified_taxon_ids)
            else:
                qs = qs.exclude(id__in=verified_taxon_ids)

        return qs

    def attach_tags_by_project(self, qs: QuerySet, project: Project) -> QuerySet:
        """
        Prefetch and override the `.tags` attribute on each Taxon
        with only the tags belonging to the given project.
        """
        # Include all tags if no project is passed
        if project is None:
            tag_qs = Tag.objects.all()
        else:
            # Prefetch only the tags that belong to the project or are global
            tag_qs = Tag.objects.filter(models.Q(project=project) | models.Q(project__isnull=True))

        tag_prefetch = Prefetch("tags", queryset=tag_qs, to_attr="prefetched_tags")

        return qs.prefetch_related(tag_prefetch)

    @action(detail=True, methods=["post"])
    def assign_tags(self, request, pk=None):
        """
        Assign tags to a taxon
        """
        taxon = self.get_object()
        tag_ids = request.data.get("tag_ids")
        logger.info(f"Tag IDs: {tag_ids}")
        if not isinstance(tag_ids, list):
            return Response({"detail": "tag_ids must be a list of IDs."}, status=status.HTTP_400_BAD_REQUEST)

        tags = Tag.objects.filter(id__in=tag_ids)
        logger.info(f"Tags: {tags}, len: {len(tags)}")
        taxon.tags.set(tags)  # replaces all tags for this taxon
        taxon.save()
        logger.info(f"Tags after assingment : {len(taxon.tags.all())}")
        return Response(
            {"taxon_id": taxon.id, "assigned_tag_ids": [tag.pk for tag in tags]},
            status=status.HTTP_200_OK,
        )

    @extend_schema(parameters=[project_id_doc_param])
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)


class TaxaListViewSet(DefaultViewSet, ProjectMixin):
    queryset = TaxaList.objects.all()
    serializer_class = TaxaListSerializer
    ordering_fields = [
        "name",
        "description",
        "annotated_taxa_count",
        "created_at",
        "updated_at",
    ]
    permission_classes = [IsProjectMemberOrReadOnly]
    require_project = True

    def get_queryset(self):
        qs = super().get_queryset()
        # Annotate with taxa count for better performance
        qs = qs.annotate(annotated_taxa_count=models.Count("taxa"))
        project = self.get_active_project()
        if project:
            return qs.filter(projects=project)
        return qs

    def perform_create(self, serializer):
        """
        Create a TaxaList and automatically assign it to the active project.

        Users cannot manually assign taxa lists to projects for security reasons.
        A taxa list is always created in the context of the active project.
        """
        instance = serializer.save()
        project = self.get_active_project()
        if project:
            instance.projects.add(project)


class TaxaListTaxonViewSet(viewsets.GenericViewSet, ProjectMixin):
    """
    Nested ViewSet for managing taxa in a taxa list.
    Accessed via /taxa/lists/{taxa_list_id}/taxa/

    Only provides create (POST) and delete (DELETE) actions.
    The UI lists taxa via the main /taxa/ endpoint with a taxa_list_id filter.
    """

    serializer_class = TaxaListTaxonSerializer
    permission_classes = [IsProjectMemberOrReadOnly]
    require_project = True

    def get_taxa_list(self):
        """Get the parent taxa list from URL parameters, scoped to the active project."""
        taxa_list_id = self.kwargs.get("taxalist_pk")
        project = self.get_active_project()
        try:
            return TaxaList.objects.get(pk=taxa_list_id, projects=project)
        except TaxaList.DoesNotExist:
            raise api_exceptions.NotFound("Taxa list not found.") from None

    def get_queryset(self):
        """Return taxa in the specified taxa list."""
        taxa_list = self.get_taxa_list()
        return taxa_list.taxa.all()

    def create(self, request, taxalist_pk=None):
        """Add a taxon to the taxa list."""
        taxa_list = self.get_taxa_list()

        # Validate input
        input_serializer = TaxaListTaxonInputSerializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)
        taxon_id = input_serializer.validated_data["taxon_id"]

        # Check if already exists
        if taxa_list.taxa.filter(pk=taxon_id).exists():
            return Response(
                {"non_field_errors": ["Taxon is already in this taxa list."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Add taxon
        taxon = get_object_or_404(Taxon, pk=taxon_id)
        taxa_list.taxa.add(taxon)

        # Return the added taxon
        serializer = self.get_serializer(taxon)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["delete"], url_path=r"(?P<taxon_id>\d+)")
    def delete_by_taxon(self, request, taxalist_pk=None, taxon_id=None):
        """
        Remove a taxon from the taxa list by taxon ID.
        DELETE /taxa/lists/{taxa_list_id}/taxa/{taxon_id}/
        """
        taxa_list = self.get_taxa_list()

        # Check if taxon exists in list
        if not taxa_list.taxa.filter(pk=taxon_id).exists():
            raise api_exceptions.NotFound("Taxon is not in this taxa list.")

        # Remove taxon
        taxa_list.taxa.remove(taxon_id)
        return Response(status=status.HTTP_204_NO_CONTENT)


class TagViewSet(DefaultViewSet, ProjectMixin):
    queryset = Tag.objects.all()
    serializer_class = TagSerializer
    filterset_fields = ["taxa"]

    def get_queryset(self):
        qs = super().get_queryset()
        project = self.get_active_project()
        if project:
            # Filter by project, but also include global tags
            return qs.filter(models.Q(project=project) | models.Q(project__isnull=True))
        return qs


class ClassificationViewSet(DefaultViewSet, ProjectMixin):
    """
    API endpoint for viewing and adding classification results from a model.
    """

    require_project_for_list = True  # Unfiltered list scans are too expensive on this table
    queryset = Classification.objects.all().select_related("taxon", "algorithm")  # , "detection")
    serializer_class = ClassificationSerializer
    filterset_fields = [
        # Docs about slow loading API browser because of large choice fields
        # https://www.django-rest-framework.org/topics/browsable-api/#handling-choicefield-with-large-numbers-of-items
        "taxon",
        "algorithm",
        "detection__source_image__project",
        "detection__source_image__collections",
    ]
    ordering_fields = [
        "created_at",
        "updated_at",
        "score",
    ]

    def get_queryset(self) -> QuerySet:
        qs = super().get_queryset()
        project = self.get_active_project()
        if project:
            qs = qs.filter(detection__source_image__project=project)
        return qs

    def get_serializer_class(self):
        """
        Return a different serializer for list and detail views.
        If "with_taxa" is in the query params, return a different serializer.
        """
        if self.action == "list":
            return ClassificationListSerializer
        elif "with_taxa" in self.request.query_params:
            return ClassificationWithTaxaSerializer
        else:
            return ClassificationSerializer


class SummaryView(GenericAPIView, ProjectMixin):
    permission_classes = [IsActiveStaffOrReadOnly]
    require_project = True  # Unfiltered summary aggregates are too expensive

    @extend_schema(parameters=[project_id_doc_param])
    def get(self, request):
        """
        Return counts of all models, applying visibility filters for draft projects.
        """
        user = request.user
        project = self.get_active_project()
        data = {
            "projects_count": Project.objects.visible_for_user(  # type: ignore
                user
            ).count(),  # @TODO filter by current user, here and everywhere!
            "deployments_count": Deployment.objects.visible_for_user(user)  # type: ignore
            .filter(project=project)
            .count(),
            "events_count": Event.objects.visible_for_user(user)  # type: ignore
            .filter(deployment__project=project, deployment__isnull=False)
            .count(),
            "captures_count": SourceImage.objects.visible_for_user(user)  # type: ignore
            .filter(deployment__project=project)
            .count(),
            # "detections_count": Detection.objects.filter(occurrence__project=project).count(),
            "occurrences_count": Occurrence.objects.visible_for_user(user)  # type: ignore
            .apply_default_filters(project=project, request=self.request)  # type: ignore
            .valid()
            .filter(project=project)
            .count(),  # type: ignore
            "taxa_count": Occurrence.objects.visible_for_user(user)  # type: ignore
            .apply_default_filters(project=project, request=self.request)  # type: ignore
            .unique_taxa(project=project)
            .count(),
        }

        aliases = {
            "num_sessions": data["events_count"],
            "num_species": data["taxa_count"],
        }

        # add an num_ alias for each _count key
        for key, value in data.items():
            if key.endswith("_count"):
                aliases["num_" + key.replace("_count", "")] = value

        data.update(aliases)

        return Response(data)


_STORAGE_CONNECTION_STATUS = [
    # These come from the ConnetionStatus react component
    # @TODO use ENUM
    "NOT_CONNECTED",
    "CONNECTING",
    "CONNECTED",
    "ERROR",
]


class StorageStatus(APIView):
    """
    Return the status of the storage connection.
    """

    permission_classes = [IsActiveStaffOrReadOnly]
    serializer_class = StorageStatusSerializer

    def post(self, request):
        """@TODO not totally sure how to use the serializer here yet."""
        data_source = request.data.get("data_source")
        example_image_urls = [img.url() for img in SourceImage.objects.order_by("?")[:10]]
        data = {
            "data_source": data_source,
            "status": _STORAGE_CONNECTION_STATUS[1],
            "updated_at": timezone.now(),
            "example_captures": example_image_urls,
        }

        return Response(data)


class PageViewSet(DefaultViewSet):
    """
    API endpoint that allows pages to be viewed or edited.
    """

    queryset = Page.objects.all()
    serializer_class = PageSerializer
    lookup_field = "slug"
    filterset_fields = ["project", "nav_level", "link_class", "published"]
    ordering_fields = [
        "nav_level",
        "nav_order",
        "created_at",
        "updated_at",
    ]

    def get_serializer_class(self):
        """
        Return different serializers for list and detail views.
        """
        if self.action == "list":
            return PageListSerializer
        else:
            return PageSerializer


class IdentificationViewSet(DefaultViewSet):
    """
    API endpoint that allows identifications to be viewed or edited.
    """

    queryset = Identification.objects.all()
    serializer_class = IdentificationSerializer
    filterset_fields = [
        "occurrence",
        "user",
        "taxon",
    ]
    ordering_fields = [
        "created_at",
        "updated_at",
        "user",
    ]

    permission_classes = [ObjectPermission]

    def perform_create(self, serializer):
        """
        Set the user to the current user.
        """
        # Get an instance for the model without saving
        obj = serializer.Meta.model(**serializer.validated_data, user=self.request.user)  # type: ignore

        # Check permissions before saving
        self.check_object_permissions(self.request, obj)

        serializer.save(user=self.request.user)


class SiteViewSet(DefaultViewSet, ProjectMixin):
    """
    API endpoint that allows sites to be viewed or edited.
    """

    queryset = Site.objects.all()
    serializer_class = SiteSerializer
    filterset_fields = ["deployments"]
    ordering_fields = [
        "created_at",
        "updated_at",
        "name",
    ]
    permission_classes = [ObjectPermission]

    def get_queryset(self) -> QuerySet:
        query_set: QuerySet = super().get_queryset()
        project = self.get_active_project()
        if project:
            query_set = query_set.filter(project=project)
        return query_set

    @extend_schema(parameters=[project_id_doc_param])
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)


class DeviceViewSet(DefaultViewSet, ProjectMixin):
    """
    API endpoint that allows devices to be viewed or edited.
    """

    queryset = Device.objects.all()
    serializer_class = DeviceSerializer
    filterset_fields = ["deployments"]
    ordering_fields = [
        "created_at",
        "updated_at",
        "name",
    ]
    permission_classes = [ObjectPermission]

    def get_queryset(self) -> QuerySet:
        query_set: QuerySet = super().get_queryset()
        project = self.get_active_project()
        if project:
            query_set = query_set.filter(project=project)
        return query_set

    @extend_schema(parameters=[project_id_doc_param])
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)


class StorageSourceConnectionTestSerializer(serializers.Serializer):
    subdir = serializers.CharField(required=False, allow_null=True)
    regex_filter = serializers.CharField(required=False, allow_null=True)


class StorageSourceViewSet(DefaultViewSet, ProjectMixin):
    """
    API endpoint that allows storage sources to be viewed or edited.
    """

    queryset = S3StorageSource.objects.all()
    serializer_class = StorageSourceSerializer
    filterset_fields = ["deployments"]
    ordering_fields = [
        "created_at",
        "updated_at",
        "name",
    ]
    permission_classes = [ObjectPermission]

    def get_queryset(self) -> QuerySet:
        query_set: QuerySet = super().get_queryset()
        project = self.get_active_project()
        if project:
            query_set = query_set.filter(project=project)
        return query_set

    @action(detail=True, methods=["post"], name="test", serializer_class=StorageSourceConnectionTestSerializer)
    def test(self, request: Request, pk=None) -> Response:
        """
        Test the connection to the storage source.
        """
        storage_source: S3StorageSource = self.get_object()
        if not storage_source:
            return Response({"detail": "Storage source not found"}, status=status.HTTP_404_NOT_FOUND)

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        result: ConnectionTestResult = storage_source.test_connection(
            subdir=serializer.validated_data.get("subdir"),
            regex_filter=serializer.validated_data.get("regex_filter"),
        )
        if result.connection_successful:
            return Response(
                status=200,
                data=result.__dict__,  # @TODO Consider using a serializer and annotating this for the OpenAPI schema
            )
        else:
            return Response(
                status=status.HTTP_400_BAD_REQUEST,
                data={
                    "detail": result.error_message,
                    "code": result.error_code,
                },
            )

    @extend_schema(parameters=[project_id_doc_param])
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)
