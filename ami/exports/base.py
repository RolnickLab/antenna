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
        self.job.progress.add_stage_param(
            self.job.job_type_key, "Number of records exported", f"{self.queryset.count()}"
        )

    @abstractmethod
    def export(self):
        """Perform the export process."""
        raise NotImplementedError()

    @abstractmethod
    def get_queryset(self):
        raise NotImplementedError()

    def get_serializer_class(self):
        return self.serializer_class

    def get_filter_backends(self):
        from ami.main.api.views import OccurrenceCollectionFilter

        return [OccurrenceCollectionFilter]
