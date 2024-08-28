import logging

from ami.main.api.views import DefaultViewSet
from ami.taxa.models import TaxonObserved
from ami.taxa.serializers import TaxonObservedListSerializer, TaxonObservedSerializer

logger = logging.getLogger(__name__)


class TaxonObservedViewSet(DefaultViewSet):
    """
    Endpoint for taxa information that have been observed in a project.
    """

    ordering_fields = [
        "id",
        "taxon__name",
        "detections_count",
        "occurrences_count",
        "best_determination_score",
        "last_detected",
        "created_at",
        "updated_at",
    ]

    queryset = TaxonObserved.objects.all().select_related("taxon", "project")

    def get_queryset(self):
        qs = super().get_queryset()
        if self.action == "list":
            return qs.with_occurrence_images(classification_threshold=0)
        elif self.action == "retrieve":
            return qs.with_occurrences().with_occurrence_images(classification_threshold=0)

    def get_serializer_class(self):
        if self.action == "list":
            return TaxonObservedListSerializer
        return TaxonObservedSerializer

    # Set plural name for the viewset list name
