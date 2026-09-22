"""
One row per detection of every occurrence (track) in scope, for taking tracks out as a benchmark.

The export format and the ``export_tracks`` management command both write through
``iter_track_rows()``, so ``TRACKS_CSV_COLUMNS`` is the single definition of the columns.
No user data is exported: a confirmed grouping carries its time, not who confirmed it.
"""

import csv
import datetime
import typing
from collections.abc import Callable, Iterator

from django.db import models
from django.db.models import Exists, F, OuterRef, Subquery

from ami.main.models import BEST_MACHINE_PREDICTION_ORDER, Classification, Detection, Occurrence

TRACKS_CSV_COLUMNS: typing.Final = (
    "occurrence_id",
    "detection_id",
    "event_id",
    "deployment_id",
    "source_image_id",
    "timestamp",
    "frame_index",
    "frame_count",
    "bbox_x1",
    "bbox_y1",
    "bbox_x2",
    "bbox_y2",
    "image_width",
    "image_height",
    "detection_label",
    "detection_score",
    "occurrence_determination",
    "occurrence_determination_score",
    "grouping_verified",
    "grouping_verified_at",
    "has_feature_vector",
    "next_detection_id",
)

DEFAULT_CHUNK_SIZE: typing.Final = 500


def _cell(value) -> str:
    """Render one value the way every tracks CSV writes it: blank for None, lowercase booleans."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, datetime.datetime):
        return value.isoformat()
    return str(value)


def _detections_for(occurrence_ids: list[int]) -> models.QuerySet:
    """Real detections of the given occurrences, in frame order, with their own best label."""
    best_classification = Classification.objects.filter(detection=OuterRef("pk")).order_by(
        *BEST_MACHINE_PREDICTION_ORDER
    )
    return (
        Detection.objects.valid()  # type: ignore[attr-defined]  Custom queryset method
        .filter(occurrence_id__in=occurrence_ids)
        .annotate(
            label=Subquery(best_classification.values("taxon__name")[:1]),
            label_score=Subquery(best_classification.values("score")[:1]),
            # Same notion as ClassificationQuerySet.with_has_features(), per detection.
            has_feature_vector=Exists(
                Classification.objects.filter(detection=OuterRef("pk"), features_2048__isnull=False)
            ),
        )
        .order_by("occurrence_id", F("source_image__timestamp").asc(nulls_last=True), "pk")
        .values(
            "pk",
            "occurrence_id",
            "bbox",
            "next_detection_id",
            "source_image_id",
            "source_image__timestamp",
            "source_image__width",
            "source_image__height",
            "source_image__event_id",
            "source_image__deployment_id",
            "label",
            "label_score",
            "has_feature_vector",
        )
    )


def iter_track_rows(
    occurrences: models.QuerySet[Occurrence],
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    on_chunk: Callable[[int], None] | None = None,
) -> Iterator[dict[str, str]]:
    """
    Yield one row per detection of each occurrence in ``occurrences``, keyed by TRACKS_CSV_COLUMNS.

    Occurrences are read in pk order, ``chunk_size`` at a time, with one detection query per
    chunk, so the query count grows with the number of chunks and never with the rows.
    ``on_chunk`` receives the running count of occurrences read, for progress reporting.
    """
    scope = (
        occurrences.order_by("pk")
        .values("pk", "determination__name", "determination_score", "grouping_verified_at")
        .distinct()  # A capture-set filter joins through detections and repeats occurrences.
    )
    occurrences_read = 0
    last_pk = 0
    while True:
        chunk = list(scope.filter(pk__gt=last_pk)[:chunk_size])
        if not chunk:
            break
        last_pk = chunk[-1]["pk"]
        occurrences_read += len(chunk)

        detections_by_occurrence: dict[int, list[dict]] = {}
        for detection in _detections_for([row["pk"] for row in chunk]):
            detections_by_occurrence.setdefault(detection["occurrence_id"], []).append(detection)

        for occurrence in chunk:
            detections = detections_by_occurrence.get(occurrence["pk"], [])
            verified_at = occurrence["grouping_verified_at"]
            for frame_index, detection in enumerate(detections):
                bbox = detection["bbox"]
                x1, y1, x2, y2 = bbox if isinstance(bbox, list) and len(bbox) == 4 else (None,) * 4
                yield {
                    "occurrence_id": _cell(occurrence["pk"]),
                    "detection_id": _cell(detection["pk"]),
                    "event_id": _cell(detection["source_image__event_id"]),
                    "deployment_id": _cell(detection["source_image__deployment_id"]),
                    "source_image_id": _cell(detection["source_image_id"]),
                    "timestamp": _cell(detection["source_image__timestamp"]),
                    "frame_index": _cell(frame_index),
                    "frame_count": _cell(len(detections)),
                    "bbox_x1": _cell(x1),
                    "bbox_y1": _cell(y1),
                    "bbox_x2": _cell(x2),
                    "bbox_y2": _cell(y2),
                    "image_width": _cell(detection["source_image__width"]),
                    "image_height": _cell(detection["source_image__height"]),
                    "detection_label": _cell(detection["label"]),
                    "detection_score": _cell(detection["label_score"]),
                    "occurrence_determination": _cell(occurrence["determination__name"]),
                    "occurrence_determination_score": _cell(occurrence["determination_score"]),
                    "grouping_verified": _cell(verified_at is not None),
                    "grouping_verified_at": _cell(verified_at),
                    "has_feature_vector": _cell(detection["has_feature_vector"]),
                    "next_detection_id": _cell(detection["next_detection_id"]),
                }

        if on_chunk:
            on_chunk(occurrences_read)
        if len(chunk) < chunk_size:
            break


def write_tracks_csv(
    occurrences: models.QuerySet[Occurrence],
    stream: typing.TextIO,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    on_chunk: Callable[[int], None] | None = None,
) -> int:
    """Write the header and every track row to ``stream``; return the number of detection rows."""
    writer = csv.DictWriter(stream, fieldnames=TRACKS_CSV_COLUMNS)
    writer.writeheader()
    rows = 0
    for row in iter_track_rows(occurrences, chunk_size=chunk_size, on_chunk=on_chunk):
        writer.writerow(row)
        rows += 1
    return rows
