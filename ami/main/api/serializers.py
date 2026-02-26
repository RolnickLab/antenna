import datetime

from django.db.models import QuerySet
from guardian.shortcuts import get_perms
from rest_framework import serializers
from rest_framework.request import Request

from ami.base.fields import DateStringField
from ami.base.serializers import DefaultSerializer, MinimalNestedModelSerializer, reverse_with_params
from ami.base.views import get_active_project
from ami.jobs.models import Job
from ami.main.models import Tag
from ami.ml.models import Algorithm, Pipeline
from ami.ml.serializers import AlgorithmSerializer, PipelineNestedSerializer
from ami.users.models import User
from ami.users.roles import ProjectManager

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
    ProjectSettingsMixin,
    S3StorageSource,
    Site,
    SourceImage,
    SourceImageCollection,
    SourceImageUpload,
    TaxaList,
    Taxon,
)


class ProjectNestedSerializer(DefaultSerializer):
    class Meta:
        model = Project
        fields = [
            "id",
            "name",
            "image",
            "details",
        ]


class PrimaryKeyRelatedFieldWithOwner(serializers.PrimaryKeyRelatedField):
    def __init__(self, **kwargs):
        self.queryset: QuerySet

        self.queryset = kwargs["queryset"]
        super().__init__(**kwargs)

    def get_queryset(self):
        return self.queryset.filter(owner=self.context["request"].user)


class UserNestedSerializer(DefaultSerializer):
    details = serializers.HyperlinkedIdentityField(view_name="user-detail", lookup_field="pk", lookup_url_kwarg="id")

    class Meta:
        model = User
        fields = [
            "id",
            "name",
            "image",
            "details",
        ]


class SourceImageNestedSerializer(DefaultSerializer):
    event_id = serializers.PrimaryKeyRelatedField(source="event", read_only=True)

    class Meta:
        model = SourceImage
        fields = [
            "id",
            "details",
            "url",
            "width",
            "height",
            "timestamp",
            "event_id",
            # "detections_count",
            # "detections",
        ]


class ExampleSourceImageNestedSerializer(DefaultSerializer):
    class Meta:
        model = SourceImage
        fields = [
            "id",
            "details",
            "url",
            "width",
            "height",
            "timestamp",
        ]


class DeviceNestedSerializer(DefaultSerializer):
    class Meta:
        model = Device
        fields = [
            "id",
            "name",
            "details",
        ]


class SiteNestedSerializer(DefaultSerializer):
    class Meta:
        model = Site
        fields = [
            "id",
            "name",
            "details",
        ]


class StorageSourceNestedSerializer(DefaultSerializer):
    class Meta:
        model = S3StorageSource
        fields = [
            "id",
            "name",
            "details",
        ]


class JobTypeSerializer(serializers.Serializer):
    """
    Serializer for the JobType json field in the Job model.

    This is duplicated from ami.jobs.serializers to avoid circular imports.
    but it is extremely simple.
    """

    name = serializers.CharField(read_only=True)
    key = serializers.SlugField(read_only=True)


class JobStatusSerializer(DefaultSerializer):
    job_type = JobTypeSerializer(read_only=True)

    class Meta:
        model = Job
        fields = [
            "id",
            "details",
            "status",
            "job_type",
            "created_at",
            "updated_at",
        ]


class DeploymentListSerializer(DefaultSerializer):
    events = serializers.SerializerMethodField()
    occurrences = serializers.SerializerMethodField()
    project = ProjectNestedSerializer(read_only=True)
    device = DeviceNestedSerializer(read_only=True)
    research_site = SiteNestedSerializer(read_only=True)
    jobs = JobStatusSerializer(many=True, read_only=True)

    class Meta:
        model = Deployment
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
            "time_zone",
            "first_date",
            "last_date",
            "device",
            "research_site",
            "jobs",
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
            "time_zone",
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
            "time_zone",
            "events_count",
            # "captures_count",
            # "detections_count",
            # "occurrences_count",
            # "taxa_count",
        ]


class TaxonNoParentNestedSerializer(DefaultSerializer):
    class Meta:
        model = Taxon
        fields = [
            "id",
            "name",
            "rank",
            "details",
            "gbif_taxon_key",
            "fieldguide_id",
            "inat_taxon_id",
            "cover_image_url",
            "cover_image_credit",
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
            "draft",
        ]


class ProjectSettingsSerializer(DefaultSerializer):
    default_processing_pipeline = PipelineNestedSerializer(read_only=True)
    default_processing_pipeline_id = serializers.PrimaryKeyRelatedField(
        queryset=Pipeline.objects.all(),
        source="default_processing_pipeline",
        write_only=True,
        required=False,
        allow_null=True,
    )
    default_filters_include_taxa = TaxonNoParentNestedSerializer(read_only=True, many=True)
    default_filters_include_taxa_ids = serializers.PrimaryKeyRelatedField(
        queryset=Taxon.objects.all(),
        many=True,
        source="default_filters_include_taxa",
        write_only=True,
        required=False,
    )
    default_filters_exclude_taxa = TaxonNoParentNestedSerializer(read_only=True, many=True)
    default_filters_exclude_taxa_ids = serializers.PrimaryKeyRelatedField(
        queryset=Taxon.objects.all(),
        many=True,
        source="default_filters_exclude_taxa",
        write_only=True,
        required=False,
    )

    class Meta:
        model = Project
        fields = ProjectSettingsMixin.get_settings_field_names() + [
            "default_processing_pipeline_id",
            "default_filters_include_taxa_ids",
            "default_filters_exclude_taxa_ids",
        ]


class ProjectSerializer(DefaultSerializer):
    deployments = DeploymentNestedSerializerWithLocationAndCounts(many=True, read_only=True)
    feature_flags = serializers.SerializerMethodField()
    owner = UserNestedSerializer(read_only=True)
    settings = ProjectSettingsSerializer(source="*", required=False)
    is_member = serializers.SerializerMethodField()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Remove summary_data field if with_charts is False
        if not self.context.get("with_charts", True):
            self.fields.pop("summary_data", None)

    def get_feature_flags(self, obj):
        if obj.feature_flags:
            return obj.feature_flags.dict()
        return {}

    def get_is_member(self, obj):
        """Check if the current user is a member of this project."""
        from ami.users.roles import Role

        request = self.context["request"]
        user = request.user

        if not user or not user.is_authenticated:
            return False

        # Return True for superusers
        if user.is_superuser:
            return True

        # Check if the user has any role in the project
        return Role.user_has_any_role(user, obj)

    class Meta:
        model = Project
        fields = ProjectListSerializer.Meta.fields + [
            "deployments",
            "summary_data",  # Conditionally included based on with_charts query param
            "owner",
            "feature_flags",
            "settings",
            "is_member",  # is the current user a member of this project
        ]


class SourceImageQuickListSerializer(DefaultSerializer):
    class Meta:
        model = SourceImage
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
    example_captures = ExampleSourceImageNestedSerializer(many=True, read_only=True)
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
            "created_at",
            "updated_at",
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


MinimalEventNestedSerializer = MinimalNestedModelSerializer.create_for_model(Event)


class DeploymentCaptureNestedSerializer(DefaultSerializer):
    event = MinimalEventNestedSerializer(read_only=True, source="event_id")

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


class DeploymentSerializer(DeploymentListSerializer):
    events = DeploymentEventNestedSerializer(many=True, read_only=True)
    occurrences = serializers.SerializerMethodField()
    example_captures = DeploymentCaptureNestedSerializer(many=True, read_only=True)
    manually_uploaded_captures = DeploymentCaptureNestedSerializer(many=True, read_only=True)
    project_id = serializers.PrimaryKeyRelatedField(
        write_only=True,
        queryset=Project.objects.all(),
        source="project",
    )
    device_id = serializers.PrimaryKeyRelatedField(
        write_only=True,
        queryset=Device.objects.all(),
        source="device",
        required=False,
    )
    research_site_id = serializers.PrimaryKeyRelatedField(
        write_only=True,
        queryset=Site.objects.all(),
        source="research_site",
        required=False,
    )
    data_source = serializers.SerializerMethodField()
    data_source_id = serializers.PrimaryKeyRelatedField(
        write_only=True,
        queryset=S3StorageSource.objects.all(),
        source="data_source",
        required=False,
    )
    data_source_total_files = serializers.IntegerField(read_only=True)
    data_source_total_size = serializers.IntegerField(read_only=True)
    data_source_total_size_display = serializers.CharField(read_only=True)
    data_source_last_checked = serializers.DateTimeField(read_only=True)

    class Meta(DeploymentListSerializer.Meta):
        fields = DeploymentListSerializer.Meta.fields + [
            "project_id",
            "device_id",
            "research_site_id",
            "data_source",
            "data_source_id",
            "data_source_uri",
            "data_source_total_files",
            "data_source_total_size",
            "data_source_total_size_display",
            "data_source_last_checked",
            "data_source_subdir",
            "data_source_regex",
            "description",
            "example_captures",
            "manually_uploaded_captures",
            # "capture_images",
        ]

    def get_data_source(self, obj):
        """
        Add uri to nested serializer of the data source

        The data source is defined by both the StorageSource model
        and the extra configuration in the Deployment model.
        """

        if obj.data_source is None:
            return None
        else:
            data = StorageSourceNestedSerializer(obj.data_source, context=self.context).data
            data["uri"] = obj.data_source_uri()
            return data

    def get_occurrences(self, obj):
        """
        Return URL to the occurrences endpoint filtered by this deployment.
        """

        return reverse_with_params(
            "occurrence-list",
            request=self.context.get("request"),
            params={"deployment": obj.pk},
        )


class TaxonParentSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    rank = serializers.SerializerMethodField()

    def get_rank(self, obj):
        return obj.rank.value


class TaxonNestedSerializer(TaxonNoParentNestedSerializer):
    """
    Simple Taxon serializer with 1 level of nested parents.
    """

    parent = TaxonNoParentNestedSerializer(read_only=True)
    parents = TaxonParentSerializer(many=True, read_only=True, source="parents_json")

    class Meta(TaxonNoParentNestedSerializer.Meta):
        fields = TaxonNoParentNestedSerializer.Meta.fields + [
            "parent",
            "parents",
        ]


class TaxonSearchResultSerializer(TaxonNestedSerializer):
    class Meta:
        model = Taxon
        fields = [
            "id",
            "name",
            "rank",
            "parent",
        ]


class TagSerializer(DefaultSerializer):
    project = ProjectNestedSerializer(read_only=True)
    project_id = serializers.PrimaryKeyRelatedField(queryset=Project.objects.all(), source="project", write_only=True)
    taxa_ids = serializers.PrimaryKeyRelatedField(
        queryset=Taxon.objects.all(), many=True, source="taxa", write_only=True, required=False
    )
    taxa = serializers.SerializerMethodField()

    class Meta:
        model = Tag
        fields = ["id", "name", "project", "project_id", "taxa_ids", "taxa"]

    def get_taxa(self, obj):
        return [{"id": taxon.id, "name": taxon.name} for taxon in obj.taxa.all()]


class TaxonListSerializer(DefaultSerializer):
    # latest_detection = DetectionNestedSerializer(read_only=True)
    occurrences = serializers.SerializerMethodField()
    parents = TaxonNestedSerializer(read_only=True)
    parent_id = serializers.PrimaryKeyRelatedField(queryset=Taxon.objects.all(), source="parent")
    tags = serializers.SerializerMethodField()

    def get_tags(self, obj):
        tag_list = getattr(obj, "prefetched_tags", [])
        return TagSerializer(tag_list, many=True, context=self.context).data

    class Meta:
        model = Taxon
        fields = [
            "id",
            "name",
            "rank",
            "parent_id",
            "parents",
            "details",
            "occurrences_count",
            "occurrences",
            "tags",
            "last_detected",
            "best_determination_score",
            "cover_image_url",
            "created_at",
            "updated_at",
        ]

    def get_occurrences(self, obj):
        """
        Return URL to the occurrences endpoint filtered by this taxon.
        """

        params = {}
        params.update(dict(self.context["request"].query_params.items()))
        params.update({"determination": obj.pk})

        return reverse_with_params(
            "occurrence-list",
            request=self.context.get("request"),
            params=params,
        )


class TaxaListSerializer(serializers.ModelSerializer):
    taxa = serializers.SerializerMethodField()
    projects = serializers.PrimaryKeyRelatedField(queryset=Project.objects.all(), many=True)

    class Meta:
        model = TaxaList
        fields = ["id", "name", "description", "taxa", "projects"]

    def get_taxa(self, obj):
        """
        Return URL to the taxa endpoint filtered by this taxalist.
        """
        return reverse_with_params(
            "taxon-list",
            request=self.context.get("request"),
            params={"taxa_list_id": obj.pk},
        )


class CaptureTaxonSerializer(DefaultSerializer):
    parent = TaxonNoParentNestedSerializer(read_only=True)
    parents = TaxonParentSerializer(many=True, read_only=True)

    def get_permissions(self, instance, instance_data):
        instance_data["user_permissions"] = []
        return instance_data

    class Meta:
        model = Taxon
        fields = [
            "id",
            "name",
            "parent",
            "parents",
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


class IdentificationSerializer(DefaultSerializer):
    user = UserNestedSerializer(read_only=True)
    occurrence = OccurrenceNestedSerializer(read_only=True)
    occurrence_id = serializers.PrimaryKeyRelatedField(
        write_only=True,
        queryset=Occurrence.objects.all(),
        source="occurrence",
    )
    taxon = TaxonNestedSerializer(read_only=True)
    taxon_id = serializers.PrimaryKeyRelatedField(
        write_only=True,
        queryset=Taxon.objects.all(),
        source="taxon",
    )
    agreed_with_identification_id = serializers.PrimaryKeyRelatedField(
        queryset=Identification.objects.all(),
        source="agreed_with_identification",
        allow_null=True,
        required=False,
    )
    agreed_with_prediction_id = serializers.PrimaryKeyRelatedField(
        queryset=Classification.objects.all(),
        source="agreed_with_prediction",
        allow_null=True,
        required=False,
    )

    class Meta:
        model = Identification
        fields = [
            "id",
            "details",
            "user",
            "occurrence",
            "occurrence_id",
            "taxon",
            "taxon_id",
            "withdrawn",
            "agreed_with_identification_id",
            "agreed_with_prediction_id",
            "comment",
            "created_at",
            "updated_at",
        ]


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
        if not obj or not obj.event:
            return 0
        else:
            return obj.event.captures.filter(timestamp__lt=obj.timestamp).count()


class TaxonOccurrenceNestedSerializer(DefaultSerializer):
    # determination_algorithm = AlgorithmSerializer(read_only=True)
    deployment = DeploymentNestedSerializer(read_only=True)
    event = EventNestedSerializer(read_only=True)
    best_detection = TaxonDetectionsSerializer(read_only=True)
    determination = CaptureTaxonSerializer(read_only=True)
    # first_appearance = TaxonSourceImageNestedSerializer(read_only=True)
    # last_appearance = TaxonSourceImageNestedSerializer(read_only=True)

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
            "first_appearance_timestamp",
            "last_appearance_timestamp",
            # "first_appearance",
            # "last_appearance",
        ]


class TaxonSerializer(DefaultSerializer):
    # latest_detection = DetectionNestedSerializer(read_only=True)
    occurrences = TaxonOccurrenceNestedSerializer(many=True, read_only=True, source="example_occurrences")
    parent = TaxonNoParentNestedSerializer(read_only=True)
    parent_id = serializers.PrimaryKeyRelatedField(queryset=Taxon.objects.all(), source="parent", write_only=True)
    parents = TaxonParentSerializer(many=True, read_only=True, source="parents_json")
    tags = serializers.SerializerMethodField()
    summary_data = serializers.SerializerMethodField()

    def get_tags(self, obj):
        # Use prefetched tags
        tag_list = getattr(obj, "prefetched_tags", [])
        return TagSerializer(tag_list, many=True, context=self.context).data

    def get_summary_data(self, obj: Taxon):
        project = get_active_project(request=self.context["request"], required=False)
        return obj.summary_data(project)

    class Meta:
        model = Taxon
        fields = [
            "id",
            "name",
            "rank",
            "parent",
            "parent_id",
            "parents",
            "details",
            "occurrences_count",
            "events_count",
            "occurrences",
            "gbif_taxon_key",
            "tags",
            "last_detected",
            "best_determination_score",
            "fieldguide_id",
            "inat_taxon_id",
            "cover_image_url",
            "cover_image_credit",
            "summary_data",
            "common_name_en",
        ]


class CaptureOccurrenceSerializer(DefaultSerializer):
    determination = TaxonNoParentNestedSerializer(read_only=True)
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


class ClassificationPredictionItemSerializer(serializers.Serializer):
    taxon = TaxonNestedSerializer(read_only=True)
    score = serializers.FloatField(read_only=True)
    logit = serializers.FloatField(read_only=True)


class ClassificationSerializer(DefaultSerializer):
    taxon = TaxonNestedSerializer(read_only=True)
    algorithm = AlgorithmSerializer(read_only=True)
    top_n = ClassificationPredictionItemSerializer(many=True, read_only=True)

    class Meta:
        model = Classification
        fields = [
            "id",
            "details",
            "taxon",
            "score",
            "algorithm",
            "scores",
            "logits",
            "top_n",
            "created_at",
            "updated_at",
        ]


class ClassificationWithTaxaSerializer(ClassificationSerializer):
    """
    Return all possible taxa objects in the category map with the classification.

    This is slow for large category maps.
    It's recommended to retrieve and cache the category map with taxa ahead of time.
    """

    taxa = TaxonNestedSerializer(many=True, read_only=True)

    class Meta(ClassificationSerializer.Meta):
        fields = ClassificationSerializer.Meta.fields + [
            "taxa",
        ]


class ClassificationListSerializer(DefaultSerializer):
    class Meta:
        model = Classification
        fields = [
            "id",
            "details",
            "taxon",
            "score",
            "algorithm",
            "created_at",
            "updated_at",
        ]


class ClassificationNestedSerializer(ClassificationSerializer):
    def get_permissions(self, instance, instance_data):
        instance_data["user_permissions"] = []
        return instance_data

    class Meta:
        model = Classification
        fields = [
            "id",
            "details",
            "taxon",
            "score",
            "terminal",
            "algorithm",
            "created_at",
        ]


class CaptureDetectionsSerializer(DefaultSerializer):
    occurrence = CaptureOccurrenceSerializer(read_only=True)
    classifications = serializers.SerializerMethodField()

    class Meta:
        model = Detection
        # queryset = Detection.objects.prefetch_related("classifications")
        fields = [
            "id",
            "details",
            "url",
            "width",
            "height",
            "bbox",
            "occurrence",
            "classifications",
            "occurrence_meets_criteria",
        ]

    def get_classifications(self, obj) -> str:
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
    classifications = ClassificationNestedSerializer(many=True, read_only=True)
    capture = DetectionCaptureNestedSerializer(read_only=True, source="source_image")

    class Meta:
        model = Detection
        # queryset = Detection.objects.prefetch_related("classifications")
        fields = [
            "id",
            "details",
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
    classifications = ClassificationNestedSerializer(many=True, read_only=True)

    class Meta:
        model = Detection
        fields = DetectionListSerializer.Meta.fields + [
            "source_image",
            "detection_algorithm",
            "detection_algorithm_id",
            "classifications",
        ]


class SourceImageListSerializer(DefaultSerializer):
    detections_count = serializers.IntegerField(read_only=True)
    detections = CaptureDetectionsSerializer(many=True, read_only=True, source="filtered_detections")
    deployment = DeploymentNestedSerializer(read_only=True)
    event = EventNestedSerializer(read_only=True)
    project = serializers.PrimaryKeyRelatedField(queryset=Project.objects.all(), required=False)
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
            "size_display",
            "detections_count",
            "occurrences_count",
            "taxa_count",
            "detections",
            "project",
        ]


class SourceImageCollectionNestedSerializer(DefaultSerializer):
    class Meta:
        model = SourceImageCollection
        fields = [
            "id",
            "name",
            "details",
            "method",
        ]


class SourceImageSerializer(SourceImageListSerializer):
    uploaded_by = serializers.PrimaryKeyRelatedField(read_only=True)
    jobs = JobStatusSerializer(many=True, read_only=True)
    collections = SourceImageCollectionNestedSerializer(many=True, read_only=True)
    # file = serializers.ImageField(allow_empty_file=False, use_url=True)

    class Meta:
        model = SourceImage
        fields = SourceImageListSerializer.Meta.fields + [
            "uploaded_by",
            "test_image",
            "jobs",
            "collections",
            "event_next_capture_id",
            "event_prev_capture_id",
            "event_current_capture_index",
            "event_total_captures",
        ]


class SourceImageUploadSerializer(DefaultSerializer):
    image = serializers.ImageField(allow_empty_file=False, use_url=True)
    created_at = serializers.DateTimeField(read_only=True)
    deployment = serializers.PrimaryKeyRelatedField(
        queryset=Deployment.objects.all(),
        required=True,
    )
    user = serializers.PrimaryKeyRelatedField(
        read_only=True,
    )
    source_image = SourceImageNestedSerializer(read_only=True)

    class Meta:
        model = SourceImageUpload
        fields = [
            "id",
            "details",
            "image",
            "deployment",
            "source_image",
            "user",
            "created_at",
        ]


class SourceImageCollectionCommonKwargsSerializer(serializers.Serializer):
    # The most common kwargs for the sampling methods
    # use for the "common_combined" method
    minute_interval = serializers.IntegerField(required=False, allow_null=True)
    max_num = serializers.IntegerField(required=False, allow_null=True)
    shuffle = serializers.BooleanField(required=False, allow_null=True)

    month_start = serializers.IntegerField(required=False, allow_null=True)
    month_end = serializers.IntegerField(required=False, allow_null=True)

    date_start = DateStringField(required=False, allow_null=True)
    date_end = DateStringField(required=False, allow_null=True)

    hour_start = serializers.IntegerField(required=False, allow_null=True)
    hour_end = serializers.IntegerField(required=False, allow_null=True)

    deployment_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        allow_null=True,
        allow_empty=True,
    )

    event_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        allow_null=True,
        allow_empty=True,
    )

    research_site_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        allow_null=True,
        allow_empty=True,
    )

    # Kwargs for other sampling methods, this is not complete
    # see the SourceImageCollection model for all available kwargs.
    size = serializers.IntegerField(required=False, allow_null=True)
    num_each = serializers.IntegerField(required=False, allow_null=True)
    exclude_events = serializers.CharField(required=False, allow_null=True)
    deployment_id = serializers.IntegerField(required=False, allow_null=True)
    position = serializers.IntegerField(required=False, allow_null=True)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        # Don't return the kwargs if they are empty
        return {key: value for key, value in data.items() if value is not None}


class SourceImageCollectionSerializer(DefaultSerializer):
    source_images = serializers.SerializerMethodField()
    kwargs = SourceImageCollectionCommonKwargsSerializer(required=False, partial=True)
    jobs = JobStatusSerializer(many=True, read_only=True)
    project = serializers.PrimaryKeyRelatedField(queryset=Project.objects.all())

    class Meta:
        model = SourceImageCollection
        fields = [
            "id",
            "details",
            "name",
            "project",
            "method",
            "kwargs",
            "source_images",
            "source_images_count",
            "source_images_with_detections_count",
            "occurrences_count",
            "taxa_count",
            "description",
            "jobs",
            "created_at",
            "updated_at",
        ]

    def get_permissions(self, instance, instance_data):
        request: Request = self.context["request"]
        user = request.user
        project = instance.get_project()
        permissions = get_perms(user, project)
        source_image_collection_permissions = {
            perm.split("_")[0] for perm in permissions if perm.endswith("_sourceimagecollection")
        }
        source_image_collection_permissions.discard("create")
        if instance.dataset_type == "curated":
            source_image_collection_permissions.discard("populate")
            if Project.Permissions.STAR_SOURCE_IMAGE in permissions:
                source_image_collection_permissions.add("star")

        instance_data["user_permissions"] = list(source_image_collection_permissions)
        return instance_data

    def get_source_images(self, obj) -> str:
        """
        Return URL to the captures endpoint filtered by this collection.
        """

        return reverse_with_params(
            "sourceimage-list",
            request=self.context.get("request"),
            params={"collections": obj.pk},
        )


class OccurrenceIdentificationSerializer(DefaultSerializer):
    user = UserNestedSerializer(read_only=True)
    taxon = TaxonNestedSerializer(read_only=True)

    def get_permissions(self, instance, instance_data):
        # If the user can delete an identification then return a delete permission
        request: Request = self.context["request"]
        user = request.user
        project = instance.get_project()
        # Add delete permission if identification created by current user or user is a project manager
        permissions = set()
        if instance.user == user or ProjectManager.has_role(user, project):
            permissions.add("delete")
        instance_data["user_permissions"] = list(permissions)
        return instance_data

    class Meta:
        model = Identification
        fields = [
            "id",
            "details",
            "taxon",
            "user",
            "withdrawn",
            "comment",
            "created_at",
        ]


class OccurrenceListSerializer(DefaultSerializer):
    determination = CaptureTaxonSerializer(read_only=True)
    deployment = DeploymentNestedSerializer(read_only=True)
    event = EventNestedSerializer(read_only=True)
    # first_appearance = TaxonSourceImageNestedSerializer(read_only=True)
    determination_details = serializers.SerializerMethodField()
    identifications = OccurrenceIdentificationSerializer(many=True, read_only=True)

    def get_permissions(self, instance, instance_data):
        request: Request = self.context["request"]
        user = request.user
        project = instance.get_project()
        permissions = set()
        if Project.Permissions.CREATE_IDENTIFICATION in get_perms(user, project):
            # check if the user has identification permissions on this project,
            # then add  update permission to response
            permissions.add("update")

        instance_data["user_permissions"] = list(permissions)
        return instance_data

    class Meta:
        model = Occurrence
        # queryset = Occurrence.objects.annotate(
        #     determination_score=Max("detections__classifications__score")
        # )
        fields = [
            "id",
            "details",
            "event",
            "deployment",
            # So far, we don't need the whole related object, just the timestamps
            # "first_appearance",
            "first_appearance_timestamp",
            # need both timestamp and time for sorting at the database level
            # (want to see all moths that occur after 3am, regardless of the date)
            "first_appearance_time",
            "duration",
            "duration_label",
            "determination",
            "detections_count",
            "detection_images",
            "determination_score",
            "determination_details",
            "identifications",
            "created_at",
            "updated_at",
        ]

    def get_determination_details(self, obj: Occurrence):
        # @TODO convert this to query methods to avoid N+1 queries.
        # Currently at 100+ queries per page of 10 occurrences.
        # Add a reusable method to the OccurrenceQuerySet class and call it from the ViewSet.

        context = self.context

        # Add this occurrence to the context so that the nested serializers can access it
        # the `parent` attribute is not available since we are manually instantiating the serializers
        context["occurrence"] = obj

        taxon = TaxonNestedSerializer(obj.determination, context=context).data if obj.determination else None
        if obj.best_identification:
            identification = OccurrenceIdentificationSerializer(obj.best_identification, context=context).data
        else:
            identification = None

        if identification or not obj.best_prediction:
            prediction = None
        else:
            prediction = ClassificationNestedSerializer(obj.best_prediction, context=context).data

        return dict(
            taxon=taxon,
            identification=identification,
            prediction=prediction,
            score=obj.determination_score,
        )


class OccurrenceSerializer(OccurrenceListSerializer):
    determination = CaptureTaxonSerializer(read_only=True)
    detections = DetectionNestedSerializer(many=True, read_only=True)
    identifications = OccurrenceIdentificationSerializer(many=True, read_only=True)
    predictions = ClassificationNestedSerializer(many=True, read_only=True)
    deployment = DeploymentNestedSerializer(read_only=True)
    event = EventNestedSerializer(read_only=True)
    # first_appearance = TaxonSourceImageNestedSerializer(read_only=True)

    class Meta:
        model = Occurrence
        fields = OccurrenceListSerializer.Meta.fields + [
            "determination_id",
            "detections",
            "predictions",
        ]
        read_only_fields = [
            "determination_score",
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
            "created_at",
            "updated_at",
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
        Look up the source image (capture) that contains a specific detection or occurrence.

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
            capture_with_subject = Occurrence.objects.get(pk=occurrence_id).first_appearance

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


class EventTimelineSourceImageSerializer(DefaultSerializer):
    class Meta:
        model = SourceImage
        fields = ["id", "details"]


class EventTimelineIntervalSerializer(serializers.Serializer):
    start = serializers.DateTimeField()
    end = serializers.DateTimeField()
    first_capture = EventTimelineSourceImageSerializer(allow_null=True)
    top_capture = EventTimelineSourceImageSerializer(allow_null=True)
    captures_count = serializers.IntegerField()
    detections_count = serializers.IntegerField()
    detections_avg = serializers.IntegerField()


class EventTimelineMetaSerializer(serializers.Serializer):
    total_intervals = serializers.IntegerField()
    resolution_minutes = serializers.IntegerField()
    max_detections = serializers.IntegerField()
    min_detections = serializers.IntegerField()
    total_detections = serializers.IntegerField()
    timeline_start = serializers.DateTimeField()
    timeline_end = serializers.DateTimeField()


class EventTimelineSerializer(serializers.Serializer):
    data = EventTimelineIntervalSerializer(many=True)  # type: ignore @TODO is `data` an existing property in DRF?
    meta = EventTimelineMetaSerializer()


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


class DeviceSerializer(DefaultSerializer):
    project = serializers.PrimaryKeyRelatedField(queryset=Project.objects.all())

    class Meta:
        model = Device
        fields = [
            "id",
            "details",
            "name",
            "description",
            "project",
            "created_at",
            "updated_at",
        ]


class SiteSerializer(DefaultSerializer):
    project = serializers.PrimaryKeyRelatedField(queryset=Project.objects.all())

    class Meta:
        model = Site
        fields = [
            "id",
            "details",
            "name",
            "description",
            "project",
            "boundary_rect",
            "created_at",
            "updated_at",
        ]


class StorageSourceSerializer(DefaultSerializer):
    project = serializers.PrimaryKeyRelatedField(queryset=Project.objects.all())
    access_key = serializers.CharField(write_only=True, required=False)
    secret_key = serializers.CharField(write_only=True, required=False, style={"input_type": "password"})
    # endpoint_url = serializers.URLField(required=False, allow_blank=True)
    # @TODO the endpoint needs to support host names without a TLD extension like "minio:9000"
    endpoint_url = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    public_base_url = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    class Meta:
        model = S3StorageSource
        fields = [
            "id",
            "details",
            "name",
            "bucket",
            "prefix",
            "access_key",
            "secret_key",
            "endpoint_url",
            "public_base_url",
            "project",
            "deployments_count",
            "total_files_indexed",
            "total_size_indexed_display",
            "total_size_indexed",
            "total_captures_indexed",
            "last_checked",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "total_files",
            "total_size",
            "last_checked",
        ]
