import urllib.parse

from django.contrib.auth.models import Group, User
from django.db.models import Count
from rest_framework import serializers
from rest_framework.reverse import reverse

from ..models import Algorithm, Classification, Deployment, Detection, Event, Occurrence, Project, SourceImage, Taxon


def reverse_with_params(viewname: str, request, params: dict, *args, **kwargs) -> str:
    query_string = urllib.parse.urlencode(params)
    base_url = reverse(viewname, request=request, args=args, kwargs=kwargs)
    url = urllib.parse.urlunsplit(("", "", base_url, query_string, ""))
    return url


class DefaultSerializer(serializers.HyperlinkedModelSerializer):
    url_field_name = "details"


class UserSerializer(DefaultSerializer):
    class Meta:
        model = User
        fields = ["details", "username", "email", "groups"]


class GroupSerializer(DefaultSerializer):
    class Meta:
        model = Group
        fields = ["id", "details", "name"]


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
            "events",
            "occurrences",
            "events_count",
            "captures_count",
            "detections_count",
            "occurrences_count",
            "taxa_count",
            "project",
            "created_at",
            "updated_at",
            "latitude",
            "longitude",
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


class DeploymentSerializer(DefaultSerializer):
    events = DeploymentEventNestedSerializer(many=True, read_only=True)
    occurrences = serializers.SerializerMethodField()

    class Meta:
        model = Deployment
        fields = DeploymentListSerializer.Meta.fields + [
            "description",
            "data_source",
        ]

    def get_occurrences(self, obj):
        """
        Return URL to the occurrences endpoint filtered by this deployment.
        """

        return reverse_with_params(
            "occurrence-list",
            request=self.context.get("request"),
            params={"deployment": obj.pk},
        )


class DeploymentNestedSerializer(DefaultSerializer):
    class Meta:
        model = Deployment
        fields = [
            "id",
            "name",
            "details",
        ]


class ProjectSerializer(DefaultSerializer):
    deployments = DeploymentNestedSerializer(many=True, read_only=True)
    deployments_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Project
        fields = [
            "id",
            "name",
            "description",
            "details",
            "deployments",
            "deployments_count",
            "created_at",
            "updated_at",
        ]


class SourceImageNestedSerializer(DefaultSerializer):
    class Meta:
        model = SourceImage
        queryset = SourceImage.objects.annotate(detections_count=Count("detections"))
        fields = [
            "id",
            "details",
            "url",
            "width",
            "height",
            "timestamp",
            "detections_count",
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
    start = serializers.DateTimeField(read_only=True)
    end = serializers.DateTimeField(read_only=True)

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
            "captures",
            "captures_count",
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
        ]


class TaxonOccurrenceNestedSerializer(DefaultSerializer):
    # determination_algorithm = AlgorithmSerializer(read_only=True)
    best_detection = TaxonDetectionsSerializer(read_only=True)
    determination = CaptureTaxonSerializer(read_only=True)

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


class DetectionNestedSerializer(DefaultSerializer):
    classifications = ClassificationSerializer(many=True, read_only=True)

    class Meta:
        model = Detection
        # queryset = Detection.objects.prefetch_related("classifications")
        fields = [
            "id",
            "timestamp",
            "url",
            "source_image",
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
            "determination",
            "detections_count",
            "detection_images",
            # "determination_score",
        ]


class OccurrenceSerializer(DefaultSerializer):
    determination = CaptureTaxonSerializer(read_only=True)
    determination_id = serializers.PrimaryKeyRelatedField(
        write_only=True, queryset=Taxon.objects.all(), source="determination"
    )
    detections = DetectionNestedSerializer(many=True, read_only=True)
    deployment = DeploymentNestedSerializer(read_only=True)
    event = EventNestedSerializer(read_only=True)

    class Meta:
        model = Occurrence
        fields = OccurrenceListSerializer.Meta.fields + [
            "determination_id",
            "detections",
        ]
