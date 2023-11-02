import logging

from django.contrib.postgres.search import TrigramSimilarity
from django.core import exceptions
from django.db import models
from django.db.models.query import QuerySet
from django.forms import BooleanField, CharField, IntegerField
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response
from rest_framework.views import APIView

from ami import tasks

from ..models import (
    Algorithm,
    Classification,
    Deployment,
    Detection,
    Event,
    Identification,
    Occurrence,
    Page,
    Pipeline,
    Project,
    SourceImage,
    SourceImageCollection,
    SourceImageUpload,
    Taxon,
)
from .serializers import (
    AlgorithmSerializer,
    ClassificationSerializer,
    DeploymentListSerializer,
    DeploymentSerializer,
    DetectionListSerializer,
    DetectionSerializer,
    EventListSerializer,
    EventSerializer,
    IdentificationSerializer,
    OccurrenceListSerializer,
    OccurrenceSerializer,
    PageListSerializer,
    PageSerializer,
    PipelineNestedSerializer,
    ProjectListSerializer,
    ProjectSerializer,
    SourceImageCollectionSerializer,
    SourceImageListSerializer,
    SourceImageSerializer,
    SourceImageUploadSerializer,
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
        OrderingFilter,
        SearchFilter,
    ]
    filterset_fields = []
    ordering_fields = ["created_at", "updated_at"]
    search_fields = []
    permission_classes = [permissions.AllowAny]


class DefaultViewSet(DefaultViewSetMixin, viewsets.ModelViewSet):
    pass


class DefaultReadOnlyViewSet(DefaultViewSetMixin, viewsets.ReadOnlyModelViewSet):
    pass


class ProjectViewSet(DefaultViewSet):
    """
    API endpoint that allows projects to be viewed or edited.
    """

    queryset = Project.objects.prefetch_related("deployments").all()
    serializer_class = ProjectSerializer

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

    queryset = Deployment.objects.annotate(
        events_count=models.Count("events", distinct=True),
        occurrences_count=models.Count("occurrences", distinct=True),
        taxa_count=models.Count("occurrences__determination", distinct=True),
        captures_count=models.Count("events__captures", distinct=True),
        # The first and last date should come from the captures,
        # but it may be much slower to query.
        first_date=models.Min("events__start__date"),
        last_date=models.Max("events__end__date"),
    ).select_related("project")
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

    queryset = (
        Event.objects.select_related("deployment")
        .annotate(
            captures_count=models.Count("captures", distinct=True),
            detections_count=models.Count("captures__detections", distinct=True),
            occurrences_count=models.Count("occurrences", distinct=True),
            taxa_count=models.Count("occurrences__determination", distinct=True),
            duration=models.F("end") - models.F("start"),
        )
        .select_related("deployment", "project")
    )  # .prefetch_related("captures").all()
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


class SourceImageViewSet(DefaultViewSet):
    """
    API endpoint that allows captures from monitoring sessions to be viewed or edited.
    """

    queryset = (
        SourceImage.objects.select_related("event", "deployment")
        .prefetch_related("detections", "jobs")
        .order_by("timestamp")
        .all()
    )

    def get_queryset(self) -> QuerySet:
        queryset = super().get_queryset()
        has_detections = self.request.query_params.get("has_detections")

        if has_detections is not None:
            has_detections = BooleanField(required=False).clean(has_detections)
            queryset = (
                queryset.annotate(
                    has_detections=models.Exists(Detection.objects.filter(source_image=models.OuterRef("pk"))),
                )
                .filter(has_detections=has_detections)
                .order_by("?")
            )
        return queryset

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
        task = tasks.populate_collection.apply_async([collection.pk])
        return Response({"task": task.id})


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

    queryset = (
        Occurrence.objects.annotate(
            detections_count=models.Count("detections", distinct=True),
            duration=models.Max("detections__timestamp") - models.Min("detections__timestamp"),
            first_appearance_time=models.Min("detections__timestamp__time"),
        )
        .select_related(
            "determination",
            "deployment",
            "event",
        )
        .prefetch_related("detections")
        .all()
    )
    serializer_class = OccurrenceSerializer
    filterset_fields = ["event", "deployment", "determination", "project"]
    ordering_fields = [
        "created_at",
        "updated_at",
        "event__start",
        "first_appearance_time",
        "duration",
        "deployment",
        "determination",
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


class TaxonViewSet(DefaultViewSet):
    """
    API endpoint that allows taxa to be viewed or edited.
    """

    queryset = (
        Taxon.objects.select_related("parent", "parent__parent")
        .annotate(
            occurrences_count=models.Count("occurrences", distinct=True),
            detections_count=models.Count("classifications__detection", distinct=True),
            events_count=models.Count("occurrences__event", distinct=True),
            last_detected=models.Max("classifications__detection__timestamp"),
        )
        .all()
        .distinct()
    )
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

    def filter_by_occurrence(self, queryset: QuerySet) -> QuerySet:
        """
        Filter taxa by when/where it has occurred.

        Supports querying by occurrence, project, deployment, or event.

        @TODO Consider using a custom filter class for this (see get_filter_name)
        """

        occurrence_id = self.request.query_params.get("occurrence")
        project_id = self.request.query_params.get("project")
        deployment_id = self.request.query_params.get("deployment")
        event_id = self.request.query_params.get("event")

        if occurrence_id:
            occurrence = Occurrence.objects.get(id=occurrence_id)
            return queryset.filter(occurrences=occurrence).distinct()
        elif project_id:
            project = Project.objects.get(id=project_id)
            return super().get_queryset().filter(occurrences__project=project).distinct()
        elif deployment_id:
            deployment = Deployment.objects.get(id=deployment_id)
            return super().get_queryset().filter(occurrences__deployment=deployment).distinct()
        elif event_id:
            event = Event.objects.get(id=event_id)
            return super().get_queryset().filter(occurrences__event=event).distinct()
        else:
            return queryset

    def get_queryset(self) -> QuerySet:
        qs = super().get_queryset()
        try:
            return self.filter_by_occurrence(qs)
        except exceptions.ObjectDoesNotExist as e:
            from rest_framework.exceptions import NotFound

            raise NotFound(detail=str(e))


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

    queryset = Pipeline.objects.all()
    serializer_class = PipelineNestedSerializer
    ordering_fields = [
        "name",
        "created_at",
        "updated_at",
    ]


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


class SummaryView(APIView):
    permission_classes = [permissions.AllowAny]
    filterset_fields = ["project"]

    def get(self, request):
        """
        Return counts of all models.
        """
        project_id = request.query_params.get("project")
        if project_id:
            project = Project.objects.get(id=project_id)
            data = {
                "projects_count": Project.objects.count(),  # @TODO filter by current user, here and everywhere!
                "deployments_count": Deployment.objects.filter(project=project).count(),
                "events_count": Event.objects.filter(deployment__project=project).count(),
                "captures_count": SourceImage.objects.filter(deployment__project=project).count(),
                "detections_count": Detection.objects.filter(occurrence__project=project).count(),
                "occurrences_count": Occurrence.objects.filter(project=project).count(),
                "taxa_count": Taxon.objects.annotate(occurrences_count=models.Count("occurrences"))
                .filter(occurrences_count__gt=0)
                .filter(occurrences__project=project)
                .distinct()
                .count(),
            }
        else:
            data = {
                "projects_count": Project.objects.count(),
                "deployments_count": Deployment.objects.count(),
                "events_count": Event.objects.count(),
                "captures_count": SourceImage.objects.count(),
                "detections_count": Detection.objects.count(),
                "occurrences_count": Occurrence.objects.count(),
                "taxa_count": Taxon.objects.annotate(occurrences_count=models.Count("occurrences"))
                .filter(occurrences_count__gt=0)
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

    permission_classes = [permissions.AllowAny]
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
