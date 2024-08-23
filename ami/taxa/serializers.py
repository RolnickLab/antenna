from ami.base.serializers import DefaultSerializer
from ami.taxa.models import TaxonObserved


class TaxonObservedSerializer(DefaultSerializer):
    class Meta:
        model = TaxonObserved
        fields = [
            "id",
            "taxon",
            "project",
            "detections_count",
            "occurrences_count",
            "best_detection",
            "best_determination_score",
            "last_detected",
            "created_at",
            "updated_at",
        ]
