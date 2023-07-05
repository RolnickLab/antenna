from django.db import models
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import permissions, viewsets
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response
from rest_framework.views import APIView

from ..models import Algorithm, Classification, Deployment, Detection, Event, Occurrence, Project, SourceImage, Taxon
from .serializers import (
    AlgorithmSerializer,
    ClassificationSerializer,
    DeploymentListSerializer,
    DeploymentSerializer,
    DetectionListSerializer,
    DetectionSerializer,
    EventListSerializer,
    EventSerializer,
    OccurrenceListSerializer,
    OccurrenceSerializer,
    ProjectSerializer,
    SourceImageListSerializer,
    SourceImageSerializer,
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


class DefaultViewSet(viewsets.ModelViewSet):
    filter_backends = [
        DjangoFilterBackend,
        OrderingFilter,
        SearchFilter,
    ]
    filterset_fields = []
    ordering_fields = ["created_at", "updated_at"]
    search_fields = []
    permission_classes = [permissions.AllowAny]


class ProjectViewSet(DefaultViewSet):
    """
    API endpoint that allows projects to be viewed or edited.
    """

    queryset = Project.objects.prefetch_related("deployments").all()
    serializer_class = ProjectSerializer


class DeploymentViewSet(DefaultViewSet):
    """
    A model viewset that uses different serializers
    for the list and detail views.
    """

    queryset = Deployment.objects.annotate(
        events_count=models.Count("events"),
        occurrences_count=models.Count("occurrences"),
    )
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

    # @TODO add annotations for counts
    queryset = Event.objects.select_related("deployment").annotate(
        occurrences_count=models.Count("occurrences"), captures_count=models.Count("captures")
    )  # .prefetch_related("captures").all()
    serializer_class = EventSerializer
    filterset_fields = [
        "deployment",
    ]  # "project"]
    ordering_fields = ["created_at", "updated_at", "start", "occurrences_count", "captures_count", "duration"]

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

    queryset = SourceImage.objects.annotate(detections_count=models.Count("detections"))
    serializer_class = SourceImageSerializer
    filterset_fields = ["event", "deployment"]
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

    queryset = Occurrence.objects.select_related("determination", "deployment", "event").all()
    serializer_class = OccurrenceSerializer
    filterset_fields = ["event", "deployment", "determination"]
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

    queryset = Taxon.objects.all()
    serializer_class = TaxonSerializer
    filterset_fields = ["name", "rank"]
    ordering_fields = [
        "created_at",
        "updated_at",
        "name",
    ]
    search_fields = ["name", "parent__name"]

    def get_serializer_class(self):
        """
        Return different serializers for list and detail views.
        """
        if self.action == "list":
            return TaxonListSerializer
        else:
            return TaxonSerializer


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
    filterset_fields = ["detection", "detection__occurrence", "determination", "algorithm", "type"]
    ordering_fields = [
        "created_at",
        "updated_at",
        "score",
    ]


class SummaryView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        """
        Return counts of all models.
        """
        data = {
            "projects_count": Project.objects.count(),
            "deployments_count": Deployment.objects.count(),
            "events_count": Event.objects.count(),
            "captures_count": SourceImage.objects.count(),
            "detections_count": Detection.objects.count(),
            "occurrences_count": Occurrence.objects.count(),
            "taxa_count": Taxon.objects.count(),
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
