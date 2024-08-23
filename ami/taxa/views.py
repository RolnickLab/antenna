import logging

from ami.main.api.views import DefaultViewSet
from ami.taxa.models import TaxonObserved
from ami.taxa.serializers import TaxonObservedSerializer

logger = logging.getLogger(__name__)


class TaxonObservedViewSet(DefaultViewSet):
    """
    Endpoint for taxa information that have been observed in a project.
    """

    queryset = TaxonObserved.objects.all()
    serializer_class = TaxonObservedSerializer
