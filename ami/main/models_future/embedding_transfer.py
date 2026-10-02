"""Move detection feature vectors between Antenna databases without their ids.

A vector is worth GPU time to recompute, so when a project is re-imported the vectors
should follow it. Each vector is written next to the natural key of its detection
(``detection_matching.DetectionKey``) and the key and name of the algorithm that produced
it; on the way back in, the detections are found again by capture path and box and the
rows are written under the same algorithm.

Layout of an export directory: ``vectors.npy`` (one row per vector), ``index.csv`` (one line
per row, the detection's natural key) and ``manifest.json`` (format version, algorithm,
vector key, dimensions, count, dtype). Vectors are read from ``DetectionEmbedding`` rows
when that table exists on this branch, otherwise from the classification vectors
(``Classification.features_2048``) the same algorithm stored, which is all older data has.
Writing always targets ``DetectionEmbedding`` and refuses when the table does not exist.
"""

from __future__ import annotations

import csv
import dataclasses
import datetime
import json
import logging
import pathlib
from collections.abc import Iterable, Iterator
from typing import Any

import numpy as np
from django.apps import apps
from django.db.models import Model

from ami.main.models import Classification, Project
from ami.main.models_future.detection_matching import (
    DEFAULT_IOU_THRESHOLD,
    DetectionKey,
    DetectionMatch,
    match_detections,
)
from ami.ml.models import Algorithm

logger = logging.getLogger(__name__)

EMBEDDINGS_FORMAT = "antenna-detection-embeddings"
EMBEDDINGS_VERSION = 1
DEFAULT_VECTOR_KEY = "embedding"
VECTORS_FILE = "vectors.npy"
INDEX_FILE = "index.csv"
MANIFEST_FILE = "manifest.json"
INDEX_COLUMNS = ["row", "capture_path", "capture_timestamp", "deployment", "detector", "x1", "y1", "x2", "y2"]
MATCH_CHUNK = 5000
WRITE_BATCH = 1000


def embedding_model() -> type[Model] | None:
    """The ``DetectionEmbedding`` model, or None on a branch that does not have it yet."""
    try:
        return apps.get_model("main", "DetectionEmbedding")
    except LookupError:
        return None


def _model_field_names(model: type[Model]) -> set[str]:
    return {field.name for field in model._meta.get_fields()}


def resolve_algorithm(reference: str) -> Algorithm:
    """An algorithm by key, then by name, then by id."""
    algorithm = Algorithm.objects.filter(key=reference).first() or Algorithm.objects.filter(name=reference).first()
    if algorithm is None and reference.isdigit():
        algorithm = Algorithm.objects.filter(pk=int(reference)).first()
    if algorithm is None:
        raise Algorithm.DoesNotExist(f"No algorithm with key, name or id {reference!r}.")
    return algorithm


@dataclasses.dataclass
class EmbeddingManifest:
    algorithm_key: str
    algorithm_name: str
    vector_key: str
    dimensions: int
    count: int
    dtype: str
    source_store: str
    project_name: str | None = None
    exported_at: str = dataclasses.field(default_factory=lambda: datetime.datetime.now().isoformat())
    version: int = EMBEDDINGS_VERSION

    def as_dict(self) -> dict:
        return {"format": EMBEDDINGS_FORMAT, **dataclasses.asdict(self)}

    @classmethod
    def read(cls, directory: pathlib.Path) -> EmbeddingManifest:
        data = json.loads((directory / MANIFEST_FILE).read_text())
        if data.get("format") != EMBEDDINGS_FORMAT:
            raise ValueError(f"{directory} is not a {EMBEDDINGS_FORMAT} export.")
        if int(data.get("version", 0)) > EMBEDDINGS_VERSION:
            raise ValueError(f"Export version {data['version']} is newer than this code understands.")
        data.pop("format")
        return cls(**data)


def _vector_rows(
    project: Project, algorithm: Algorithm, vector_key: str
) -> tuple[str, Iterator[tuple[DetectionKey, Any]]]:
    """(store name, iterator of (detection key, vector)) for one algorithm's vectors in a project."""
    model = embedding_model()
    if model is not None:
        rows = model.objects.filter(detection__source_image__project=project, algorithm=algorithm)
        if "key" in _model_field_names(model):
            rows = rows.filter(key=vector_key)
        rows = rows.select_related("detection__source_image__deployment", "detection__detection_algorithm").order_by(
            "pk"
        )
        return "detection_embedding", (
            (DetectionKey.for_detection(row.detection), row.vector) for row in rows.iterator()
        )

    # Older data: the classifier's backbone vector lives on the classification. Newest per detection.
    rows = (
        Classification.objects.filter(
            detection__source_image__project=project, algorithm=algorithm, features_2048__isnull=False
        )
        .select_related("detection__source_image__deployment", "detection__detection_algorithm")
        .order_by("detection_id", "-timestamp", "-pk")
        .distinct("detection_id")
    )
    return "classification_features", (
        (DetectionKey.for_detection(row.detection), row.features_2048) for row in rows.iterator()
    )


def export_embeddings(
    project: Project,
    algorithm: Algorithm,
    directory: pathlib.Path,
    vector_key: str = DEFAULT_VECTOR_KEY,
    dtype: str = "float32",
) -> EmbeddingManifest:
    """Write one algorithm's vectors for ``project`` to ``directory``; returns the manifest written."""
    directory.mkdir(parents=True, exist_ok=True)
    store, rows = _vector_rows(project, algorithm, vector_key)
    vectors: list[np.ndarray] = []
    with (directory / INDEX_FILE).open("w", newline="") as index_file:
        writer = csv.writer(index_file)
        writer.writerow(INDEX_COLUMNS)
        for row, (key, vector) in enumerate(rows):
            # pgvector returns lists on some versions and arrays on others; np.asarray takes both.
            vectors.append(np.asarray(list(vector), dtype=dtype))
            writer.writerow(
                [
                    row,
                    key.capture_path,
                    key.capture_timestamp or "",
                    key.deployment or "",
                    key.detector or "",
                    *key.bbox,
                ]
            )
    if vectors:
        lengths = {len(v) for v in vectors}
        if len(lengths) > 1:
            raise ValueError(
                f"Algorithm {algorithm.key} stored vectors of several lengths {sorted(lengths)}; export one at a time."
            )
        matrix = np.stack(vectors)
    else:
        matrix = np.zeros((0, 0), dtype=dtype)
    np.save(directory / VECTORS_FILE, matrix)
    manifest = EmbeddingManifest(
        algorithm_key=algorithm.key,
        algorithm_name=algorithm.name,
        vector_key=vector_key,
        dimensions=int(matrix.shape[1]) if matrix.size else 0,
        count=int(matrix.shape[0]),
        dtype=dtype,
        source_store=store,
        project_name=project.name,
    )
    (directory / MANIFEST_FILE).write_text(json.dumps(manifest.as_dict(), indent=1))
    return manifest


def read_index(directory: pathlib.Path) -> list[DetectionKey]:
    keys = []
    with (directory / INDEX_FILE).open(newline="") as index_file:
        for line in csv.DictReader(index_file):
            keys.append(
                DetectionKey(
                    capture_path=line["capture_path"],
                    bbox=(float(line["x1"]), float(line["y1"]), float(line["x2"]), float(line["y2"])),
                    capture_timestamp=line["capture_timestamp"] or None,
                    deployment=line["deployment"] or None,
                    detector=line["detector"] or None,
                )
            )
    return keys


def _chunks(items: list, size: int) -> Iterable[list]:
    for start in range(0, len(items), size):
        yield items[start : start + size]


@dataclasses.dataclass
class EmbeddingImportReport:
    matches: list[DetectionMatch]
    written: int = 0
    skipped_existing: int = 0
    replaced: int = 0
    execute: bool = False

    def summary(self) -> dict:
        from collections import Counter

        counts = Counter(match.status for match in self.matches)
        return {
            "mode": "execute" if self.execute else "dry-run",
            "vectors_total": len(self.matches),
            "detections": dict(counts),
            "written": self.written,
            "skipped_existing": self.skipped_existing,
            "replaced": self.replaced,
        }


def import_embeddings(
    project: Project,
    directory: pathlib.Path,
    execute: bool = False,
    iou_threshold: float = DEFAULT_IOU_THRESHOLD,
    replace: bool = False,
    algorithm: Algorithm | None = None,
) -> EmbeddingImportReport:
    """Write the vectors in ``directory`` as ``DetectionEmbedding`` rows on ``project``'s detections.

    Detections are found by natural key. A detection that already has a vector from the
    same algorithm (and key) is skipped unless ``replace`` is set. A dry run only matches.
    """
    manifest = EmbeddingManifest.read(directory)
    algorithm = algorithm or resolve_algorithm(manifest.algorithm_key)
    keys = read_index(directory)
    if len(keys) != manifest.count:
        raise ValueError(f"{INDEX_FILE} has {len(keys)} rows but the manifest says {manifest.count}.")
    matches: list[DetectionMatch] = []
    for chunk in _chunks(keys, MATCH_CHUNK):
        matches.extend(match_detections(project, chunk, iou_threshold))
    report = EmbeddingImportReport(matches=matches, execute=execute)
    if not execute:
        return report

    model = embedding_model()
    if model is None:
        raise RuntimeError("This branch has no DetectionEmbedding table; vectors cannot be imported here.")
    fields = _model_field_names(model)
    matrix = np.load(directory / VECTORS_FILE, mmap_mode="r")
    if matrix.shape[0] != manifest.count:
        raise ValueError(f"{VECTORS_FILE} has {matrix.shape[0]} rows but the manifest says {manifest.count}.")

    found = [(row, match.detection_id) for row, match in enumerate(matches) if match.found]
    for chunk in _chunks(found, WRITE_BATCH):
        detection_ids = [detection_id for _, detection_id in chunk]
        existing = model.objects.filter(detection_id__in=detection_ids, algorithm=algorithm)
        if "key" in fields:
            existing = existing.filter(key=manifest.vector_key)
        existing_ids = set(existing.values_list("detection_id", flat=True))
        if replace and existing_ids:
            existing.delete()
            report.replaced += len(existing_ids)
        rows = []
        for row, detection_id in chunk:
            if detection_id in existing_ids and not replace:
                report.skipped_existing += 1
                continue
            values: dict[str, Any] = {
                "detection_id": detection_id,
                "algorithm": algorithm,
                "vector": matrix[row].tolist(),
            }
            # Fields the settled schema adds; absent on the draft table.
            if "key" in fields:
                values["key"] = manifest.vector_key
            if "project" in fields:
                values["project"] = project
            rows.append(model(**values))
        model.objects.bulk_create(rows, batch_size=WRITE_BATCH)
        report.written += len(rows)
    return report
