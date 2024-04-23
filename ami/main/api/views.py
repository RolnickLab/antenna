import logging

from django.contrib.postgres.search import TrigramSimilarity
from django.core import exceptions
from django.db import models
from django.db.models import Prefetch
from django.db.models.query import QuerySet
from django.forms import BooleanField, CharField, IntegerField
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import exceptions as api_exceptions
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.filters import SearchFilter
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from ami import tasks
from ami.base.filters import NullsLastOrderingFilter
from ami.base.pagination import LimitOffsetPaginationWithPermissions
from ami.base.permissions import IsActiveStaffOrReadOnly
from ami.utils.requests import get_active_classification_threshold

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
    S3StorageSource,
    Site,
    SourceImage,
    SourceImageCollection,
    SourceImageUpload,
    Taxon,
)
from .serializers import (
    ClassificationSerializer,
    DeploymentListSerializer,
    DeploymentSerializer,
    DetectionListSerializer,
    DetectionSerializer,
    DeviceSerializer,
    EventListSerializer,
    EventSerializer,
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
    TaxonListSerializer,
    TaxonNestedSerializer,
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
    pass


class DefaultReadOnlyViewSet(DefaultViewSetMixin, viewsets.ReadOnlyModelViewSet):
    pass


class ProjectPagination(LimitOffsetPaginationWithPermissions):
    default_limit = 20


class ProjectViewSet(DefaultViewSet):
    """
    API endpoint that allows projects to be viewed or edited.
    """

    queryset = Project.objects.filter(active=True).prefetch_related("deployments").all()
    serializer_class = ProjectSerializer
    pagination_class = ProjectPagination

    def get_serializer_class(self):
        """
        Return different serializers for list and detail views.
        """
        if self.action == "list":
            return ProjectListSerializer
        else:
            return ProjectSerializer


class DeploymentViewSet(DefaultViewSet):
    """
    A model viewset that uses different serializers
    for the list and detail views.
    """

    queryset = Deployment.objects.select_related("project", "device", "research_site")
    filterset_fields = ["project"]
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

    def get_serializer_class(self):
        """
        Return different serializers for list and detail views.
        """
        if self.action == "list":
            return DeploymentListSerializer
        else:
            return DeploymentSerializer


class EventViewSet(DefaultViewSet):
    """
    API endpoint that allows events to be viewed or edited.
    """

    queryset = Event.objects.all()
    serializer_class = EventSerializer
    filterset_fields = ["deployment", "project"]
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
        qs = qs.filter(deployment__isnull=False)
        qs = qs.annotate(
            captures_count=models.Count("captures", distinct=True),
            duration=models.F("end") - models.F("start"),
        ).select_related("deployment", "project")

        return qs


class SourceImageViewSet(DefaultViewSet):
    """
    API endpoint that allows captures from monitoring sessions to be viewed or edited.
    """

    queryset = (
        SourceImage.objects.select_related(
            "event",
            "deployment",
        )
        # .prefetch_related("jobs", "collections") # These are only needed in the detail view
        .order_by("timestamp").all()
    )

    def get_queryset(self) -> QuerySet:
        queryset = super().get_queryset()
        has_detections = self.request.query_params.get("has_detections")
        classification_threshold = get_active_classification_threshold(self.request)

        if classification_threshold is not None:
            prefetch_queryset = Detection.objects.filter(
                occurrence__detections__classifications__score__gte=classification_threshold
            )
        else:
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

        if has_detections is not None:
            has_detections = BooleanField(required=False).clean(has_detections)
            queryset = (
                queryset.annotate(
                    has_detections=models.Exists(Detection.objects.filter(source_image=models.OuterRef("pk"))),
                )
                .filter(has_detections=has_detections)
                .order_by(
                    "?"
                )  # Random order is here for our demo ML backend to limit the same images from being processed
                # @TODO remove this when we have a real queue for the ML backend
            )
        return queryset

    def get_serializer_context(self):
        return {"request": self.request}

    serializer_class = SourceImageSerializer
    filterset_fields = ["event", "deployment", "deployment__project", "collections"]
    ordering_fields = [
        "created_at",
        "updated_at",
        "timestamp",
        "size",
        "detections_count",
        "deployment__name",
        "event__start",
    ]

    def get_serializer_class(self):
        """
        Return different serializers for list and detail views.
        """
        if self.action == "list":
            return SourceImageListSerializer
        else:
            return SourceImageSerializer

    @action(detail=True, methods=["post"], name="star")
    def star(self, _request, pk=None) -> Response:
        """
        Add a source image to the project's starred images collection.
        """
        source_image = self.get_object()
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


class SourceImageCollectionViewSet(DefaultViewSet):
    """
    Endpoint for viewing collections or samples of source images.
    """

    queryset = (
        SourceImageCollection.objects.annotate(
            source_image_count=models.Count("images"),
        )
        .prefetch_related("jobs")
        .all()
    )
    serializer_class = SourceImageCollectionSerializer

    filterset_fields = ["project", "method"]
    ordering_fields = [
        "created_at",
        "updated_at",
        "name",
        "method",
        "source_image_count",
    ]

    @action(detail=True, methods=["post"], name="populate")
    def populate(self, request, pk=None):
        """
        Populate a collection with source images using the configured sampling method and arguments.
        """
        collection = self.get_object()
        collection.images.clear()
        task = tasks.populate_collection.apply_async([collection.pk])
        return Response({"task": task.id})

    def _get_source_image(self):
        """
        Allow parameter to be passed as a GET query param or in the request body.
        """
        key = "source_image"
        try:
            source_image_id = IntegerField(required=True, min_value=0).clean(
                self.request.data.get(key) or self.request.query_params.get(key)
            )
        except Exception as e:
            raise api_exceptions.ValidationError from e

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


class SourceImageUploadViewSet(DefaultViewSet):
    """
    Endpoint for uploading images.
    """

    queryset = SourceImageUpload.objects.all()

    serializer_class = SourceImageUploadSerializer

    def get_queryset(self) -> QuerySet:
        # Only allow users to see their own uploads
        qs = super().get_queryset()
        if self.request.user.pk:
            qs = qs.filter(user=self.request.user)
        return qs


class DetectionViewSet(DefaultViewSet):
    """
    API endpoint that allows detections to be viewed or edited.
    """

    queryset = Detection.objects.all()
    serializer_class = DetectionSerializer
    filterset_fields = ["source_image", "detection_algorithm"]
    ordering_fields = ["created_at", "updated_at", "detection_score", "timestamp"]

    def get_serializer_class(self):
        """
        Return different serializers for list and detail views.
        """
        if self.action == "list":
            return DetectionListSerializer
        else:
            return DetectionSerializer

    # def get_queryset(self):
    #     """
    #     Return a different queryset for list and detail views.
    #     """

    #     if self.action == "list":
    #         return Detection.objects.select_related().all()
    #     else:
    #         return Detection.objects.select_related(
    #             "detection_algorithm").all()


class OccurrenceViewSet(DefaultViewSet):
    """
    API endpoint that allows occurrences to be viewed or edited.
    """

    queryset = Occurrence.objects.all()

    serializer_class = OccurrenceSerializer
    filterset_fields = ["event", "deployment", "determination", "project", "determination__rank"]
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
        "pixel_area",
        "created_at",
    ]

    def get_serializer_class(self):
        """
        Return different serializers for list and detail views.
        """
        if self.action == "list":
            return OccurrenceListSerializer
        else:
            return OccurrenceSerializer

    def get_queryset(self) -> QuerySet:
        qs = super().get_queryset()
        from django.db.models.expressions import RawSQL

        detections_with_area = Detection.objects.annotate(
            area=RawSQL("((bbox->>2)::float - (bbox->>0)::float) * ((bbox->>3)::float - (bbox->>1)::float)", [])
        )
        qs = qs.select_related(
            "determination",
            "deployment",
            "event",
        ).annotate(
            detections_count=models.Count("detections", distinct=True),
            duration=models.Max("detections__timestamp") - models.Min("detections__timestamp"),
            first_appearance_timestamp=models.Min("detections__timestamp"),
            first_appearance_time=models.Min("detections__timestamp__time"),
            pixel_area=models.Subquery(
                detections_with_area.filter(occurrence=models.OuterRef("pk")).order_by("-area").values("area")[:1]
            ),
        )
        if self.action == "list":
            qs = (
                qs.all()
                .exclude(detections=None)
                .exclude(event=None)
                .filter(determination_score__gte=get_active_classification_threshold(self.request))
                .exclude(first_appearance_timestamp=None)  # This must come after annotations
                .order_by("-determination_score")
            )
        else:
            qs = qs.prefetch_related(
                Prefetch(
                    "detections", queryset=Detection.objects.order_by("-timestamp").select_related("source_image")
                )
            )

        return qs


class TaxonViewSet(DefaultViewSet):
    """
    API endpoint that allows taxa to be viewed or edited.
    """

    queryset = Taxon.objects.all()
    serializer_class = TaxonSerializer
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
        "detections_count",
        "last_detected",
        "best_determination_score",
        "name",
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
        with_parents = BooleanField(required=False).clean(request.query_params.get("with_parents", True))

        if query and len(query) >= min_query_length:
            if with_parents:
                taxa = (
                    Taxon.objects.select_related("parent", "parent__parent")
                    .annotate(similarity=TrigramSimilarity("name", query))
                    .order_by("-similarity")[:limit]
                )
                return Response(TaxonNestedSerializer(taxa, many=True, context={"request": request}).data)
            else:
                taxa = (
                    Taxon.objects.filter(name__icontains=query)
                    .annotate(similarity=TrigramSimilarity("name", query))
                    .order_by("-similarity")[:default_results_limit]
                    .values("id", "name", "rank")[:limit]
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

    def filter_by_occurrence(self, queryset: QuerySet) -> tuple[QuerySet, bool]:
        """
        Filter taxa by when/where it has occurred.

        Supports querying by occurrence, project, deployment, or event.

        @TODO Consider using a custom filter class for this (see get_filter_name)
        """

        occurrence_id = self.request.query_params.get("occurrence")
        project_id = self.request.query_params.get("project") or self.request.query_params.get("occurrences__project")
        deployment_id = self.request.query_params.get("deployment") or self.request.query_params.get(
            "occurrences__deployment"
        )
        event_id = self.request.query_params.get("event") or self.request.query_params.get("occurrences__event")

        filter_active = any([occurrence_id, project_id, deployment_id, event_id])

        if occurrence_id:
            occurrence = Occurrence.objects.get(id=occurrence_id)
            # This query does not need the same filtering as the others
            return queryset.filter(occurrences=occurrence).distinct(), True
        elif project_id:
            project = Project.objects.get(id=project_id)
            queryset = super().get_queryset().filter(occurrences__project=project)
        elif deployment_id:
            deployment = Deployment.objects.get(id=deployment_id)
            queryset = super().get_queryset().filter(occurrences__deployment=deployment)
        elif event_id:
            event = Event.objects.get(id=event_id)
            queryset = super().get_queryset().filter(occurrences__event=event)

        # @TODO need to return the models.Q filter used, so we can use it for counts and related occurrences.
        return queryset, filter_active

    def filter_by_classification_threshold(self, queryset: QuerySet) -> QuerySet:
        """
        Filter taxa by their best determination score in occurrences.

        This is only applicable to list queries that are not filtered by occurrence, project, deployment, or event.
        """

        queryset = (
            queryset.annotate(best_determination_score=models.Max("occurrences__determination_score"))
            .filter(best_determination_score__gte=get_active_classification_threshold(self.request))
            .distinct()
        )

        # If ordering is not specified, order by best determination score
        if not self.request.query_params.get("ordering"):
            queryset = queryset.order_by("-best_determination_score")

        return queryset

    def get_queryset(self) -> QuerySet:
        qs = super().get_queryset()
        try:
            qs, filter_active = self.filter_by_occurrence(qs)
        except exceptions.ObjectDoesNotExist as e:
            from rest_framework.exceptions import NotFound

            raise NotFound(detail=str(e))

        qs = qs.select_related("parent", "parent__parent")

        # @TODO this should check what the user has access to
        project_id = self.request.query_params.get("project")
        taxon_occurrences_query = (
            Occurrence.objects.filter(
                determination_score__gte=get_active_classification_threshold(self.request),
                event__isnull=False,
            )
            .distinct()
            .annotate(
                first_appearance_timestamp=models.Min("detections__timestamp"),
                last_appearance_timestamp=models.Max("detections__timestamp"),
            )
            .order_by("-first_appearance_timestamp")
        )
        taxon_occurrences_count_filter = models.Q(
            occurrences__determination_score__gte=get_active_classification_threshold(self.request),
            occurrences__event__isnull=False,
        )
        if project_id:
            taxon_occurrences_query = taxon_occurrences_query.filter(project=project_id)
            taxon_occurrences_count_filter &= models.Q(occurrences__project=project_id)

        if self.action == "retrieve":
            qs = qs.prefetch_related(Prefetch("occurrences", queryset=taxon_occurrences_query))

        if filter_active:
            qs = self.filter_by_classification_threshold(qs)
            qs = qs.annotate(
                occurrences_count=models.Count(
                    "occurrences",
                    filter=taxon_occurrences_count_filter,
                    distinct=True,
                ),
                last_detected=models.Max("classifications__detection__timestamp"),
            )

        elif self.action == "list":
            # If no filter don't return anything related to occurrences
            # @TODO add a project_id filter to all request from the frontend
            # event detail views should be filtered by project
            qs = qs.prefetch_related(Prefetch("occurrences", queryset=Occurrence.objects.none()))
            qs = qs.annotate(
                occurrences_count=models.Value(0),
                # events_count=models.Value(0),
                last_detected=models.Value(None, output_field=models.DateTimeField()),
            )

        return qs

    # Override the main detail view to include occurrences
    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)


class ClassificationViewSet(DefaultViewSet):
    """
    API endpoint for viewing and adding classification results from a model.
    """

    queryset = Classification.objects.all()
    serializer_class = ClassificationSerializer
    filterset_fields = ["detection", "detection__occurrence", "taxon", "algorithm"]
    ordering_fields = [
        "created_at",
        "updated_at",
        "score",
    ]


class SummaryView(GenericAPIView):
    permission_classes = [IsActiveStaffOrReadOnly]
    filterset_fields = ["project"]

    def get(self, request):
        """
        Return counts of all models.
        """
        project_id = request.query_params.get("project")
        confidence_threshold = get_active_classification_threshold(request)
        if project_id:
            project = Project.objects.get(id=project_id)
            data = {
                "projects_count": Project.objects.count(),  # @TODO filter by current user, here and everywhere!
                "deployments_count": Deployment.objects.filter(project=project).count(),
                "events_count": Event.objects.filter(deployment__project=project, deployment__isnull=False).count(),
                "captures_count": SourceImage.objects.filter(deployment__project=project).count(),
                # "detections_count": Detection.objects.filter(occurrence__project=project).count(),
                "occurrences_count": Occurrence.objects.filter(
                    project=project,
                    determination_score__gte=confidence_threshold,
                    event__isnull=False,
                ).count(),
                "taxa_count": Taxon.objects.annotate(occurrences_count=models.Count("occurrences"))
                .filter(
                    occurrences_count__gt=0,
                    occurrences__determination_score__gte=confidence_threshold,
                    occurrences__project=project,
                )
                .distinct()
                .count(),
            }
        else:
            data = {
                "projects_count": Project.objects.count(),
                "deployments_count": Deployment.objects.count(),
                "events_count": Event.objects.filter(deployment__isnull=False).count(),
                "captures_count": SourceImage.objects.count(),
                # "detections_count": Detection.objects.count(),
                "occurrences_count": Occurrence.objects.filter(
                    determination_score__gte=confidence_threshold, event__isnull=False
                ).count(),
                "taxa_count": Taxon.objects.annotate(occurrences_count=models.Count("occurrences"))
                .filter(occurrences_count__gt=0, occurrences__determination_score__gte=confidence_threshold)
                .count(),
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

    def perform_create(self, serializer):
        """
        Set the user to the current user.
        """
        serializer.save(user=self.request.user)


class SiteViewSet(DefaultViewSet):
    """
    API endpoint that allows sites to be viewed or edited.
    """

    queryset = Site.objects.all()
    serializer_class = SiteSerializer
    filterset_fields = ["project", "deployments"]
    ordering_fields = [
        "created_at",
        "updated_at",
        "name",
    ]


class DeviceViewSet(DefaultViewSet):
    """
    API endpoint that allows devices to be viewed or edited.
    """

    queryset = Device.objects.all()
    serializer_class = DeviceSerializer
    filterset_fields = ["project", "deployments"]
    ordering_fields = [
        "created_at",
        "updated_at",
        "name",
    ]


class StorageSourceViewSet(DefaultViewSet):
    """
    API endpoint that allows storage sources to be viewed or edited.
    """

    queryset = S3StorageSource.objects.all()
    serializer_class = StorageSourceSerializer
    filterset_fields = ["project", "deployments"]
    ordering_fields = [
        "created_at",
        "updated_at",
        "name",
    ]
