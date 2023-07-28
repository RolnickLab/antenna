from django.db import models
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import permissions, viewsets
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response
from rest_framework.views import APIView

from ..models import (
    Algorithm,
    Classification,
    Deployment,
    Detection,
    Event,
    Job,
    Occurrence,
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
    JobListSerializer,
    JobSerializer,
    LabelStudioDetectionSerializer,
    LabelStudioOccurrenceSerializer,
    LabelStudioSourceImageSerializer,
    OccurrenceListSerializer,
    OccurrenceSerializer,
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


class DeploymentViewSet(DefaultViewSet):
    """
    A model viewset that uses different serializers
    for the list and detail views.
    """

    queryset = Deployment.objects.annotate(
        events_count=models.Count("events", distinct=True),
        occurrences_count=models.Count("occurrences", distinct=True),
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
    queryset = (
        Event.objects.select_related("deployment")
        .annotate(
            captures_count=models.Count("captures", distinct=True),
            detections_count=models.Count("captures__detections", distinct=True),
            occurrences_count=models.Count("occurrences", distinct=True),
            taxa_count=models.Count("occurrences__determination", distinct=True),
        )
        .distinct()
    )  # .prefetch_related("captures").all()
    serializer_class = EventSerializer
    filterset_fields = [
        "deployment",
    ]  # "project"]
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

    queryset = (
        Occurrence.objects.annotate(
            detections_count=models.Count("detections", distinct=True),
        )
        .select_related("determination", "deployment", "event")
        .all()
    )
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
            "taxa_count": Taxon.objects.distinct().count(),
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


class LabelStudioSourceImageViewSet(DefaultReadOnlyViewSet):
    """
    Endpoint for importing data to annotate in Label Studio.

    if the request type is TXT then return a list of urls to the images.
    @TODO use custom renderer: https://www.django-rest-framework.org/api-guide/renderers/#example
    """

    queryset = SourceImage.objects.all()
    serializer_class = LabelStudioSourceImageSerializer
    paginator = None

    # def get_serializer_class(self):
    #     """
    #     Return different serializers for list and detail views.
    #     """
    #     if self.action == "list":
    #         return LabelStudioBatchSerializer
    #     else:
    #         return self.serializer_class

    # def list(self, request, *args, **kwargs):
    #     """
    #     Return a list of reversed urls to the API detail views for each object.
    #     """
    #     from rest_framework.reverse import reverse
    #     # import httpresponse

    #     # Manually return a text http response with a list of urls to the object details views using reverse.
    #     response = super().list(request, *args, **kwargs)
    #     response.data = []
    #     for obj in self.get_queryset():
    #         # response.write(request.build_absolute_uri(obj.get_absolute_url()) + "\n")

    #         url = reverse("api:sourceimage-detail", args=[obj.pk], request=request).rstrip("/") + ".json"
    #         response.data.append({"url": url})

    #     return response


class LabelStudioDetectionViewSet(DefaultReadOnlyViewSet):
    """ """

    queryset = Detection.objects.all()[:3]
    serializer_class = LabelStudioDetectionSerializer
    paginator = None


class LabelStudioOccurrenceViewSet(DefaultReadOnlyViewSet):
    """ """

    queryset = Occurrence.objects.all()[:3]
    serializer_class = LabelStudioOccurrenceSerializer
    paginator = None
