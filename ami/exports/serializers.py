from rest_framework import serializers

from ami.main.models import Classification, Deployment, Event, Identification, Occurrence, Taxon
from ami.ml.models import Algorithm
from ami.users.models import User


class DefaultExportSerializer(serializers.ModelSerializer):
    pass


class TaxonNoParentNestedSerializer(DefaultExportSerializer):
    class Meta:
        model = Taxon
        fields = [
            "id",
            "name",
            "rank",
            "gbif_taxon_key",
        ]


class TaxonParentSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    rank = serializers.SerializerMethodField()

    def get_rank(self, obj):
        return obj.rank.value


class CaptureTaxonSerializer(DefaultExportSerializer):
    parent = TaxonNoParentNestedSerializer(read_only=True)
    parents = TaxonParentSerializer(many=True, read_only=True)

    class Meta:
        model = Taxon
        fields = [
            "id",
            "name",
            "parent",
            "parents",
            "rank",
        ]


class DeploymentNestedSerializer(DefaultExportSerializer):
    class Meta:
        model = Deployment
        fields = [
            "id",
            "name",
        ]


class EventNestedSerializer(DefaultExportSerializer):
    class Meta:
        model = Event
        fields = [
            "id",
            "name",
            "date_label",
        ]


class UserNestedSerializer(DefaultExportSerializer):
    class Meta:
        model = User
        fields = [
            "id",
            "name",
            "image",
        ]


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


class OccurrenceIdentificationSerializer(DefaultExportSerializer):
    user = UserNestedSerializer(read_only=True)
    taxon = TaxonNestedSerializer(read_only=True)

    class Meta:
        model = Identification
        fields = [
            "id",
            "taxon",
            "user",
            "withdrawn",
            "comment",
            "created_at",
        ]


class AlgorithmSerializer(DefaultExportSerializer):
    class Meta:
        model = Algorithm
        fields = [
            "id",
            "name",
            "key",
            "description",
            "uri",
            "version",
            "version_name",
            "task_type",
            "category_map",
            "created_at",
            "updated_at",
        ]


class ClassificationPredictionItemSerializer(DefaultExportSerializer):
    taxon = TaxonNestedSerializer(read_only=True)
    score = serializers.FloatField(read_only=True)
    logit = serializers.FloatField(read_only=True)


class ClassificationSerializer(DefaultExportSerializer):
    taxon = TaxonNestedSerializer(read_only=True)
    algorithm = AlgorithmSerializer(read_only=True)
    top_n = ClassificationPredictionItemSerializer(many=True, read_only=True)

    class Meta:
        model = Classification
        fields = [
            "id",
            "taxon",
            "score",
            "algorithm",
            "scores",
            "logits",
            "top_n",
            "created_at",
            "updated_at",
        ]


class ClassificationNestedSerializer(ClassificationSerializer):
    class Meta:
        model = Classification
        fields = [
            "id",
            "taxon",
            "score",
            "terminal",
            "algorithm",
            "created_at",
        ]


class OccurrenceExportSerializer(DefaultExportSerializer):
    determination = CaptureTaxonSerializer(read_only=True)
    deployment = DeploymentNestedSerializer(read_only=True)
    event = EventNestedSerializer(read_only=True)
    # first_appearance = TaxonSourceImageNestedSerializer(read_only=True)
    determination_details = serializers.SerializerMethodField()
    identifications = OccurrenceIdentificationSerializer(many=True, read_only=True)

    class Meta:
        model = Occurrence

        fields = [
            "id",
            "event",
            "deployment",
            "first_appearance_timestamp",
            "first_appearance_time",
            "duration",
            "duration_label",
            "determination",
            "detections_count",
            # "detection_images",
            "determination_score",
            "determination_details",
            "identifications",
            "created_at",
            "updated_at",
        ]

    def get_determination_details(self, obj: Occurrence):
        context = self.context
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


class OccurrenceTabularSerializer(DefaultExportSerializer):
    """Serializer to format occurrences for tabular data export."""

    event_id = serializers.IntegerField(source="event.id", allow_null=True)
    event_name = serializers.CharField(source="event.name", allow_null=True)
    deployment_id = serializers.IntegerField(source="deployment.id", allow_null=True)
    deployment_name = serializers.CharField(source="deployment.name", allow_null=True)
    determination_id = serializers.IntegerField(source="determination.id", allow_null=True)
    determination_name = serializers.CharField(source="determination.name", allow_null=True)
    detections_count = serializers.IntegerField()
    first_appearance_timestamp = serializers.DateTimeField()
    duration = serializers.SerializerMethodField()

    def get_duration(self, obj):
        return obj.duration().total_seconds() if obj.duration else None

    class Meta:
        model = Occurrence
        fields = [
            "id",
            "event_id",
            "event_name",
            "deployment_id",
            "deployment_name",
            "determination_id",
            "determination_name",
            "determination_score",
            "detections_count",
            "first_appearance_timestamp",
            "duration",
        ]
