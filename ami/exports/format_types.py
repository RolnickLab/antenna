import csv
import json
import logging
import os
import tempfile

from django.core.serializers.json import DjangoJSONEncoder
from rest_framework import serializers

from ami.exports.base import BaseExporter
from ami.exports.utils import get_data_in_batches
from ami.main.models import Occurrence, get_media_url
from ami.ml.schemas import BoundingBox

logger = logging.getLogger(__name__)


def get_export_serializer():
    from ami.main.api.serializers import OccurrenceSerializer

    class OccurrenceExportSerializer(OccurrenceSerializer):
        detection_images = serializers.SerializerMethodField()

        def get_detection_images(self, obj: Occurrence):
            """Convert the generator field to a list before serialization"""
            if hasattr(obj, "detection_images") and callable(obj.detection_images):
                return list(obj.detection_images())  # Convert generator to list
            return []

        def get_permissions(self, instance_data):
            return instance_data

        def to_representation(self, instance):
            return serializers.HyperlinkedModelSerializer.to_representation(self, instance)

    return OccurrenceExportSerializer


class JSONExporter(BaseExporter):
    """Handles JSON export of occurrences."""

    file_format = "json"

    def get_serializer_class(self):
        return get_export_serializer()

    def get_queryset(self):
        return (
            Occurrence.objects.valid()  # type: ignore[union-attr]  Custom manager method
            .filter(project=self.project)
            .select_related(
                "determination",
                "deployment",
                "event",
            )
            .with_timestamps()  # type: ignore[union-attr]  Custom queryset method
            .with_detections_count()
            .with_identifications()
        )

    def export(self):
        """Exports occurrences to JSON format."""
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".json", mode="w", encoding="utf-8")
        with open(temp_file.name, "w", encoding="utf-8") as f:
            first = True
            f.write("[")
            records_exported = 0
            for i, batch in enumerate(get_data_in_batches(self.queryset, self.get_serializer_class())):
                json_data = json.dumps(batch, cls=DjangoJSONEncoder)
                json_data = json_data[1:-1]  # remove [ and ] from json string
                f.write(",\n" if not first else "")
                f.write(json_data)
                first = False
                records_exported += len(batch)
                self.update_job_progress(records_exported)
            f.write("]")

        self.update_export_stats(file_temp_path=temp_file.name)
        return temp_file.name  # Return file path


class OccurrenceTabularSerializer(serializers.ModelSerializer):
    """Serializer to format occurrences for tabular data export."""

    event_id = serializers.IntegerField(source="event.id", allow_null=True)
    event_name = serializers.CharField(source="event.name", allow_null=True)
    deployment_id = serializers.IntegerField(source="deployment.id", allow_null=True)
    deployment_name = serializers.CharField(source="deployment.name", allow_null=True)
    project_id = serializers.IntegerField(source="project.id", allow_null=True)
    project_name = serializers.CharField(source="project.name", allow_null=True)

    determination_id = serializers.IntegerField(source="determination.id", allow_null=True)
    determination_name = serializers.CharField(source="determination.name", allow_null=True)
    determination_score = serializers.FloatField(allow_null=True)
    verification_status = serializers.SerializerMethodField()

    best_detection_url = serializers.SerializerMethodField()
    best_detection_width = serializers.SerializerMethodField()
    best_detection_height = serializers.SerializerMethodField()

    class Meta:
        model = Occurrence
        fields = [
            "id",
            "event_id",
            "event_name",
            "deployment_id",
            "deployment_name",
            "project_id",
            "project_name",
            "determination_id",
            "determination_name",
            "determination_score",
            "verification_status",
            "detections_count",
            "first_appearance_timestamp",
            "last_appearance_timestamp",
            "duration",
            "best_detection_url",
            "best_detection_width",
            "best_detection_height",
        ]

    def get_verification_status(self, obj):
        """
        Returns 'Verified' if the occurrence has identifications, otherwise 'Not verified'.
        """
        return "Verified" if obj.identifications.exists() else "Not verified"

    def get_best_detection_url(self, obj):
        """
        Returns the full URL to the cropped detection image.
        Uses the annotated best_detection_path from the queryset.
        """
        path = getattr(obj, "best_detection_path", None)
        return get_media_url(path) if path else None

    def get_best_detection_width(self, obj):
        """Returns the width of the detection bounding box."""
        bbox = BoundingBox.from_coords(getattr(obj, "best_detection_bbox", None), raise_on_error=False)
        return bbox.width if bbox else None

    def get_best_detection_height(self, obj):
        """Returns the height of the detection bounding box."""
        bbox = BoundingBox.from_coords(getattr(obj, "best_detection_bbox", None), raise_on_error=False)
        return bbox.height if bbox else None


class CSVExporter(BaseExporter):
    """Handles CSV export of occurrences."""

    file_format = "csv"

    serializer_class = OccurrenceTabularSerializer

    def get_queryset(self):
        return (
            Occurrence.objects.valid()  # type: ignore[union-attr]  Custom queryset method
            .filter(project=self.project)
            .select_related(
                "determination",
                "deployment",
                "event",
            )
            .with_timestamps()  # type: ignore[union-attr]  Custom queryset method
            .with_detections_count()
            .with_identifications()
            .with_best_detection()  # type: ignore[union-attr]  Custom queryset method
        )

    def export(self):
        """Exports occurrences to CSV format."""

        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".csv", mode="w", newline="", encoding="utf-8")

        # Extract field names dynamically from the serializer
        serializer = self.serializer_class()
        field_names = list(serializer.fields.keys())
        records_exported = 0
        with open(temp_file.name, "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=field_names)
            writer.writeheader()

            for i, batch in enumerate(get_data_in_batches(self.queryset, self.serializer_class)):
                writer.writerows(batch)
                records_exported += len(batch)
                self.update_job_progress(records_exported)
        self.update_export_stats(file_temp_path=temp_file.name)
        return temp_file.name  # Return the file path


class DwCAExporter(BaseExporter):
    """Handles Darwin Core Archive (DwC-A) export with Event Core and Occurrence Extension."""

    file_format = "zip"

    def get_queryset(self):
        """Return the occurrence queryset (used by BaseExporter for record count)."""
        return (
            Occurrence.objects.valid()  # type: ignore[union-attr]
            .filter(project=self.project, event__isnull=False, determination__isnull=False)
            .select_related(
                "determination",
                "event",
                "deployment",
            )
            .with_detections_count()
            .with_identifications()
        )

    def get_events_queryset(self):
        from ami.main.models import Event

        return Event.objects.filter(project=self.project).select_related(
            "deployment",
            "project",
        )

    def get_filter_backends(self):
        # DwC-A exports events + occurrences; the collection-based filter doesn't apply
        return []

    def export(self):
        """Export project data as a Darwin Core Archive ZIP."""
        from django.utils.text import slugify

        from ami.exports.dwca import (
            EVENT_FIELDS,
            OCCURRENCE_FIELDS,
            create_dwca_zip,
            generate_eml_xml,
            generate_meta_xml,
            write_tsv,
        )

        project_slug = slugify(self.project.name)

        # Write event.txt
        event_file = tempfile.NamedTemporaryFile(delete=False, suffix=".txt", mode="w", encoding="utf-8")
        event_file.close()
        # Write occurrence.txt
        occ_file = tempfile.NamedTemporaryFile(delete=False, suffix=".txt", mode="w", encoding="utf-8")
        occ_file.close()

        try:
            events_qs = self.get_events_queryset()
            event_count = write_tsv(event_file.name, EVENT_FIELDS, events_qs, project_slug)
            logger.info(f"DwC-A: wrote {event_count} events")

            occ_count = write_tsv(
                occ_file.name,
                OCCURRENCE_FIELDS,
                self.queryset,
                project_slug,
                progress_callback=self.update_job_progress,
            )
            logger.info(f"DwC-A: wrote {occ_count} occurrences")

            # Ensure final progress update for small exports (<500 records)
            if self.total_records:
                self.update_job_progress(occ_count)

            # Generate metadata
            meta_xml = generate_meta_xml(EVENT_FIELDS, OCCURRENCE_FIELDS)
            eml_xml = generate_eml_xml(self.project)

            # Package into ZIP
            zip_path = create_dwca_zip(event_file.name, occ_file.name, meta_xml, eml_xml)

            self.update_export_stats(file_temp_path=zip_path)
            return zip_path
        finally:
            for path in [event_file.name, occ_file.name]:
                try:
                    os.unlink(path)
                except OSError:
                    pass
