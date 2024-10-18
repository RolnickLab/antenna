import csv
import json
import logging

from django.core.cache import cache
from django.core.files.storage import default_storage
from django.utils import timezone
from django.utils.text import slugify
from rest_framework import serializers
from rest_framework.views import APIView

logger = logging.getLogger(__name__)


class BaseExportSerializer(serializers.Serializer):
    """
    Base serializer for exporting data in various formats, from multiple models.
    """

    pass


class BaseExportView(APIView):
    """
    Read-only API view for exporting data in various formats, from multiple models.
    """

    pass


def write_export(report_name, Serializer, get_data_batch_function, format="csv"):
    timestamp = timezone.now().strftime("%Y%m%d-%H%M%S")
    file_name = f"{slugify(report_name)}-{timestamp}.{format}"
    file_path = f"exports/{file_name}"

    try:
        with default_storage.open(file_path, "w") as file:
            if format == "csv":
                writer = csv.writer(file)
                writer.writerow(Serializer().fields.keys())  # Write header
                for batch in get_data_batch_function():
                    serializer = Serializer(batch, many=True)
                    for row in serializer.data:
                        writer.writerow(row.values())
            else:  # JSON
                file.write("[")
                first = True
                for batch in get_data_batch_function(report_name):
                    serializer = Serializer(batch, many=True)
                    for item in serializer.data:
                        if not first:
                            file.write(",")
                        json.dump(item, file)
                        first = False
                file.write("]")

        # Cache the file path
        cache.set(f"export_{report_name}_{format}", file_path, 3600)  # Cache for 1 hour

        logger.info(f"Export generated successfully: {file_path}")
        return file_path
    except Exception as e:
        logger.error(f"Error generating export: {str(e)}")
        raise
