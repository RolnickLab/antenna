import csv
import json
import logging
import os
import tempfile

from django.core.serializers.json import DjangoJSONEncoder
from rest_framework import serializers

from ami.exports.base import BaseExporter
from ami.exports.taxa_list import COLUMN_ORDER as TAXA_LIST_COLUMNS
from ami.exports.taxa_list import TaxonAccumulator, empty_row_for_taxon, row_for_taxon
from ami.exports.utils import get_data_in_batches
from ami.main.models import Occurrence, SourceImage, Taxon, get_media_url
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


class TaxaListCSVExporter(BaseExporter):
    """Export the unique taxa observed in a SourceImageCollection as a CSV.

    One row per `Taxon` that appears as the `determination` of at least one
    valid occurrence (after applying the project's default filters) within the
    selected collection. Aggregations cover occurrence count, classification
    score, occurrence date, and time-of-night.

    Future hooks (intentionally stubbed; see project design doc):

    1. **Absence rows.** When a project declares an explicit "taxonomic scope"
       (today: `Project.default_filters_include_taxa` recursively expanded;
       eventually a per-Project default `TaxaList`, and per-Site `TaxaList`
       for the deployment-level case), this exporter will emit a row per
       scope-taxon that was not observed, with `direct_occurrences_count = 0`.
       That turns the file into a presence/absence checklist. Wired via
       `_get_expected_taxa()`; v1 returns nothing so the column shape is
       stable when absence rows turn on.

    2. **Darwin Core Taxon-Core archive variant.** A sibling `taxa_list_dwca`
       format can ship later by reusing this aggregator + Taxon fetch and
       emitting a DwC `taxon.txt` (plus `meta.xml` / `eml.xml`) zip instead of
       a flat CSV. The columns this format produces are intentionally a
       superset of DwC Taxon-Core fields. See PR #1131 for the surrounding
       DwC-A export and `targetscope.derive_target_taxonomic_scope` for the
       expected-taxa derivation.
    """

    file_format = "csv"
    filename_label = "taxa_list"

    def __init__(self, data_export):
        super().__init__(data_export)
        # The base class's `total_records` counts occurrences, but each output
        # row is one taxon. Reset progress denominators so the percentage
        # tracks the file we're actually writing.
        unique_taxa_count = (
            self.queryset.filter(determination__isnull=False).values("determination_id").distinct().count()
        )
        self.total_records = unique_taxa_count
        if self.job:
            self.job.progress.add_or_update_stage_param(
                self.job.job_type_key, "Total records to export", self.total_records
            )
            self.job.save()

    def get_queryset(self):
        """Filtered occurrence queryset.

        We start from the Occurrence model (not Taxon) so the existing
        `OccurrenceCollectionFilter` filter backend can scope to the user's
        selected collection. The taxa set is derived from this queryset's
        `determination_id` column during `export()`.
        """
        return (
            Occurrence.objects.valid()  # type: ignore[union-attr]  Custom queryset method
            .filter(project=self.project, determination__isnull=False)
            .apply_default_filters(self.project)  # type: ignore[union-attr]  Custom queryset method
            .with_timestamps()  # type: ignore[union-attr]  Custom queryset method
        )

    def _get_expected_taxa(self):
        """Return the taxa expected to be observable in this project.

        Stub for the future "absence rows" feature. Currently returns an empty
        queryset, so v1 only emits rows for taxa actually observed. When a
        project gets a populated taxonomic scope (any of:
          - `Project.default_filters_include_taxa`, recursively expanded via
            `parents_json__contains`,
          - a per-project default TaxaList,
          - a per-Site TaxaList),
        this method will be updated to return that set, and the writer below
        will emit zero-count rows for any expected taxon not in the observed
        accumulator.
        """
        return Taxon.objects.none()

    def update_export_stats(self, file_temp_path=None):
        """Override base behaviour: report the number of CSV rows we actually
        wrote (one per unique taxon), not the occurrence count from the source
        queryset.
        """
        self.data_export.record_count = self._rows_written
        if file_temp_path and os.path.exists(file_temp_path):
            self.data_export.file_size = os.path.getsize(file_temp_path)
        self.data_export.save()

    def export(self):
        """Stream filtered occurrences once, aggregate per-taxon, write CSV."""
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".csv", mode="w", newline="", encoding="utf-8")

        # Streaming pass: build per-taxon accumulators.
        accumulators: dict[int, TaxonAccumulator] = {}
        occurrence_values = self.queryset.values(
            "determination_id",
            "determination_score",
            "first_appearance_timestamp",
            "last_appearance_timestamp",
        )
        for occ in occurrence_values.iterator(chunk_size=500):
            det_id = occ["determination_id"]
            if det_id is None:
                continue
            accum = accumulators.get(det_id)
            if accum is None:
                accum = TaxonAccumulator()
                accumulators[det_id] = accum
            accum.add(
                score=occ.get("determination_score"),
                first_dt=occ.get("first_appearance_timestamp"),
                last_dt=occ.get("last_appearance_timestamp"),
            )

        # Fetch taxon rows in a single query, ordered by name for stable output.
        observed_taxa = list(Taxon.objects.filter(id__in=accumulators.keys()).order_by("name"))

        # Future absence rows: any expected taxon not in `accumulators` would
        # be emitted with a zero-count placeholder row. v1 returns an empty
        # queryset so this loop is a no-op.
        observed_ids = set(accumulators.keys())
        absent_taxa = list(self._get_expected_taxa().exclude(id__in=observed_ids).order_by("name"))

        records_exported = 0
        with open(temp_file.name, "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=TAXA_LIST_COLUMNS)
            writer.writeheader()

            for taxon in observed_taxa:
                row = row_for_taxon(taxon, accumulators[taxon.pk])
                writer.writerow(row)
                records_exported += 1
                self.update_job_progress(records_exported)

            for taxon in absent_taxa:
                writer.writerow(empty_row_for_taxon(taxon))
                records_exported += 1
                self.update_job_progress(records_exported)

        self._rows_written = records_exported
        self.update_export_stats(file_temp_path=temp_file.name)
        return temp_file.name
