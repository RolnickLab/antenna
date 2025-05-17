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
from ami.base.pagination import LimitOffsetPaginationWithPermissions
from ami.base.permissions import (
    CanDeleteIdentification,
    CanPopulateSourceImageCollection,
    CanStarSourceImage,
    CanUpdateIdentification,
    DeploymentCRUDPermission,
    DeviceCRUDPermission,
    IsActiveStaffOrReadOnly,
    ProjectCRUDPermission,
    S3StorageSourceCRUDPermission,
    SiteCRUDPermission,
    SourceImageCollectionCRUDPermission,
    SourceImageCRUDPermission,
    SourceImageUploadCRUDPermission,
)
from ami.base.serializers import FilterParamsSerializer, SingleParamSerializer
from ami.base.views import ProjectMixin
from ami.jobs.models import DetectionClusteringJob, Job
from ami.main.api.serializers import ClusterDetectionsSerializer, TagSerializer
from ami.utils.requests import get_active_classification_threshold, project_id_doc_param
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
    ClassificationSimilaritySerializer,
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
    permission_classes = [ProjectCRUDPermission]

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

    def perform_create(self, serializer):
        super().perform_create(serializer)
        # Check if user is authenticated
        if not self.request.user or not self.request.user.is_authenticated:
            raise PermissionDenied("You must be authenticated to create a project.")

        # Add current user as project owner
        serializer.save(owner=self.request.user)

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
        "first_date",
        "last_date",
    ]

    permission_classes = [DeploymentCRUDPermission]

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

            qs = qs.annotate(
                taxa_count=models.Count(
                    "occurrences__determination",
                    distinct=True,
                    filter=models.Q(
                        occurrences__determination_score__gte=get_active_classification_threshold(self.request),
                    ),
                ),
            )

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
        "detections_count",
        "occurrences_count",
        "taxa_count",
        "deployment__name",
        "event__start",
    ]
    permission_classes = [CanStarSourceImage, SourceImageCRUDPermission]

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

        classification_threshold = get_active_classification_threshold(self.request)
        queryset = queryset.with_occurrences_count(  # type: ignore
            classification_threshold=classification_threshold
        ).with_taxa_count(  # type: ignore
            classification_threshold=classification_threshold
        )

        queryset.select_related(
            "event",
            "deployment",
            "deployment__storage",
        ).order_by("timestamp")

        if self.action == "list":
            # It's cumbersome to override the default list view, so customize the queryset here
            queryset = self.filter_by_has_detections(queryset)

        elif self.action == "retrieve":
            queryset = queryset.prefetch_related("jobs", "collections")
            queryset = self.add_adjacent_captures(queryset)
            with_detections_default = True

        with_detections = self.request.query_params.get("with_detections", with_detections_default)
        if with_detections is not None:
            # Convert string to boolean
            with_detections = BooleanField(required=False).clean(with_detections)

        if with_detections:
            queryset = self.prefetch_detections(queryset)

        return queryset

    def filter_by_has_detections(self, queryset: QuerySet) -> QuerySet:
        has_detections = self.request.query_params.get("has_detections")
        if has_detections is not None:
            has_detections = BooleanField(required=False).clean(has_detections)
            queryset = queryset.annotate(
                has_detections=models.Exists(Detection.objects.filter(source_image=models.OuterRef("pk"))),
            ).filter(has_detections=has_detections)
        return queryset

    def prefetch_detections(self, queryset: QuerySet) -> QuerySet:
        # Return all detections for source images, let frontend filter them
        prefetch_queryset = Detection.objects.all()

        related_detections = Prefetch(
            "detections",
            queryset=prefetch_queryset.select_related(
                "occurrence",
                "occurrence__determination",
            ).annotate(determination_score=models.Max("occurrence__detections__classifications__score")),
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
        CanPopulateSourceImageCollection,
        SourceImageCollectionCRUDPermission,
    ]
    filterset_fields = ["method"]
    ordering_fields = [
        "created_at",
        "updated_at",
        "name",
        "method",
        "source_images_count",
        "source_images_with_detections_count",
        "occurrences_count",
    ]

    def get_queryset(self) -> QuerySet:
        classification_threshold = get_active_classification_threshold(self.request)
        query_set: QuerySet = super().get_queryset()
        project = self.get_active_project()
        if project:
            query_set = query_set.filter(project=project)
        queryset = query_set.with_occurrences_count(  # type: ignore
            classification_threshold=classification_threshold
        ).with_taxa_count(  # type: ignore
            classification_threshold=classification_threshold
        )
        return queryset

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

    @action(detail=True, methods=["post"], name="cluster detections")
    def cluster_detections(self, request, pk=None):
        """
        Trigger a background job to cluster detections from this collection.
        """

        collection: SourceImageCollection = self.get_object()
        serializer = ClusterDetectionsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        params = serializer.validated_data
        job = Job.objects.create(
            name=f"Clustering detections for collection {collection.pk}",
            project=collection.project,
            source_image_collection=collection,
            job_type_key=DetectionClusteringJob.key,
            params=params,
        )
        job.enqueue()
        logger.info(f"Triggered clustering job for collection {collection.pk}")
        return Response({"job_id": job.pk, "project_id": collection.project.pk})

    @extend_schema(parameters=[project_id_doc_param])
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)


class SourceImageUploadViewSet(DefaultViewSet, ProjectMixin):
    """
    Endpoint for uploading images.
    """

    queryset = SourceImageUpload.objects.all()

    serializer_class = SourceImageUploadSerializer
    permission_classes = [SourceImageUploadCRUDPermission]

    def get_queryset(self) -> QuerySet:
        # Only allow users to see their own uploads
        qs = super().get_queryset()
        if self.request.user.pk:
            qs = qs.filter(user=self.request.user)
        return qs

    pagination_class = LimitOffsetPaginationWithPermissions
    # This is the maximum limit for manually uploaded captures
    pagination_class.default_limit = 20


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

    def filter_queryset(self, request, queryset, view):
        taxalist_id = IntegerField(required=False).clean(request.query_params.get(self.query_param))
        if taxalist_id:
            taxa_list = TaxaList.objects.filter(id=taxalist_id).first()
            if taxa_list:
                taxa = taxa_list.taxa.all()  # Get taxalist taxon objects

                # filter by the exact determination
                query_filter = Q(determination__in=taxa)

                # filter by the taxon's children
                for taxon in taxa:
                    query_filter |= Q(determination__parents_json__contains=[{"id": taxon.pk}])

                queryset = queryset.filter(query_filter)
                return queryset

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


OccurrenceDeterminationScoreFilter = ThresholdFilter.create(
    query_param="classification_threshold", filter_param="determination_score"
)
OccurrenceOODScoreFilter = ThresholdFilter.create("determination_ood_score")


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
        OccurrenceDeterminationScoreFilter,
        OccurrenceOODScoreFilter,
    ]
    filterset_fields = [
        "event",
        "deployment",
        "determination__rank",
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
        "determination_ood_score",
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
                name="determination_ood_score",
                description="Filter occurrences by minimum out-of-distribution score.",
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

    def filter_queryset(self, request, queryset, view):
        taxalist_id = IntegerField(required=False).clean(request.query_params.get(self.query_param))
        if taxalist_id:
            taxa_list = TaxaList.objects.filter(id=taxalist_id).first()
            if taxa_list:
                taxa = taxa_list.taxa.all()  # Get taxa in the TaxaList
                query_filter = Q(id__in=taxa)
                for taxon in taxa:
                    query_filter |= Q(parents_json__contains=[{"id": taxon.pk}])

                queryset = queryset.filter(query_filter)
                return queryset

        return queryset


class TaxonUnknownSpeciesFilter(filters.BaseFilterBackend):
    """
    Filter taxa that is or is not marked as "Unknown species".
    """

    query_param = "unknown_species"

    def filter_queryset(self, request: Request, queryset, view):
        if self.query_param in request.query_params:
            unknown_species = BooleanField(required=False).clean(request.query_params.get(self.query_param))
            if unknown_species:
                queryset = queryset.filter(unknown_species=True)
            else:
                queryset = queryset.exclude(unknown_species=True)

        return queryset


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
        TaxonUnknownSpeciesFilter,
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
        qs = super().get_queryset().filter(active=True)
        project = self.get_active_project()
        qs = self.attach_tags_by_project(qs, project)

        # @TODO if taxa belongs to a project, ensure user has permission to view it
        # taxa.projects

        if project:
            qs = qs.filter(models.Q(project=project) | models.Q(project__isnull=True))

            include_unobserved = True  # Show detail views for unobserved taxa instead of 404
            # @TODO move to a QuerySet manager
            qs = qs.annotate(
                best_detection_image_path=models.Subquery(
                    Occurrence.objects.filter(
                        self.get_occurrence_filters(project),
                        determination_id=models.OuterRef("id"),
                    )
                    .order_by("-determination_score")
                    .values("best_detection__path")[:1],
                    output_field=models.TextField(),
                )
            )
            if self.action == "list":
                include_unobserved = self.request.query_params.get("include_unobserved", False)
            qs = self.get_taxa_observed(qs, project, include_unobserved=include_unobserved)
            if self.action == "retrieve":
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

    def get_taxa_observed(self, qs: QuerySet, project: Project, include_unobserved=False) -> QuerySet:
        """
        If a project is passed, only return taxa that have been observed.
        Also add the number of occurrences and the last time it was detected.
        """
        occurrence_filters = self.get_occurrence_filters(project)

        # @TODO make this recursive into child taxa and cache
        occurrences_count = models.Subquery(
            Occurrence.objects.filter(
                occurrence_filters,
                determination_id=models.OuterRef("id"),
            )
            .values("determination_id")
            .annotate(count=models.Count("id"))
            .values("count"),
            output_field=models.IntegerField(),
        )

        last_detected = models.Subquery(
            Occurrence.objects.filter(
                occurrence_filters,
                determination_id=models.OuterRef("id"),
                detections__timestamp__isnull=False,  # ensure we have a timestamp
            )
            .values("determination_id")
            .annotate(last_detected=models.Max("detections__timestamp"))
            .values("last_detected"),
            output_field=models.DateTimeField(),
        )

        # Get the best score using the determination_score field directly
        best_score = models.Subquery(
            Occurrence.objects.filter(
                occurrence_filters,
                determination_id=models.OuterRef("id"),
            )
            .values("determination_id")
            .annotate(best_score=models.Max("determination_score"))
            .values("best_score")[:1],
            output_field=models.FloatField(),
        )

        qs = qs.annotate(
            occurrences_count=Coalesce(occurrences_count, 0),
            last_detected=last_detected,
            best_determination_score=best_score,
        )

        if not include_unobserved:
            qs = qs.filter(
                models.Exists(
                    Occurrence.objects.filter(
                        occurrence_filters,
                        determination_id=models.OuterRef("id"),
                    ),
                )
            )
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
            return qs.filter(models.Q(project=project) | models.Q(project__isnull=True))
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

    @action(detail=True, methods=["get"])
    def similar(self, request, pk=None):
        try:
            ref_classification = self.get_object()
            similar_qs = ref_classification.get_similar_classifications(distance_metric="cosine")
            serializer = ClassificationSimilaritySerializer(similar_qs, many=True, context={"request": request})
            return Response(serializer.data)

        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class SummaryView(GenericAPIView, ProjectMixin):
    permission_classes = [IsActiveStaffOrReadOnly]

    @extend_schema(parameters=[project_id_doc_param])
    def get(self, request):
        """
        Return counts of all models.
        """
        project = self.get_active_project()
        if project:
            data = {
                "projects_count": Project.objects.count(),  # @TODO filter by current user, here and everywhere!
                "deployments_count": Deployment.objects.filter(project=project).count(),
                "events_count": Event.objects.filter(deployment__project=project, deployment__isnull=False).count(),
                "captures_count": SourceImage.objects.filter(deployment__project=project).count(),
                # "detections_count": Detection.objects.filter(occurrence__project=project).count(),
                "occurrences_count": Occurrence.objects.valid().filter(project=project).count(),  # type: ignore
                "taxa_count": Occurrence.objects.all().unique_taxa(project=project).count(),  # type: ignore
            }
        else:
            data = {
                "projects_count": Project.objects.count(),
                "deployments_count": Deployment.objects.count(),
                "events_count": Event.objects.filter(deployment__isnull=False).count(),
                "captures_count": SourceImage.objects.count(),
                # "detections_count": Detection.objects.count(),
                "occurrences_count": Occurrence.objects.valid().count(),  # type: ignore
                "taxa_count": Occurrence.objects.all().unique_taxa().count(),  # type: ignore
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
    permission_classes = [CanUpdateIdentification, CanDeleteIdentification]

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
    permission_classes = [SiteCRUDPermission]

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
    permission_classes = [DeviceCRUDPermission]

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
    permission_classes = [S3StorageSourceCRUDPermission]

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
