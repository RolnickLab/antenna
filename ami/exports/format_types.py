import csv
import json
import logging
import os
import tempfile

from django.core.serializers.json import DjangoJSONEncoder
from rest_framework import serializers

from ami.exports.base import BaseExporter
from ami.exports.utils import get_data_in_batches
from ami.main.models import Occurrence, SourceImage, get_media_url
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

    # Machine prediction fields
    best_machine_prediction_name = serializers.CharField(allow_null=True, default=None)
    best_machine_prediction_algorithm = serializers.CharField(allow_null=True, default=None)
    best_machine_prediction_score = serializers.FloatField(allow_null=True, default=None)

    # Verification fields
    verified_by = serializers.SerializerMethodField()
    participant_count = serializers.IntegerField(default=0)
    agreed_with_algorithm = serializers.SerializerMethodField()
    agreed_with_user = serializers.SerializerMethodField()
    determination_matches_machine_prediction = serializers.SerializerMethodField()

    # Detection fields
    best_detection_url = serializers.SerializerMethodField()
    best_detection_bbox = serializers.SerializerMethodField()
    best_detection_width = serializers.SerializerMethodField()
    best_detection_height = serializers.SerializerMethodField()
    best_detection_capture_url = serializers.SerializerMethodField()

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
            "best_machine_prediction_name",
            "best_machine_prediction_algorithm",
            "best_machine_prediction_score",
            "verified_by",
            "participant_count",
            "agreed_with_algorithm",
            "agreed_with_user",
            "determination_matches_machine_prediction",
            "detections_count",
            "first_appearance_timestamp",
            "last_appearance_timestamp",
            "duration",
            "best_detection_url",
            "best_detection_bbox",
            "best_detection_width",
            "best_detection_height",
            "best_detection_capture_url",
        ]

    def get_verification_status(self, obj) -> bool:
        """True if the occurrence has any non-withdrawn human identification."""
        count = getattr(obj, "participant_count", None)
        if count is not None:
            return count > 0
        return obj.identifications.filter(withdrawn=False).exists()

    def get_verified_by(self, obj):
        """Returns the display name of the user who made the best identification."""
        return getattr(obj, "verified_by_name", None)

    def get_agreed_with_algorithm(self, obj):
        """Returns the algorithm name if the identifier explicitly agreed with an ML prediction."""
        return getattr(obj, "agreed_with_algorithm_name", None)

    def get_agreed_with_user(self, obj):
        """Returns the email of the prior identifier the best identification explicitly agreed with."""
        return getattr(obj, "agreed_with_user_email", None)

    def get_determination_matches_machine_prediction(self, obj):
        """Returns whether the determination taxon matches the best machine prediction taxon."""
        prediction_taxon_id = getattr(obj, "best_machine_prediction_taxon_id", None)
        if prediction_taxon_id is None or obj.determination_id is None:
            return None
        return obj.determination_id == prediction_taxon_id

    def get_best_detection_url(self, obj):
        """Returns the full URL to the cropped detection image."""
        path = getattr(obj, "best_detection_path", None)
        return get_media_url(path) if path else None

    def get_best_detection_bbox(self, obj):
        """Returns the raw bounding box coordinates [x1, y1, x2, y2]."""
        return getattr(obj, "best_detection_bbox", None)

    def get_best_detection_width(self, obj):
        """Returns the width of the detection bounding box."""
        bbox = BoundingBox.from_coords(getattr(obj, "best_detection_bbox", None), raise_on_error=False)
        return bbox.width if bbox else None

    def get_best_detection_height(self, obj):
        """Returns the height of the detection bounding box."""
        bbox = BoundingBox.from_coords(getattr(obj, "best_detection_bbox", None), raise_on_error=False)
        return bbox.height if bbox else None

    def get_best_detection_capture_url(self, obj):
        """Returns the public URL to the source capture (original full-frame image).

        Built from annotated `path` + `public_base_url` to avoid loading the
        capture (SourceImage) row per occurrence; presigned URLs for private
        buckets aren't supported here for the same reason.
        """
        path = getattr(obj, "best_detection_capture_path", None)
        base_url = getattr(obj, "best_detection_capture_public_base_url", None)
        if path and base_url:
            return SourceImage.build_public_url(base_url, path)
        return None


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
            .with_best_machine_prediction()
            .with_verification_info()
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


def _append_validation_report_to_zip(zip_path, validation) -> None:
    """Append a human-readable VALIDATION_ERRORS.txt to a failed DwC-A archive.

    The archive is left on disk so it can be persisted to storage for the user to
    download and inspect. The exporter still raises ValueError afterwards so the
    DataExport is marked failed.
    """
    import zipfile

    lines = ["DwC-A archive failed structural validation.", ""]
    lines.append(f"Errors ({len(validation.errors)}):")
    lines.extend(f"  - {e}" for e in validation.errors)
    if validation.warnings:
        lines.append("")
        lines.append(f"Warnings ({len(validation.warnings)}):")
        lines.extend(f"  - {w}" for w in validation.warnings)
    lines.append("")
    body = "\n".join(lines).encode("utf-8")

    with zipfile.ZipFile(zip_path, "a", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("VALIDATION_ERRORS.txt", body)


class DwCAExporter(BaseExporter):
    """Handles Darwin Core Archive (DwC-A) export with Event Core and Occurrence Extension."""

    file_format = "zip"
    filename_label = "dwca_draft-2026-04"

    DWCA_MAX_OCCURRENCES = 100_000

    def get_queryset(self):
        """Return the occurrence queryset (used by BaseExporter for record count).

        Applies the project's default filters (score threshold, include/exclude taxa).
        Low-confidence ML output is gated here to avoid publishing unreviewed
        classifications to downstream consumers (e.g. GBIF).

        Prefetches cover every reader downstream (occurrence.txt, multimedia.txt,
        measurementorfact.txt) so the queryset can be materialized to a list once
        in `export()` and reused without extra DB passes.
        """
        return (
            Occurrence.objects.valid()  # type: ignore[union-attr]
            .filter(project=self.project, event__isnull=False, determination__isnull=False)
            .apply_default_filters(self.project)  # type: ignore[union-attr]
            .select_related(
                "determination",
                "event",
                "deployment",
            )
            .prefetch_related(
                "detections__source_image",
                "detections__detection_algorithm",
                "detections__classifications__algorithm",
            )
            .with_detections_count()
            .with_identifications()
        )

    def get_events_queryset(self):
        from ami.main.models import Event

        event_ids = self.queryset.values_list("event_id", flat=True).distinct()
        return Event.objects.filter(
            project=self.project,
            id__in=event_ids,
        ).select_related(
            "deployment",
            "project",
        )

    def export(self):
        """Export project data as a Darwin Core Archive ZIP."""
        from django.utils.text import slugify

        from ami.exports.dwca import (
            EVENT_FIELDS,
            MOF_FIELDS,
            MULTIMEDIA_FIELDS,
            OCCURRENCE_FIELDS,
            create_dwca_zip,
            generate_eml_xml,
            generate_meta_xml,
            write_tsv,
        )
        from ami.exports.dwca.rows import iter_mof_rows, iter_multimedia_rows
        from ami.exports.dwca.targetscope import derive_target_taxonomic_scope

        project_slug = slugify(self.project.name)

        def _tmp_txt():
            tf = tempfile.NamedTemporaryFile(delete=False, suffix=".txt", mode="w", encoding="utf-8")
            tf.close()
            return tf.name

        event_path = _tmp_txt()
        occ_path = _tmp_txt()
        multimedia_path = _tmp_txt()
        mof_path = _tmp_txt()

        try:
            if self.total_records > self.DWCA_MAX_OCCURRENCES:
                raise ValueError(
                    f"DwC-A export refused: project has {self.total_records} occurrences, "
                    f"hard cap is {self.DWCA_MAX_OCCURRENCES}. The current exporter materializes "
                    f"the queryset in memory; streaming fan-out is planned as a follow-up."
                )

            events_qs = self.get_events_queryset()
            events_list = list(events_qs)
            target_scope = derive_target_taxonomic_scope(self.project)
            for e in events_list:
                e._target_taxonomic_scope = target_scope

            # Materialize the occurrence queryset once with all prefetches in place
            # so all three extension writers iterate the same in-memory list.
            occurrences_list = list(self.queryset)

            event_count = write_tsv(event_path, EVENT_FIELDS, events_list, project_slug)
            logger.info(f"DwC-A: wrote {event_count} events")

            occ_count = write_tsv(
                occ_path,
                OCCURRENCE_FIELDS,
                occurrences_list,
                project_slug,
                progress_callback=self.update_job_progress,
            )
            logger.info(f"DwC-A: wrote {occ_count} occurrences")

            mm_count = write_tsv(
                multimedia_path,
                MULTIMEDIA_FIELDS,
                iter_multimedia_rows(events_list, occurrences_list, project_slug),
                project_slug,
            )
            logger.info(f"DwC-A: wrote {mm_count} multimedia rows")

            mof_count = write_tsv(
                mof_path,
                MOF_FIELDS,
                iter_mof_rows(occurrences_list, project_slug),
                project_slug,
            )
            logger.info(f"DwC-A: wrote {mof_count} measurementOrFact rows")

            if self.total_records:
                self.update_job_progress(occ_count)

            meta_xml = generate_meta_xml(
                [
                    {
                        "role": "core",
                        "row_type": "http://rs.tdwg.org/dwc/terms/Event",
                        "filename": "event.txt",
                        "fields": EVENT_FIELDS,
                    },
                    {
                        "role": "extension",
                        "row_type": "http://rs.tdwg.org/dwc/terms/Occurrence",
                        "filename": "occurrence.txt",
                        "fields": OCCURRENCE_FIELDS,
                    },
                    {
                        "role": "extension",
                        "row_type": "http://rs.gbif.org/terms/1.0/Multimedia",
                        "filename": "multimedia.txt",
                        "fields": MULTIMEDIA_FIELDS,
                    },
                    {
                        "role": "extension",
                        "row_type": "http://rs.gbif.org/terms/1.0/MeasurementOrFact",
                        "filename": "measurementorfact.txt",
                        "fields": MOF_FIELDS,
                    },
                ]
            )
            eml_xml = generate_eml_xml(self.project, events_list)

            zip_path = create_dwca_zip(
                {
                    "event.txt": event_path,
                    "occurrence.txt": occ_path,
                    "multimedia.txt": multimedia_path,
                    "measurementorfact.txt": mof_path,
                },
                meta_xml,
                eml_xml,
            )

            from ami.exports.dwca_validator import validate_dwca_zip

            validation = validate_dwca_zip(zip_path)
            for warning in validation.warnings:
                logger.warning(f"DwC-A validation warning: {warning}")
            if not validation.ok:
                for err in validation.errors:
                    logger.error(f"DwC-A validation error: {err}")
                _append_validation_report_to_zip(zip_path, validation)
                try:
                    file_url = self.data_export.save_export_file(zip_path)
                    self.data_export.file_url = file_url
                    self.data_export.save(update_fields=["file_url"])
                except OSError as exc:
                    logger.error(f"Could not persist failed DwC-A archive for inspection: {exc}")
                raise ValueError(
                    f"DwC-A archive failed structural validation ({len(validation.errors)} errors). "
                    f"First: {validation.errors[0]}. "
                    f"See VALIDATION_ERRORS.txt inside the archive for the full report."
                )

            self.update_export_stats(file_temp_path=zip_path)
            return zip_path
        finally:
            for path in (event_path, occ_path, multimedia_path, mof_path):
                try:
                    os.unlink(path)
                except OSError:
                    pass
