from ami.base.serializers import DefaultSerializer, MinimalNestedModelSerializer
from ami.main.api.serializers import OccurrenceNestedSerializer, TaxonSerializer
from ami.main.models import Detection
from ami.taxa.models import TaxonObserved

MinimalDetectionNestedSerializer = MinimalNestedModelSerializer.create_for_model(Detection)


class TaxonObservedListSerializer(DefaultSerializer):
    # occurrences = DefaultSerializer(many=True, read_only=True, source="top_occurrences")
    # best_detection = MinimalNestedModelSerializer(source="best_detection_id", read_only=True)
    taxon = TaxonSerializer()

    class Meta:
        model = TaxonObserved
        fields = [
            "id",
            "details",
            "taxon",
            "project",
            "detections_count",
            "occurrences_count",
            "best_determination_score",
            "last_detected",
            "created_at",
            "updated_at",
            "occurrence_images",
        ]


class TaxonObservedSerializer(TaxonObservedListSerializer):
    occurrences = OccurrenceNestedSerializer(many=True, read_only=True, source="top_occurrences")

    class Meta(TaxonObservedListSerializer.Meta):
        fields = TaxonObservedListSerializer.Meta.fields + [
            "occurrences",
        ]
