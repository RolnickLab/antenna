from django.core import exceptions
from django.db import models
from django.db.models.query import QuerySet
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from ..models import (
    Algorithm,
    Classification,
    Deployment,
    Detection,
    Event,
    Identification,
    Job,
    Occurrence,
    Page,
    Project,
    SourceImage,
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
    JobListSerializer,
    JobSerializer,
    LabelStudioDetectionSerializer,
    LabelStudioOccurrenceSerializer,
    LabelStudioSourceImageSerializer,
    OccurrenceListSerializer,
    OccurrenceSerializer,
    PageListSerializer,
    PageSerializer,
    ProjectListSerializer,
    ProjectSerializer,
    SourceImageListSerializer,
    SourceImageSerializer,
    StorageStatusSerializer,
    TaxonListSerializer,
    TaxonSerializer,
)

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


class DefaultViewSet(viewsets.ModelViewSet, DefaultViewSetMixin):
    pass


class DefaultReadOnlyViewSet(viewsets.ReadOnlyModelViewSet, DefaultViewSetMixin):
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
        # The first and last date should come from the captures,
        # but it may be much slower to query.
        first_date=models.Min("events__start__date"),
        last_date=models.Max("events__end__date"),
    ).select_related("project")
    filterset_fields = ["project"]
    ordering_fields = ["created_at", "updated_at", "occurrences_count", "events_count"]

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
            captures_count=models.Count("captures"),
            detections_count=models.Count("captures__detections"),
            occurrences_count=models.Count("occurrences"),
            taxa_count=models.Count("occurrences__determination", distinct=True),
        )
        .select_related("deployment", "project")
    )  # .prefetch_related("captures").all()
    serializer_class = EventSerializer
    filterset_fields = ["deployment", "project"]
    ordering_fields = [
        "created_at",
        "updated_at",
        "start",
        "captures_count",
        "detections_count",
        "occurrences_count",
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
        SourceImage.objects.annotate(
            detections_count=models.Count("detections", distinct=True),
        )
        .select_related("event", "deployment")
        .all()
    )
    serializer_class = SourceImageSerializer
    filterset_fields = ["event", "deployment", "deployment__project"]
    ordering_fields = [
        "created_at",
        "updated_at",
        "timestamp",
        "size",
        "detections_count",
    ]

    def get_serializer_class(self):
        """
        Return different serializers for list and detail views.
        """
        if self.action == "list":
            return SourceImageListSerializer
        else:
            return SourceImageSerializer


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
        )
        .select_related("determination", "deployment", "event")
        .all()
    )
    serializer_class = OccurrenceSerializer
    filterset_fields = ["event", "deployment", "determination", "project"]
    ordering_fields = ["created_at", "updated_at", "timestamp"]

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
        Taxon.objects.annotate(
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
        query = request.query_params.get("q", None)
        if query:
            taxa = Taxon.objects.filter(name__icontains=query)
            return Response(TaxonListSerializer(taxa, many=True, context={"request": request}).data)
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


class JobViewSet(DefaultViewSet):
    """
    API endpoint that allows jobs to be viewed or edited.
    """

    queryset = Job.objects.all()
    serializer_class = JobSerializer
    filterset_fields = ["status", "project", "deployment"]
    ordering_fields = [
        "created_at",
        "updated_at",
        "status",
        "started_at",
    ]

    def get_serializer_class(self):
        """
        Return different serializers for list and detail views.
        """
        if self.action == "list":
            return JobListSerializer
        else:
            return JobSerializer

    # The default schema is now returned if the progresr or config attrbutes are empty.
    # def list(self, request, *args, **kwargs):
    permission_classes = [permissions.AllowAny]
    #     """
    #     Return a list of jobs, with the most recent first.
    #     """
    #     response = super().list(request, *args, **kwargs)
    #     response.data["default_config"] = Job.default_config()
    #     response.data["default_progress"] = Job.default_progress()
    #     return response


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


class LabelStudioFlatPaginator(LimitOffsetPagination):
    """
    A custom paginator that does not nest the data under a "results" key.

    This is needed for Label Studio to work. Generally you will want all of the results in one page.

    @TODO eventually each task should be it's own JSON file and this will not be needed.
    """

    limit = 100

    def get_paginated_response(self, data):
        return Response(data)


class LabelStudioSourceImageViewSet(DefaultReadOnlyViewSet):
    """Endpoint for importing data to annotate in Label Studio."""

    queryset = SourceImage.objects.select_related("event", "event__deployment", "event__deployment__data_source")
    serializer_class = LabelStudioSourceImageSerializer
    pagination_class = LabelStudioFlatPaginator
    filterset_fields = ["event", "deployment", "deployment__project"]

    @action(detail=False, methods=["get"], name="interval")
    def interval(self, request):
        """
        Return a sample of captures based on time intervals.

        URL parameters:

        - `deployment`: limit to a specific deployment<br>
        - `project`: limit to all deployments in a specific project<br>
        - `event_day_interval`: number of days between events<br>
        - `capture_minute_interval`: number of minutes between captures<br>
        - `limit`: maximum number of captures to return<br>

        Example: `/api/labelstudio/captures/interval/?project=1&event_day_interval=3&capture_minute_interval=30&limit=100`  # noqa

        Objects are returned in a format ready to import as a list of Label Studio tasks.
        """
        from ami.main.models import sample_captures, sample_events

        deployment_id = request.query_params.get("deployment", None)
        project_id = request.query_params.get("project", None)
        day_interval = int(request.query_params.get("event_day_interval", 3))
        minute_interval = int(request.query_params.get("capture_minute_interval", 30))
        max_num = int(request.query_params.get("limit", 100))
        captures = []
        if deployment_id:
            deployments = [Deployment.objects.get(id=deployment_id)]
        elif project_id:
            project = Project.objects.get(id=project_id)
            deployments = Deployment.objects.filter(project=project)
        else:
            deployments = Deployment.objects.all()
        for deployment in deployments:
            events = sample_events(deployment=deployment, day_interval=day_interval)
            for capture in sample_captures(
                deployment=deployment, events=list(events), minute_interval=minute_interval
            ):
                captures.append(capture)
                if len(captures) >= max_num:
                    break
        return Response(self.get_serializer(captures, many=True).data)


class LabelStudioDetectionViewSet(DefaultReadOnlyViewSet):
    """ """

    queryset = Detection.objects.all()
    serializer_class = LabelStudioDetectionSerializer
    filterset_fields = ["source_image__event", "source_image__deployment", "source_image__deployment__project"]
    pagination_class = LabelStudioFlatPaginator


class LabelStudioOccurrenceViewSet(DefaultReadOnlyViewSet):
    """ """

    queryset = Occurrence.objects.all()
    serializer_class = LabelStudioOccurrenceSerializer
    filterset_fields = ["event", "deployment", "project"]
    pagination_class = LabelStudioFlatPaginator


class LabelStudioHooksViewSet(viewsets.ViewSet):
    """Endpoints for Label Studio to send data to."""

    permission_classes = [permissions.AllowAny]

    @action(detail=False, methods=["post"], name="all")
    def all(self, request):
        data = request.data
        hook_name = data.get("action")
        if hook_name == "PROJECT_UPDATED":
            return self.update_project(request)
        else:
            return Response({"action": "hook_name", "data": data})

    def update_project(self, request):
        """ """
        # from ami.labelstudio.hooks import update_project_after_save
        project = request.data["project"]
        # update_project_after_save(project=project, request=request)
        return Response({"action": "update_project", "data": project})


class IdentificationViewSet(DefaultViewSet):
    """
    API endpoint that allows identifications to be viewed or edited.
    """

    queryset = Identification.objects.all()
    serializer_class = IdentificationSerializer
    filterset_fields = ["occurrence", "user", "taxon", "primary"]
    ordering_fields = [
        "created_at",
        "updated_at",
        "user",
        "priority",
    ]

    def perform_create(self, serializer):
        """
        Set the user to the current user.
        """
        serializer.save(user=self.request.user)
