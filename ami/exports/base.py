import logging
from abc import ABC, abstractmethod

from ami.exports.utils import apply_filters

logger = logging.getLogger(__name__)


class BaseExporter(ABC):
    """Base class for all data export handlers."""

    file_format = ""  # To be defined in child classes
    serializer_class = None
    filter_backends = []

    def __init__(self, job, filters):
        self.job = job
        self.queryset = apply_filters(
            queryset=self.get_queryset(), filters=filters, filter_backends=self.get_filter_backends()
        )

    @abstractmethod
    def export(self):
        """Perform the export process."""
        pass

    @abstractmethod
    def get_queryset(self):
        pass

    def get_serializer_class(self):
        return self.serializer_class

    def get_filter_backends(self):
        from ami.main.api.views import (
            CustomOccurrenceDeterminationFilter,
            OccurrenceAlgorithmFilter,
            OccurrenceCollectionFilter,
            OccurrenceDateFilter,
            OccurrenceVerified,
            OccurrenceVerifiedByMeFilter,
        )

        return [
            CustomOccurrenceDeterminationFilter,
            OccurrenceAlgorithmFilter,
            OccurrenceCollectionFilter,
            OccurrenceDateFilter,
            OccurrenceVerified,
            OccurrenceVerifiedByMeFilter,
        ]
