import csv
import json
import logging
import tempfile
from collections.abc import Iterable

from django.core.serializers.json import DjangoJSONEncoder
from django.db import models
from rest_framework import serializers

from ami.exports.serializers import OccurrenceExportSerializer, OccurrenceTabularSerializer
from ami.main.models import Occurrence

logger = logging.getLogger(__name__)


def export_occurrences_to_dwc(occurrences: Iterable[Occurrence]):
    raise NotImplementedError


def export_occurrences_to_json(occurrences: models.QuerySet, job):
    """
    Export occurrences to a JSON file
    """

    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".json", mode="w", encoding="utf-8")

    with open(temp_file.name, "w", encoding="utf-8") as f:
        total = occurrences.count()
        first = True
        i = 0

        for i, batch in enumerate(get_data_in_batches(QuerySet=occurrences, Serializer=OccurrenceExportSerializer)):
            json_data = json.dumps(batch, cls=DjangoJSONEncoder)

            # Write JSON object with correct formatting
            f.write(",\n" if not first else "")  # Add comma except for the first item
            f.write(json_data)
            first = False  # Update flag after first iteration
            i += len(batch)
            job.progress.update_stage("occurrence_export", progress=round(i / total, 2))
            job.save()

    return temp_file.name  # Return file path


def export_occurrences_to_csv(occurrences: models.QuerySet, job):
    """
    Export occurrences to a CSV file
    """
    # Create a temporary file for CSV output
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".csv", mode="w", newline="", encoding="utf-8")

    # Define the CSV column headers
    field_names = [
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

    total = occurrences.count()

    with open(temp_file.name, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=field_names)
        writer.writeheader()

        # Process occurrences in batches to optimize memory usage
        for i, batch in enumerate(get_data_in_batches(occurrences, OccurrenceTabularSerializer)):
            # Write each occurrence in the batch to CSV
            for occurrence in batch:
                writer.writerow(occurrence)
            job.progress.update_stage("occurrence_export", progress=round(i / total, 2))
            job.save()
            i += len(batch)
    return temp_file.name  # Return the file path


def get_data_in_batches(QuerySet: models.QuerySet, Serializer: type[serializers.Serializer], batch_size=1000):
    """
    Yield batches of serialized data from a queryset efficiently.
    """
    items = QuerySet.iterator(chunk_size=batch_size)  # Efficient iteration to avoid memory issues
    batch = []

    for i, item in enumerate(items):
        try:
            # Serialize the occurrence object
            serializer = Serializer(item)
            item_data = serializer.data
            batch.append(item_data)

            # Yield batch once it reaches batch_size
            if len(batch) >= batch_size:
                yield batch
                batch = []  # Reset batch
        except Exception as e:
            logger.warning(f"Error processing occurrence {item.id}: {str(e)}")
            raise e

    # Yield the remaining batch
    if batch:
        yield batch
