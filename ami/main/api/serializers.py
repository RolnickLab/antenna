import datetime
import typing
import urllib.parse

from django.contrib.auth.models import Group, User
from django.db.models import Count
from rest_framework import serializers
from rest_framework.reverse import reverse

from ..models import (
    Algorithm,
    Classification,
    Deployment,
    Detection,
    Event,
    Job,
    Occurrence,
    Page,
    Project,
    SourceImage,
    Taxon,
)
from .permissions import add_object_level_permissions


def reverse_with_params(viewname: str, args=None, kwargs=None, request=None, params: dict = {}, **extra) -> str:
    query_string = urllib.parse.urlencode(params)
    base_url = reverse(viewname, request=request, args=args, kwargs=kwargs, **extra)
    url = urllib.parse.urlunsplit(("", "", base_url, query_string, ""))
    return url


def add_format_to_url(url: str, format: typing.Literal["json", "html", "csv"]) -> str:
    """
    Add a format suffix to a URL.

    This is a workaround for the DRF `format_suffix_patterns` decorator not working
    with the `reverse` function.
    """
    url_parts = urllib.parse.urlsplit(url)
    url_parts = url_parts._replace(path=f"{url_parts.path.rstrip('/')}.{format}")
    return urllib.parse.urlunsplit(url_parts)


class DefaultSerializer(serializers.HyperlinkedModelSerializer):
    url_field_name = "details"

    def to_representation(self, instance):
        data = super().to_representation(instance)

        return add_object_level_permissions(self.context.get("request").user, data)


class UserSerializer(DefaultSerializer):
    class Meta:
        model = User
        fields = ["details", "username", "email", "groups"]


class GroupSerializer(DefaultSerializer):
    class Meta:
        model = Group
        fields = ["id", "details", "name"]


class SourceImageNestedSerializer(DefaultSerializer):
    class Meta:
        model = SourceImage
        fields = [
            "id",
            "details",
            "url",
            "width",
            "height",
            "timestamp",
            # "detections_count",
            # "detections",
        ]


class DeploymentListSerializer(DefaultSerializer):
    events = serializers.SerializerMethodField()
    occurrences = serializers.SerializerMethodField()

    class Meta:
        model = Deployment
        queryset = Deployment.objects.annotate(
            events_count=Count("events"),
            occurrences_count=Count("occurrences"),
        )
        fields = [
            "id",
            "name",
            "details",
            "image",
            "events",
            "occurrences",
            "events_count",
            "captures_count",
            "occurrences_count",
            "taxa_count",
            "project",
            "created_at",
            "updated_at",
            "latitude",
            "longitude",
            "first_date",
            "last_date",
        ]

    def get_events(self, obj):
        """
        Return URL to the events endpoint filtered by this deployment.
        """

        return reverse_with_params(
            "event-list",
            request=self.context.get("request"),
            params={"deployment": obj.pk},
        )

    def get_occurrences(self, obj):
        """
        Return URL to the occurrences endpoint filtered by this deployment.
        """

        return reverse_with_params(
            "occurrence-list",
            request=self.context.get("request"),
            params={"deployment": obj.pk},
        )


class DeploymentEventNestedSerializer(DefaultSerializer):
    class Meta:
        model = Event
        fields = [
            "id",
            "name",
            "details",
            "occurrences_count",
            "taxa_count",
        ]


class DeploymentNestedSerializer(DefaultSerializer):
    class Meta:
        model = Deployment
        fields = [
            "id",
            "name",
            "details",
        ]


class DeploymentNestedSerializerWithLocationAndCounts(DefaultSerializer):
    class Meta:
        model = Deployment
        fields = [
            "id",
            "name",
            "image",
            "details",
            "latitude",
            "longitude",
            "events_count",
            # "captures_count",
            # "detections_count",
            # "occurrences_count",
            # "taxa_count",
        ]


class ProjectListSerializer(DefaultSerializer):
    deployments_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Project
        fields = [
            "id",
            "name",
            "description",
            "details",
            "deployments_count",
            "created_at",
            "updated_at",
            "image",
        ]


class ProjectSerializer(DefaultSerializer):
    deployments = DeploymentNestedSerializerWithLocationAndCounts(many=True, read_only=True)

    class Meta:
        model = Project
        fields = ProjectListSerializer.Meta.fields + [
            "deployments",
            "summary_data",  # @TODO move to a 2nd request, it's too slow
        ]


class ProjectNestedSerializer(DefaultSerializer):
    class Meta:
        model = Project
        fields = [
            "id",
            "name",
            "details",
        ]


class SourceImageQuickListSerializer(DefaultSerializer):
    class Meta:
        model = SourceImage
        queryset = SourceImage.objects.annotate(detections_count=Count("detections"))
        fields = [
            "id",
            "details",
            "url",
            "timestamp",
            "detections_count",
        ]


class EventListSerializer(DefaultSerializer):
    deployment = DeploymentNestedSerializer(
        read_only=True,
    )
    example_captures = SourceImageNestedSerializer(many=True, read_only=True)
    # captures = serializers.StringRelatedField(many=True, read_only=True)
    captures = serializers.SerializerMethodField()

    class Meta:
        model = Event
        fields = [
            "id",
            "name",
            "details",
            "deployment",
            "start",
            "end",
            "day",
            "date_label",
            "duration",
            "duration_label",
            "captures_count",
            "detections_count",
            "occurrences_count",
            "taxa_count",
            "captures",
            "example_captures",
        ]

    def get_captures(self, obj):
        """
        Return URL to the captures endpoint filtered by this event.
        """

        return reverse_with_params(
            "sourceimage-list",
            request=self.context.get("request"),
            params={"event": obj.pk},
        )


class EventNestedSerializer(DefaultSerializer):
    class Meta:
        model = Event
        fields = [
            "id",
            "name",
            "details",
            "date_label",
        ]


class DeploymentCaptureNestedSerializer(DefaultSerializer):
    event = EventNestedSerializer(read_only=True)

    class Meta:
        model = SourceImage
        fields = [
            "id",
            "details",
            "url",
            "width",
            "height",
            "timestamp",
            "event",
        ]


class DeploymentSerializer(DefaultSerializer):
    events = DeploymentEventNestedSerializer(many=True, read_only=True)
    occurrences = serializers.SerializerMethodField()
    example_captures = DeploymentCaptureNestedSerializer(many=True, read_only=True)
    data_source = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Deployment
        fields = DeploymentListSerializer.Meta.fields + [
            "description",
            "data_source",
            "example_captures",
            # "capture_images",
        ]

    def get_data_source(self, obj):
        return obj.data_source_uri()

    def get_occurrences(self, obj):
        """
        Return URL to the occurrences endpoint filtered by this deployment.
        """

        return reverse_with_params(
            "occurrence-list",
            request=self.context.get("request"),
            params={"deployment": obj.pk},
        )


class TaxonListSerializer(DefaultSerializer):
    # latest_detection = DetectionNestedSerializer(read_only=True)
    occurrences = serializers.SerializerMethodField()

    class Meta:
        model = Taxon
        fields = [
            "id",
            "name",
            "rank",
            "parent",
            "details",
            "occurrences_count",
            "detections_count",
            "occurrences",
            "occurrence_images",
            "last_detected",
        ]

    def get_occurrences(self, obj):
        """
        Return URL to the occurrences endpoint filtered by this taxon.
        """

        return reverse_with_params(
            "occurrence-list",
            request=self.context.get("request"),
            params={"determination": obj.pk},
        )


class CaptureTaxonSerializer(DefaultSerializer):
    class Meta:
        model = Taxon
        fields = [
            "id",
            "name",
            "rank",
            "details",
        ]


class OccurrenceNestedSerializer(DefaultSerializer):
    determination = CaptureTaxonSerializer(read_only=True)

    class Meta:
        model = Occurrence
        # queryset = Occurrence.objects.annotate(
        #     determination_score=Max("detections__classsifications__score")
        # )
        fields = [
            "id",
            "details",
            "determination",
            # "determination_score",
        ]


class AlgorithmSerializer(DefaultSerializer):
    class Meta:
        model = Algorithm
        fields = ["id", "name", "version", "details", "created_at"]


class TaxonDetectionsSerializer(DefaultSerializer):
    class Meta:
        model = Detection
        # queryset = Detection.objects.prefetch_related("classifications")
        fields = [
            "id",
            "url",
            "timestamp",
            "details",
            "width",
            "height",
        ]


class TaxonSourceImageNestedSerializer(DefaultSerializer):
    page = serializers.SerializerMethodField()
    page_offset = serializers.SerializerMethodField()

    class Meta:
        model = SourceImage
        fields = [
            "id",
            "details",
            "timestamp",
            "event",
            "page_offset",
            "page",
        ]

    def get_page(self, obj):
        return reverse_with_params(
            "sourceimage-list",
            request=self.context.get("request"),
            params={"offset": self.get_page_offset(obj)},
        )

    def get_page_offset(self, obj) -> int:
        # @TODO this may not be correct. Test or remove if unnecessary.
        # the Occurrence to Session navigation in the UI will be using
        # another method.
        return obj.event.captures.filter(timestamp__lt=obj.timestamp).count()


class TaxonOccurrenceNestedSerializer(DefaultSerializer):
    # determination_algorithm = AlgorithmSerializer(read_only=True)
    deployment = DeploymentNestedSerializer(read_only=True)
    event = EventNestedSerializer(read_only=True)
    best_detection = TaxonDetectionsSerializer(read_only=True)
    determination = CaptureTaxonSerializer(read_only=True)
    first_appearance = TaxonSourceImageNestedSerializer(read_only=True)
    last_appearance = TaxonSourceImageNestedSerializer(read_only=True)

    class Meta:
        model = Occurrence
        fields = [
            "id",
            "details",
            "deployment",
            "event",
            "determination_score",
            "determination",
            "best_detection",
            "detections_count",
            "duration",
            "duration_label",
            "first_appearance",
            "last_appearance",
        ]


class TaxonSerializer(DefaultSerializer):
    # latest_detection = DetectionNestedSerializer(read_only=True)
    occurrences = TaxonOccurrenceNestedSerializer(many=True, read_only=True)

    class Meta:
        model = Taxon
        fields = [
            "id",
            "name",
            "rank",
            "parent",
            "details",
            "occurrences_count",
            "detections_count",
            "events_count",
            "occurrences",
        ]


class CaptureOccurrenceSerializer(DefaultSerializer):
    determination = CaptureTaxonSerializer(read_only=True)
    determination_algorithm = AlgorithmSerializer(read_only=True)

    class Meta:
        model = Occurrence
        fields = [
            "id",
            "details",
            "determination",
            "determination_score",
            "determination_algorithm",
        ]


class ClassificationSerializer(DefaultSerializer):
    determination = CaptureTaxonSerializer(read_only=True)
    algorithm = AlgorithmSerializer(read_only=True)

    class Meta:
        model = Classification
        fields = [
            "id",
            "determination",
            "score",
            "algorithm",
            "type",
        ]


class CaptureDetectionsSerializer(DefaultSerializer):
    occurrence = CaptureOccurrenceSerializer(read_only=True)
    classifications = serializers.SerializerMethodField()

    class Meta:
        model = Detection
        # queryset = Detection.objects.prefetch_related("classifications")
        fields = [
            "id",
            "url",
            "width",
            "height",
            "bbox",
            "occurrence",
            "classifications",
        ]

    def get_classifications(self, obj):
        """
        Return URL to the classifications endpoint filtered by this detection.
        """

        return reverse_with_params(
            "classification-list",
            request=self.context.get("request"),
            params={"detection": obj.pk},
        )


class DetectionCaptureNestedSerializer(DefaultSerializer):
    class Meta:
        model = SourceImage
        fields = [
            "id",
            "details",
            "url",
            "width",
            "height",
        ]


class DetectionNestedSerializer(DefaultSerializer):
    classifications = ClassificationSerializer(many=True, read_only=True)
    capture = DetectionCaptureNestedSerializer(read_only=True, source="source_image")

    class Meta:
        model = Detection
        # queryset = Detection.objects.prefetch_related("classifications")
        fields = [
            "id",
            "timestamp",
            "url",
            "capture",
            "width",
            "height",
            "bbox",
            "occurrence",
            "classifications",
        ]


class DetectionListSerializer(DefaultSerializer):
    class Meta:
        model = Detection
        fields = [
            "id",
            "details",
            "bbox",
            "width",
            "height",
            # "top_n_classifications",
            "occurrence",
            "timestamp",
            "source_image",
            "detection_algorithm",
            "url",
        ]


class DetectionSerializer(DefaultSerializer):
    detection_algorithm = AlgorithmSerializer(read_only=True)
    detection_algorithm_id = serializers.PrimaryKeyRelatedField(
        queryset=Algorithm.objects.all(), source="detection_algorithm", write_only=True
    )

    class Meta:
        model = Detection
        fields = DetectionListSerializer.Meta.fields + [
            "source_image",
            "detection_algorithm",
            "detection_algorithm_id",
        ]


class SourceImageListSerializer(DefaultSerializer):
    detections_count = serializers.IntegerField(read_only=True)
    detections = CaptureDetectionsSerializer(many=True, read_only=True)
    # file = serializers.ImageField(allow_empty_file=False, use_url=True)

    class Meta:
        model = SourceImage
        fields = [
            "id",
            "details",
            "deployment",
            "event",
            "url",
            # "thumbnail",
            "timestamp",
            "width",
            "height",
            "size",
            "detections_count",
            "detections",
        ]


class SourceImageSerializer(DefaultSerializer):
    detections_count = serializers.IntegerField(read_only=True)
    detections = CaptureDetectionsSerializer(many=True, read_only=True)
    # file = serializers.ImageField(allow_empty_file=False, use_url=True)

    class Meta:
        model = SourceImage
        fields = SourceImageListSerializer.Meta.fields + []


class OccurrenceListSerializer(DefaultSerializer):
    determination = CaptureTaxonSerializer(read_only=True)
    deployment = DeploymentNestedSerializer(read_only=True)
    event = EventNestedSerializer(read_only=True)
    first_appearance = TaxonSourceImageNestedSerializer(read_only=True)

    class Meta:
        model = Occurrence
        # queryset = Occurrence.objects.annotate(
        #     determination_score=Max("detections__classsifications__score")
        # )
        fields = [
            "id",
            "details",
            "event",
            "deployment",
            "first_appearance",
            "duration",
            "duration_label",
            "determination",
            "detections_count",
            "detection_images",
            "determination_score",
        ]


class OccurrenceSerializer(DefaultSerializer):
    determination = CaptureTaxonSerializer(read_only=True)
    determination_id = serializers.PrimaryKeyRelatedField(
        write_only=True, queryset=Taxon.objects.all(), source="determination"
    )
    detections = DetectionNestedSerializer(many=True, read_only=True)
    deployment = DeploymentNestedSerializer(read_only=True)
    event = EventNestedSerializer(read_only=True)
    first_appearance = TaxonSourceImageNestedSerializer(read_only=True)

    class Meta:
        model = Occurrence
        fields = OccurrenceListSerializer.Meta.fields + [
            "determination_id",
            "detections",
        ]


class EventCaptureNestedSerializer(DefaultSerializer):
    """
    Load the first capture for an event. Or @TODO a single capture from the URL params.
    """

    detections = CaptureDetectionsSerializer(many=True, read_only=True)

    class Meta:
        model = SourceImage
        fields = [
            "id",
            "details",
            "url",
            "width",
            "height",
            "timestamp",
            "detections_count",
            "detections",
            # "page_url",
        ]


class EventSerializer(DefaultSerializer):
    deployment = DeploymentNestedSerializer(
        read_only=True,
    )
    deployment_id = serializers.PrimaryKeyRelatedField(
        write_only=True,
        queryset=Deployment.objects.all(),
        source="deployment",
    )
    captures = serializers.SerializerMethodField()
    first_capture = EventCaptureNestedSerializer(read_only=True)
    start = serializers.DateTimeField(read_only=True)
    end = serializers.DateTimeField(read_only=True)
    capture_page_offset = serializers.SerializerMethodField()

    class Meta:
        model = Event
        fields = [
            "id",
            "name",
            "details",
            "deployment",
            "deployment_id",
            "start",
            "end",
            "day",
            "date_label",
            "duration",
            "duration_label",
            "captures_count",
            "detections_count",
            "occurrences_count",
            "stats",
            "taxa_count",
            "captures",
            "first_capture",
            "summary_data",
            "capture_page_offset",
        ]

    def get_captures(self, obj):
        """
        Return URL to the captures endpoint filtered by this event.
        """

        params = {"event": obj.pk, "ordering": "timestamp"}

        initial_offset = self.get_capture_page_offset(obj)
        if initial_offset:
            params["offset"] = initial_offset

        return reverse_with_params(
            "sourceimage-list",
            request=self.context.get("request"),
            params=params,
        )

    def get_capture_page_offset(self, obj) -> int | None:
        """
        Look up the source image (capture) that contains a specfic detection or occurrence.

        Return the page offset for the capture to be used when requesting the capture list endpoint.
        """
        request = self.context["request"]
        event = obj
        capture_with_subject = None

        occurrence_id = request.query_params.get("occurrence")
        detection_id = request.query_params.get("detection")
        capture_id = request.query_params.get("capture")
        timestamp = request.query_params.get("timestamp")

        if capture_id:
            capture_with_subject = SourceImage.objects.get(pk=capture_id)
        elif timestamp:
            timestamp = datetime.datetime.fromisoformat(timestamp)
            capture_with_subject = event.captures.filter(timestamp=timestamp).first()
        elif detection_id:
            capture_with_subject = Detection.objects.get(pk=detection_id).source_image
        elif occurrence_id:
            capture_with_subject = Occurrence.objects.get(pk=occurrence_id).first_appearance()

        if capture_with_subject and capture_with_subject.event:
            # Assert that the capture is part of the event
            # @TODO add logging and return 404 if not found
            assert capture_with_subject.event.pk == event.pk, (
                f"Capture {capture_with_subject.pk} is not part of Event {event.pk} "
                f"(It belongs to Event {capture_with_subject.event.pk})"
            )
            # This is only reliable if the captures are ordered by timestamp. Which is the default sort order.
            offset = SourceImage.objects.filter(event=event, timestamp__lt=capture_with_subject.timestamp).count()
        else:
            offset = request.query_params.get("offset", None)

        return offset


class JobListSerializer(DefaultSerializer):
    project = ProjectNestedSerializer(read_only=True)
    deployment = DeploymentNestedSerializer(read_only=True)

    class Meta:
        model = Job
        fields = [
            "id",
            "details",
            "name",
            "project",
            "deployment",
            "status",
            "progress",
            "started_at",
            "finished_at",
            # "duration",
            # "duration_label",
            # "progress",
            # "progress_label",
            # "progress_percent",
            # "progress_percent_label",
        ]


class JobSerializer(DefaultSerializer):
    project = ProjectNestedSerializer(read_only=True)
    project_id = serializers.PrimaryKeyRelatedField(write_only=True, queryset=Project.objects.all(), source="project")
    config = serializers.JSONField(initial=Job.default_config(), allow_null=False, required=False)
    progress = serializers.JSONField(initial=Job.default_progress(), allow_null=False, required=False)

    class Meta:
        model = Job
        fields = JobListSerializer.Meta.fields + [
            "config",
            "result",
            "project",
            "project_id",
        ]


class StorageStatusSerializer(serializers.Serializer):
    data_source = serializers.CharField(max_length=200)


class PageSerializer(DefaultSerializer):
    details = serializers.HyperlinkedIdentityField(view_name="page-detail", lookup_field="slug")

    class Meta:
        model = Page
        fields = [
            "id",
            "details",
            "name",
            "slug",
            "content",
            "html",
            "nav_level",
            "nav_order",
            "link_class",
            "published",
            "updated_at",
        ]


class PageListSerializer(PageSerializer):
    class Meta:
        model = Page
        queryset = Page.objects.filter(published=True)  # This has no effect
        fields = [
            "id",
            "details",
            "name",
            "slug",
            "nav_level",
            "nav_order",
            "link_class",
            "published",
            "updated_at",
        ]


class LabelStudioBatchSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()

    class Meta:
        model = SourceImage
        fields = ["url"]

    def get_url(self, obj):
        # return f"https://example.com/label-studio/captures/{obj.pk}/"
        url = reverse_with_params(
            "api:labelstudio-captures-detail",
            request=self.context.get("request"),
            args=[obj.pk],
        )
        url = add_format_to_url(url, "json")
        return url


class LabelStudioSourceImageSerializer(serializers.ModelSerializer):
    """
    Serialize source images for manual annotation of detected objects in Label Studio.

    Manually specifies the json output to match the Label Studio task format.
    https://labelstud.io/guide/tasks.html#Example-JSON-format
    """

    data = serializers.SerializerMethodField()
    annotations = serializers.SerializerMethodField()
    predictions = serializers.SerializerMethodField()

    class Meta:
        model = SourceImage
        fields = ["data", "annotations", "predictions"]

    def get_data(self, obj):
        deployment_name = obj.deployment.name if obj.deployment else ""
        project_name = obj.deployment.project.name if obj.deployment and obj.deployment.project else ""
        # public_url = obj.deployment.data_source.public_url(obj.path)
        return {
            "image": obj.public_url(),
            "ami_id": obj.pk,
            "timestamp": obj.timestamp,
            "event": obj.event.date_label() if obj.event else None,
            "event_id": obj.event.pk if obj.event else None,
            "deployment": (obj.deployment.name if obj.deployment else None),
            "deployment_id": (obj.deployment.pk if obj.deployment else None),
            "project": (obj.deployment.project.name if obj.deployment and obj.deployment.project else None),
            "project_id": (obj.deployment.project.pk if obj.deployment and obj.deployment.project else None),
            "location": f"{project_name} / {deployment_name}",
        }

    def get_annotations(self, obj):
        # @TODO implement if necessary, make optional by URL param
        return []

    def get_predictions(self, obj):
        # @TODO implement if necessary, make optional by URL param
        return []


class LabelStudioDetectionSerializer(serializers.ModelSerializer):
    """
    Serialize detections for manual annotation of objects of interest in Label Studio.

    Manually specifies the json output to match the Label Studio task format.
    https://labelstud.io/guide/tasks.html
    """

    data = serializers.SerializerMethodField()
    annotations = serializers.SerializerMethodField()
    predictions = serializers.SerializerMethodField()

    class Meta:
        model = Detection
        fields = ["data", "annotations", "predictions"]

    def get_data(self, obj):
        # public_url = obj.deployment.data_source.public_url(obj.path)

        return {
            "image": obj.public_url(),
            "ami_id": obj.pk,
            "timestamp": obj.timestamp,
            "deployment": (obj.source_image.deployment.name if obj.source_image.deployment else None),
            "deployment_id": (obj.source_image.deployment.pk if obj.source_image.deployment else None),
            "occurrence_id": (obj.occurrence.pk if obj.occurrence else None),
            "project": (
                obj.source_image.deployment.project.name
                if obj.source_image.deployment and obj.source_image.deployment.project
                else None
            ),
            "project_id": (
                obj.source_image.deployment.project.pk
                if obj.source_image.deployment and obj.source_image.deployment.project
                else None
            ),
            "source_image": obj.source_image.url(),
            "source_image_id": obj.source_image.pk,
        }

    def get_annotations(self, obj):
        return [
            # {
            #     "result": [
            #         {
            #             "type": "choices",
            #             "value": {
            #                 "choices": [
            #                     "Moth",  # these become the selected choice!
            #                     "Non-Moth",
            #                 ]
            #             },
            #             "choice": "single",
            #             "to_name": "image",
            #             "from_name": "choice",
            #         }
            #     ],
            # }
        ]

    def get_predictions(self, obj):
        # @TODO implement if necessary, make optional by URL param
        return []


class LabelStudioOccurrenceSerializer(serializers.ModelSerializer):
    """
    Serialize occurrences for manual annotation of objects of interest in Label Studio.

    Manually specifies the json output to match the Label Studio task format.
    https://labelstud.io/guide/tasks.html
    """

    data = serializers.SerializerMethodField()
    annotations = serializers.SerializerMethodField()
    predictions = serializers.SerializerMethodField()

    class Meta:
        model = Occurrence
        fields = ["data", "annotations", "predictions"]

    def get_data(self, obj):
        best_detection: Detection = obj.best_detection()
        first_appearance: SourceImage = obj.first_appearance()
        deployment_name = obj.deployment.name if obj.deployment else ""
        project_name = obj.deployment.project.name if obj.deployment and obj.deployment.project else ""
        return {
            "image": best_detection.url(),
            "ami_id": obj.pk,
            "url": obj.url(),
            "context_url": obj.context_url(),
            "deployment": (obj.deployment.name if obj.deployment else None),
            "deployment_id": (obj.deployment.pk if obj.deployment else None),
            "project": (obj.deployment.project.name if obj.deployment and obj.deployment.project else None),
            "project_id": (obj.deployment.project.pk if obj.deployment and obj.deployment.project else None),
            "event": (obj.event.day() if obj.event else None),
            "source_image": best_detection.url(),
            "source_image_id": best_detection.pk,
            "details_link": f"<a href='{obj.url()}' target='_blank'>View Details</a>",
            "context_link": f"<a href='{obj.context_url()}' target='_blank'>View Context</a>",
            "details_url": obj.url(),
            "table": {
                "Location": f"{project_name} / {deployment_name}",
                "Date": (obj.event.day().strftime("%B %m, %Y") if obj.event else None),
                "First Appearance": first_appearance.timestamp.strftime("%I:%M %p")
                if first_appearance.timestamp
                else None,
            },
        }

    def get_annotations(self, obj):
        return []

    def get_predictions(self, obj):
        # @TODO implement if necessary, make optional by URL param
        return []
