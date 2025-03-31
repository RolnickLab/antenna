import logging
import os
from abc import ABC, abstractmethod

from ami.exports.utils import apply_filters

logger = logging.getLogger(__name__)


class BaseExporter(ABC):
    """Base class for all data export handlers."""

    file_format = ""  # To be defined in child classes
    serializer_class = None
    filter_backends = []

    def __init__(self, data_export):
        self.data_export = data_export
        self.job = data_export.job if hasattr(data_export, "job") else None
        self.project = data_export.project
        self.queryset = apply_filters(
            queryset=self.get_queryset(), filters=data_export.filters, filter_backends=self.get_filter_backends()
        )
        self.total_records = self.queryset.count()
        if self.job:
            self.job.progress.add_stage_param(
                self.job.job_type_key, "Total records to export", f"{self.total_records}"
            )
            self.job.progress.add_stage_param(self.job.job_type_key, "Number of records exported")

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

    def update_export_stats(self, file_temp_path=None):
        """
        Updates record_count based on queryset and file size after export.
        """
        # Set record count from queryset
        self.data_export.record_count = self.queryset.count()

        # Check if temp file path is provided and update file size

        if file_temp_path and os.path.exists(file_temp_path):
            self.data_export.file_size = os.path.getsize(file_temp_path)

        # Save the updated values
        self.data_export.save()

    def update_job_progress(self, records_exported):
        """
        Updates job progress and record count.
        """
        if self.job:
            self.job.progress.update_stage(
                self.job.job_type_key, progress=round(records_exported / self.total_records, 2)
            )
            self.job.progress.add_or_update_stage_param(
                self.job.job_type_key, "Number of records exported", f"{records_exported}"
            )
            self.job.save()
