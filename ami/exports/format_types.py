import csv
import json
import logging
import tempfile

from django.core.serializers.json import DjangoJSONEncoder

from ami.exports.base import BaseExporter
from ami.exports.serializers import OccurrenceTabularSerializer, get_export_serializer
from ami.exports.utils import get_data_in_batches

logger = logging.getLogger(__name__)


class JSONExporter(BaseExporter):
    """Handles JSON export of occurrences."""

    file_format = "json"
    from ami.exports.serializers import get_export_serializer

    def get_serializer_class(self):
        return get_export_serializer()

    def get_queryset(self):
        return self.job.project.occurrences.all()

    def export(self):
        """Exports occurrences to JSON format."""
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".json", mode="w", encoding="utf-8")

        with open(temp_file.name, "w", encoding="utf-8") as f:
            total = self.queryset.count()
            first = True

            for i, batch in enumerate(get_data_in_batches(self.queryset, self.get_serializer_class())):
                json_data = json.dumps(batch, cls=DjangoJSONEncoder)
                f.write(",\n" if not first else "")
                f.write(json_data)
                first = False
                self.job.progress.update_stage("occurrence_export", progress=round(i / total, 2))
                self.job.save()

        return temp_file.name  # Return file path


class CSVExporter(BaseExporter):
    """Handles CSV export of occurrences."""

    file_format = "csv"

    serializer_class = OccurrenceTabularSerializer

    def get_queryset(self):
        return self.job.project.occurrences.all()

    def export(self):
        """Exports occurrences to CSV format."""
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".csv", mode="w", newline="", encoding="utf-8")

        # Extract field names dynamically from the serializer
        serializer = self.serializer_class()
        field_names = list(serializer.fields.keys())

        total = self.queryset.count()

        with open(temp_file.name, "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=field_names)
            writer.writeheader()

            for i, batch in enumerate(get_data_in_batches(self.queryset, self.serializer_class)):
                writer.writerows(batch)
                self.job.progress.update_stage("occurrence_export", progress=round(i / total, 2))
                self.job.save()

        return temp_file.name  # Return the file path
