import datetime
import logging
from statistics import mode

from django.contrib.postgres.search import TrigramSimilarity
from django.core import exceptions
from django.db import models
from django.db.models import Prefetch, Q
from django.db.models.functions import Coalesce
from django.db.models.query import QuerySet
from django.forms import BooleanField, CharField, IntegerField
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
from ami.base.permissions import IsActiveStaffOrReadOnly, ObjectPermission
from ami.base.serializers import FilterParamsSerializer, SingleParamSerializer
from ami.base.views import ProjectMixin
from ami.main.api.schemas import project_id_doc_param
from ami.main.api.serializers import TagSerializer
from ami.utils.requests import get_default_classification_threshold
from ami.utils.storages import ConnectionTestResult

from ..models import (
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
    TaxonListSerializer,
    TaxonSearchResultSerializer,
    TaxonSerializer,
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


class ProjectViewSet(DefaultViewSet, ProjectMixin):
    """
    API endpoint that allows projects to be viewed or edited.
    """

    queryset = Project.objects.filter(active=True).prefetch_related("deployments").all()
    serializer_class = ProjectSerializer
    pagination_class = ProjectPagination
    permission_classes = [ObjectPermission]

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

        qs = SourceImage.objects.filter(event=event)

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
            .values("id", "timestamp", "detections_count")
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
            Detection.objects.all()
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
        Add a source image to the project's starred images collection.
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
        Remove a source image from the project's starred images collection.
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
    Endpoint for viewing collections or samples of source images.
    """

    queryset = (
        SourceImageCollection.objects.all()
        .with_source_images_count()  # type: ignore
        .with_source_images_with_detections_count()
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
        Populate a collection with source images using the configured sampling method and arguments.
        """
        collection: SourceImageCollection = self.get_object()

        if collection:
            from ami.jobs.models import Job, SourceImageCollectionPopulateJob

            assert collection.project, "Collection must be associated with a project"
            job = Job.objects.create(
                name=f"Populate captures for collection {collection.pk}",
                project=collection.project,
                source_image_collection=collection,
                job_type_key=SourceImageCollectionPopulateJob.key,
            )
            job.enqueue()
            msg = f"Populating captures for collection {collection.pk} in background."
            logger.info(msg)
            return Response({"job_id": job.pk, "project_id": collection.project.pk})
        else:
            raise api_exceptions.ValidationError(detail="Invalid collection requested")

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
        Add a source image to a collection.
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
        Remove a source image from a collection.
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

    queryset = Detection.objects.all().select_related("source_image", "detection_algorithm")
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
        return super().list(request, *args, **kwargs)

    # def get_queryset(self):
    #     """
    #     Return a different queryset for list and detail views.
    #     """

    #     if self.action == "list":
    #         return Detection.objects.select_related().all()
    #     else:
    #         return Detection.objects.select_related(
    #             "detection_algorithm").all()


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
            # Here the queryset is the Occurrence queryset
            return queryset.filter(
                models.Q(determination=taxon) | models.Q(determination__parents_json__contains=[{"id": taxon.pk}])
            )
        else:
            return queryset


class OccurrenceCollectionFilter(filters.BaseFilterBackend):
    """
    Filter occurrences by the collection their detections source images belong to.
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
    Filter taxa by the collection their occurrences belong to.
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
        if self.action != "list":
            qs = qs.prefetch_related(
                Prefetch(
                    "detections", queryset=Detection.objects.order_by("-timestamp").select_related("source_image")
                )
            )

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
                description="Filter occurrences by the collection their detections' source images belong to.",
                required=False,
                type=OpenApiTypes.INT,
            ),
        ]
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)


class TaxonTaxaListFilter(filters.BaseFilterBackend):
    """
    Filters taxa based on a TaxaList Similar to `OccurrenceTaxaListFilter`.

    Queries for all taxa that are either:
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

        def _get_filter(taxa_list: TaxaList) -> models.Q:
            taxa = taxa_list.taxa.all()  # Get taxa in the taxa list
            query_filter = Q(id__in=taxa)
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

    def get_occurrence_filters(self, project: Project) -> models.Q:
        """
        Filter taxa by when/where it has occurred.

        Supports querying by occurrence, project, deployment, or event.

        @TODO Consider using a custom filter class for this (see get_filter_name)
        @TODO Move this to a custom QuerySet manager on the Taxon model
        """

        occurrence_id = self.request.query_params.get("occurrence")
        deployment_id = self.request.query_params.get("deployment") or self.request.query_params.get(
            "occurrences__deployment"
        )
        event_id = self.request.query_params.get("event") or self.request.query_params.get("occurrences__event")
        collection_id = self.request.query_params.get("collection")

        # filter_active = any([occurrence_id, project, deployment_id, event_id, collection_id])

        filters = models.Q(
            project=project,
            event__isnull=False,
        )
        try:
            """
            Ensure that the related objects exist before filtering by them.
            This may be overkill!
            """
            if occurrence_id:
                Occurrence.objects.get(id=occurrence_id)
                # This query does not need the same filtering as the others
                filters &= models.Q(id=occurrence_id)
            if deployment_id:
                Deployment.objects.get(id=deployment_id)
                filters &= models.Q(deployment=deployment_id)
            if event_id:
                Event.objects.get(id=event_id)
                filters &= models.Q(event=event_id)
            if collection_id:
                SourceImageCollection.objects.get(id=collection_id)
                filters &= models.Q(detections__source_image__collections=collection_id)
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
                    qs, project, include_unobserved=include_unobserved, apply_default_filters=False
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
        self, qs: QuerySet, project: Project, include_unobserved=False, apply_default_filters=True
    ) -> QuerySet:
        """
        If a project is passed, only return taxa that have been observed.
        Also add the number of occurrences and the last time it was detected.

        Uses efficient subqueries with default filters applied directly via Q objects
        to leverage composite indexes on (determination_id, project_id, event_id, determination_score).
        This avoids the N+1 query problem by building a single Q filter that can be reused
        across all subqueries.
        """
        occurrence_filters = self.get_occurrence_filters(project)

        # Build a single Q filter for default filters (score threshold + taxa filters)
        # This creates an efficient filter that works with composite indexes
        # Respects apply_defaults flag: build_occurrence_default_filters_q checks it internally
        from ami.main.models_future.filters import build_occurrence_default_filters_q

        default_filters_q = build_occurrence_default_filters_q(project, self.request, occurrence_accessor="")

        # Combine base occurrence filters with default filters
        base_filter = models.Q(
            occurrence_filters,
            determination_id=models.OuterRef("id"),
        )
        if apply_default_filters:
            base_filter = base_filter & default_filters_q

        # Count occurrences - uses composite index (determination_id, project_id, event_id, determination_score)
        occurrences_count_subquery = models.Subquery(
            Occurrence.objects.filter(base_filter)
            .values("determination_id")
            .annotate(count=models.Count("id"))
            .values("count")[:1],
            output_field=models.IntegerField(),
        )

        # Get best score - uses same composite index
        best_score_subquery = models.Subquery(
            Occurrence.objects.filter(base_filter)
            .values("determination_id")
            .annotate(max_score=models.Max("determination_score"))
            .values("max_score")[:1],
            output_field=models.FloatField(),
        )

        # Get last detected timestamp - requires join with detections
        last_detected_subquery = models.Subquery(
            Occurrence.objects.filter(
                base_filter,
                detections__timestamp__isnull=False,
            )
            .values("determination_id")
            .annotate(last_detected=models.Max("detections__timestamp"))
            .values("last_detected")[:1],
            output_field=models.DateTimeField(),
        )

        # Apply annotations
        qs = qs.annotate(
            occurrences_count=Coalesce(occurrences_count_subquery, 0),
            best_determination_score=best_score_subquery,
            last_detected=last_detected_subquery,
        )

        if not include_unobserved:
            # Efficient EXISTS check that uses the composite index
            qs = qs.filter(models.Exists(Occurrence.objects.filter(base_filter)))

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


class TaxaListViewSet(viewsets.ModelViewSet, ProjectMixin):
    queryset = TaxaList.objects.all()

    def get_queryset(self):
        qs = super().get_queryset()
        project = self.get_active_project()
        if project:
            return qs.filter(projects=project)
        return qs

    serializer_class = TaxaListSerializer


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

    @extend_schema(parameters=[project_id_doc_param])
    def get(self, request):
        """
        Return counts of all models, applying visibility filters for draft projects.
        """
        user = request.user
        project = self.get_active_project()
        if project:
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
        else:
            data = {
                "projects_count": Project.objects.visible_for_user(user).count(),  # type: ignore
                "deployments_count": Deployment.objects.visible_for_user(user).count(),  # type: ignore
                "events_count": Event.objects.visible_for_user(user)  # type: ignore
                .filter(deployment__isnull=False)
                .count(),
                "captures_count": SourceImage.objects.visible_for_user(user).count(),  # type: ignore
                "occurrences_count": Occurrence.objects.valid().visible_for_user(user).count(),  # type: ignore
                "taxa_count": Occurrence.objects.visible_for_user(user).unique_taxa().count(),  # type: ignore
                "last_updated": timezone.now(),
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
