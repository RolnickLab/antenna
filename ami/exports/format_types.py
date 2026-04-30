import csv
import datetime
import json
import logging
import os
import tempfile

from django.conf import settings
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

    def get_best_detection_source_image_id(self, obj):
        """Returns the source image id for the best detection."""
        return getattr(obj, "best_detection_source_image_id", None)

    def get_best_detection_capture_timestamp(self, obj):
        """Returns the capture timestamp for the best detection source image."""
        return getattr(obj, "best_detection_capture_timestamp", None)

    def get_best_detection_capture_path(self, obj):
        """Returns the capture path for the best detection source image."""
        return getattr(obj, "best_detection_capture_path", None)

    def get_best_detection_capture_width(self, obj):
        """Returns the capture width for the best detection source image."""
        return getattr(obj, "best_detection_capture_width", None)

    def get_best_detection_capture_height(self, obj):
        """Returns the capture height for the best detection source image."""
        return getattr(obj, "best_detection_capture_height", None)

    def get_best_detection_capture_url(self, obj):
        """Returns the public URL to the source capture (original full-frame image).

        Built from annotated `path` + `public_base_url` to avoid loading the
        capture (SourceImage) row per occurrence; presigned URLs for private
        buckets aren't supported here for the same reason.
        """
        path = self.get_best_detection_capture_path(obj)
        base_url = getattr(obj, "best_detection_capture_public_base_url", None)
        if path and base_url:
            return SourceImage.build_public_url(base_url, path)
        return None


class OccurrenceCocoTabularSerializer(OccurrenceTabularSerializer):
    """CSV-shaped occurrence row plus SourceImage metadata for COCO exports."""

    # Best detection SourceImage fields
    source_image_id = serializers.SerializerMethodField()
    capture_timestamp = serializers.SerializerMethodField()
    capture_path = serializers.SerializerMethodField()
    capture_width = serializers.SerializerMethodField()
    capture_height = serializers.SerializerMethodField()

    class Meta(OccurrenceTabularSerializer.Meta):
        fields = OccurrenceTabularSerializer.Meta.fields + [
            "source_image_id",
            "capture_timestamp",
            "capture_path",
            "capture_width",
            "capture_height",
        ]

    def get_source_image_id(self, obj):
        return self.get_best_detection_source_image_id(obj)

    def get_capture_timestamp(self, obj):
        ts = self.get_best_detection_capture_timestamp(obj)
        if ts is None:
            return None
        return ts.isoformat() if hasattr(ts, "isoformat") else str(ts)

    def get_capture_path(self, obj):
        return self.get_best_detection_capture_path(obj)

    def get_capture_width(self, obj):
        return self.get_best_detection_capture_width(obj)

    def get_capture_height(self, obj):
        return self.get_best_detection_capture_height(obj)


def corner_bbox_to_coco_bbox(corner: list | None) -> tuple[list[float], float] | None:
    """Convert [x1, y1, x2, y2] to COCO [x, y, width, height] and area."""
    bbox = BoundingBox.from_coords(corner, raise_on_error=False)
    if bbox is None:
        return None
    w, h = bbox.width, bbox.height
    if w is None or h is None or w <= 0 or h <= 0:
        return None
    return [float(bbox.x1), float(bbox.y1), float(w), float(h)], float(w * h)


def build_coco_dict_from_occurrence_rows(rows: list[dict], project) -> dict:
    """Build a COCO-style detection dict from serialized occurrence rows (determination categories only)."""
    categories_by_id: dict[int, dict] = {}
    images_by_id: dict[int, dict] = {}
    annotations: list[dict] = []

    for row in rows:
        determination_id = row.get("determination_id")
        if determination_id is None:
            logger.warning(f"No determination_id found for row: {row}")
            continue

        coco_result = corner_bbox_to_coco_bbox(row.get("best_detection_bbox"))
        if coco_result is None:
            logger.warning(f"No coco_bbox found for row: {row}")
            continue

        coco_bbox, area = coco_result
        source_image_id = row.get("source_image_id")
        if source_image_id is None:
            logger.warning(f"No source_image_id found for row: {row}")
            continue

        det_name = row.get("determination_name") or ""
        if int(determination_id) not in categories_by_id:
            categories_by_id[int(determination_id)] = {
                "id": int(determination_id),
                "name": det_name,
            }
        else:
            assert (
                categories_by_id[int(determination_id)]["name"] == det_name
            ), f"Determination name mismatch for id: {determination_id}"

        if source_image_id not in images_by_id:
            cap_path = row.get("capture_path") or ""
            images_by_id[int(source_image_id)] = {
                "id": int(source_image_id),
                "file_name": os.path.basename(cap_path) if cap_path else "",
                "width": row.get("capture_width"),
                "height": row.get("capture_height"),
                "coco_url": row.get("best_detection_capture_url"),
                "date_captured": row.get("capture_timestamp"),
            }

        occ_id = row.get("id")
        if occ_id is None:
            logger.warning(f"No occ_id found for row: {row}")
            continue

        ann: dict = {
            "id": int(occ_id),
            "image_id": int(source_image_id),
            "category_id": int(determination_id),
            "bbox": coco_bbox,
            "area": area,
            "iscrowd": 0,  # TODO: Could we use this field to indiate crowd of insects?
            "determination_score": row.get("determination_score"),
            "verification_status": row.get("verification_status"),
            "best_machine_prediction_name": row.get("best_machine_prediction_name"),
            "best_machine_prediction_algorithm": row.get("best_machine_prediction_algorithm"),
            "best_machine_prediction_score": row.get("best_machine_prediction_score"),
            "determination_matches_machine_prediction": row.get("determination_matches_machine_prediction"),
            "best_detection_width": row.get("best_detection_width"),
            "best_detection_height": row.get("best_detection_height"),
        }
        annotations.append(ann)

    base = getattr(settings, "EXTERNAL_BASE_URL", "") or ""
    info_url = ""
    if base.strip():
        info_url = f"{base.rstrip('/')}/projects/{project.pk}/summary"  # TODO: is there a better way to do this?

    payload = {
        "info": {
            "description": f"{project.name} ({project.pk}) Occurrences",
            "url": info_url,
            "date_created": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        },
        "images": list(images_by_id.values()),
        "annotations": annotations,
        "categories": sorted(categories_by_id.values(), key=lambda c: c["id"]),
    }
    return payload


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


class CocoJSONExporter(BaseExporter):
    """Exports occurrences as a COCO-style detection dataset (same rows as CSV plus capture metadata)."""

    file_format = "json"

    serializer_class = OccurrenceCocoTabularSerializer

    def get_queryset(self):
        return (
            Occurrence.objects.valid()
            .filter(project=self.project)
            .select_related(
                "determination",
                "deployment",
                "event",
            )
            .with_timestamps()
            .with_detections_count()
            .with_identifications()
            .with_best_detection()
            .with_best_machine_prediction()
            .with_verification_info()
        )

    def export(self):
        """Serialize occurrences in batches, build COCO JSON, write to a temp file."""
        rows: list[dict] = []
        records_exported = 0
        for batch in get_data_in_batches(self.queryset, self.serializer_class):
            rows.extend(batch)
            records_exported += len(batch)
            self.update_job_progress(records_exported)

        coco_payload = build_coco_dict_from_occurrence_rows(rows, self.project)

        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".json", mode="w", encoding="utf-8")
        with open(temp_file.name, "w", encoding="utf-8") as f:
            json.dump(coco_payload, f, cls=DjangoJSONEncoder)

        self.update_export_stats(file_temp_path=temp_file.name)
        return temp_file.name
