"""Move detection feature vectors between Antenna databases without their ids.

A vector is worth GPU time to recompute, so when a project is re-imported the vectors
should follow it. Each vector is written next to the natural key of its detection
(``detection_matching.DetectionKey``) and the key and name of the algorithm that produced
it; on the way back in, the detections are found again by capture path and box and the
rows are written under the same algorithm.

Vectors live in two stores and an export carries both: ``DetectionEmbedding`` rows (an
extractor's vector for a detection, under a vector key) where that table exists, and the
backbone features a classifier stored on its own ``Classification`` rows
(``features_2048``), which is all older data has. The two have different lengths, so each
source gets its own matrix file; ``index.csv`` says which source every row came from.

Layout of an export directory: ``vectors.<source>.npy`` per source, ``index.csv`` (one line
per vector: source, row in that source's matrix, the detection's natural key) and
``manifest.json`` (format version, algorithm, vector key, per-source count and dimensions).
On import, embeddings become ``DetectionEmbedding`` rows and classifier features go back
onto the matching classification when the target has one; a feature vector whose detection
has no classification from that algorithm is reported as skipped. Both stores are optional
per branch: an export notes the ones it could not read in its manifest, and an import counts
rows it has nowhere to put instead of failing.
"""

from __future__ import annotations

import csv
import dataclasses
import datetime
import json
import logging
import pathlib
from collections import Counter
from collections.abc import Iterable, Iterator
from typing import Any

import numpy as np
from django.apps import apps
from django.core.exceptions import FieldDoesNotExist
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
INDEX_FILE = "index.csv"
MANIFEST_FILE = "manifest.json"
INDEX_COLUMNS = [
    "source",
    "row",
    "capture_path",
    "capture_timestamp",
    "deployment",
    "detector",
    "x1",
    "y1",
    "x2",
    "y2",
]
MATCH_CHUNK = 5000
WRITE_BATCH = 1000

# Where a vector was read from, and so where it is written back to.
SOURCE_EMBEDDING = "embedding"  # a DetectionEmbedding row
SOURCE_CLASSIFIER_FEATURES = "classifier_features"  # Classification.features_2048
SOURCES = (SOURCE_EMBEDDING, SOURCE_CLASSIFIER_FEATURES)
CLASSIFIER_FEATURES_FIELD = "features_2048"


def embedding_model() -> type[Model] | None:
    """The ``DetectionEmbedding`` model, or None on a branch that does not have it yet."""
    try:
        return apps.get_model("main", "DetectionEmbedding")
    except LookupError:
        return None


def _model_field_names(model: type[Model]) -> set[str]:
    return {field.name for field in model._meta.get_fields()}


def classifier_features_available() -> bool:
    """Whether classifications on this branch carry a feature vector (``features_2048``)."""
    try:
        Classification._meta.get_field(CLASSIFIER_FEATURES_FIELD)
    except FieldDoesNotExist:
        return False
    return True


def vectors_file(source: str) -> str:
    return f"vectors.{source}.npy"


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
    # Per source: {"file": ..., "count": ..., "dimensions": ...}
    sources: dict[str, dict]
    count: int
    dtype: str
    # Sources the exporting branch could not read, with the reason, so an empty source is not a surprise.
    skipped_sources: dict[str, str] = dataclasses.field(default_factory=dict)
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


def _embedding_rows(project: Project, algorithm: Algorithm, vector_key: str) -> Iterator[tuple[DetectionKey, Any]]:
    model = embedding_model()
    if model is None:
        return iter(())
    rows = model.objects.filter(detection__source_image__project=project, algorithm=algorithm)
    if "key" in _model_field_names(model):
        rows = rows.filter(key=vector_key)
    rows = rows.select_related("detection__source_image__deployment", "detection__detection_algorithm").order_by("pk")
    return ((DetectionKey.for_detection(row.detection), row.vector) for row in rows.iterator())


def _classifier_feature_rows(project: Project, algorithm: Algorithm) -> Iterator[tuple[DetectionKey, Any]]:
    """The newest feature vector the algorithm stored on each detection's classifications."""
    rows = (
        Classification.objects.filter(
            detection__source_image__project=project, algorithm=algorithm, features_2048__isnull=False
        )
        .select_related("detection__source_image__deployment", "detection__detection_algorithm")
        .order_by("detection_id", "-timestamp", "-pk")
        .distinct("detection_id")
    )
    return ((DetectionKey.for_detection(row.detection), row.features_2048) for row in rows.iterator())


def export_embeddings(
    project: Project,
    algorithm: Algorithm,
    directory: pathlib.Path,
    vector_key: str = DEFAULT_VECTOR_KEY,
    dtype: str = "float32",
) -> EmbeddingManifest:
    """Write one algorithm's vectors for ``project`` to ``directory``, from both stores.

    A detection with a vector in both stores appears twice in the index, once per source;
    within a source each detection appears once. Returns the manifest written.
    """
    directory.mkdir(parents=True, exist_ok=True)
    readers: dict[str, Iterator[tuple[DetectionKey, Any]]] = {}
    skipped: dict[str, str] = {}
    if embedding_model() is not None:
        readers[SOURCE_EMBEDDING] = _embedding_rows(project, algorithm, vector_key)
    else:
        skipped[SOURCE_EMBEDDING] = "this branch has no DetectionEmbedding table"
    if classifier_features_available():
        readers[SOURCE_CLASSIFIER_FEATURES] = _classifier_feature_rows(project, algorithm)
    else:
        skipped[
            SOURCE_CLASSIFIER_FEATURES
        ] = f"classifications on this branch have no {CLASSIFIER_FEATURES_FIELD} field"
    sources: dict[str, dict] = {}
    with (directory / INDEX_FILE).open("w", newline="") as index_file:
        writer = csv.writer(index_file)
        writer.writerow(INDEX_COLUMNS)
        for source, rows in readers.items():
            vectors: list[np.ndarray] = []
            for row, (key, vector) in enumerate(rows):
                # pgvector returns lists on some versions and arrays on others; np.asarray takes both.
                vectors.append(np.asarray(list(vector), dtype=dtype))
                writer.writerow(
                    [
                        source,
                        row,
                        key.capture_path,
                        key.capture_timestamp or "",
                        key.deployment or "",
                        key.detector or "",
                        *key.bbox,
                    ]
                )
            if not vectors:
                continue
            lengths = {len(v) for v in vectors}
            if len(lengths) > 1:
                raise ValueError(
                    f"Algorithm {algorithm.key} stored {source} vectors of several lengths {sorted(lengths)}; "
                    "export one at a time."
                )
            matrix = np.stack(vectors)
            np.save(directory / vectors_file(source), matrix)
            sources[source] = {"file": vectors_file(source), "count": len(vectors), "dimensions": int(matrix.shape[1])}
    manifest = EmbeddingManifest(
        algorithm_key=algorithm.key,
        algorithm_name=algorithm.name,
        vector_key=vector_key,
        sources=sources,
        count=sum(entry["count"] for entry in sources.values()),
        dtype=dtype,
        skipped_sources=skipped,
        project_name=project.name,
    )
    (directory / MANIFEST_FILE).write_text(json.dumps(manifest.as_dict(), indent=1))
    return manifest


@dataclasses.dataclass(frozen=True)
class IndexEntry:
    source: str
    row: int
    key: DetectionKey


def read_index(directory: pathlib.Path) -> list[IndexEntry]:
    entries = []
    with (directory / INDEX_FILE).open(newline="") as index_file:
        for line in csv.DictReader(index_file):
            if line["source"] not in SOURCES:
                raise ValueError(f"Unknown vector source {line['source']!r} in {INDEX_FILE}.")
            entries.append(
                IndexEntry(
                    source=line["source"],
                    row=int(line["row"]),
                    key=DetectionKey(
                        capture_path=line["capture_path"],
                        bbox=(float(line["x1"]), float(line["y1"]), float(line["x2"]), float(line["y2"])),
                        capture_timestamp=line["capture_timestamp"] or None,
                        deployment=line["deployment"] or None,
                        detector=line["detector"] or None,
                    ),
                )
            )
    return entries


def _chunks(items: list, size: int) -> Iterable[list]:
    for start in range(0, len(items), size):
        yield items[start : start + size]


@dataclasses.dataclass
class EmbeddingImportReport:
    entries: list[IndexEntry]
    matches: list[DetectionMatch]
    execute: bool = False
    written: Counter = dataclasses.field(default_factory=Counter)  # per source
    skipped_existing: Counter = dataclasses.field(default_factory=Counter)  # per source
    replaced: Counter = dataclasses.field(default_factory=Counter)  # per source
    # Classifier features whose detection has no classification from the algorithm on the target.
    skipped_no_classification: int = 0
    # Rows of a source the target branch has no column or table for.
    skipped_no_field: Counter = dataclasses.field(default_factory=Counter)  # per source

    def summary(self) -> dict:
        return {
            "mode": "execute" if self.execute else "dry-run",
            "vectors_total": len(self.entries),
            "sources": dict(Counter(entry.source for entry in self.entries)),
            "detections": dict(Counter(match.status for match in self.matches)),
            "written": dict(self.written),
            "skipped_existing": dict(self.skipped_existing),
            "replaced": dict(self.replaced),
            "skipped_no_classification": self.skipped_no_classification,
            "skipped_no_field": dict(self.skipped_no_field),
        }


def _load_matrix(directory: pathlib.Path, manifest: EmbeddingManifest, source: str) -> np.ndarray:
    entry = manifest.sources.get(source)
    if entry is None:
        raise ValueError(f"The manifest lists no {source} vectors but {INDEX_FILE} has rows of that source.")
    matrix = np.load(directory / entry["file"], mmap_mode="r")
    if matrix.shape[0] != entry["count"]:
        raise ValueError(f"{entry['file']} has {matrix.shape[0]} rows but the manifest says {entry['count']}.")
    return matrix


def _write_embeddings(
    project: Project,
    algorithm: Algorithm,
    vector_key: str,
    matrix: np.ndarray,
    found: list[tuple[int, int]],
    replace: bool,
    report: EmbeddingImportReport,
) -> None:
    """Store embedding rows, through the model's own insert-mostly writer where it has one.

    ``DetectionEmbedding.objects.store`` (the settled schema) leaves a row holding the same
    vector alone and replaces one holding a different vector, so ``replace`` is implied there.
    The draft table has no such writer; rows are compared by hand and ``replace`` decides.
    """
    model = embedding_model()
    if model is None:
        raise RuntimeError("This branch has no DetectionEmbedding table; embedding vectors cannot be imported here.")
    fields = _model_field_names(model)

    def build(row: int, detection_id: int):
        values: dict[str, Any] = {"detection_id": detection_id, "algorithm": algorithm, "vector": matrix[row].tolist()}
        # Fields the settled schema has; absent on the draft table.
        if "key" in fields:
            values["key"] = vector_key
        if "project" in fields:
            values["project"] = project
        return model(**values)

    store = getattr(model.objects, "store", None)
    for chunk in _chunks(found, WRITE_BATCH):
        if store is not None:
            inserted, unchanged = store(build(row, detection_id) for row, detection_id in chunk)
            report.written[SOURCE_EMBEDDING] += inserted
            report.skipped_existing[SOURCE_EMBEDDING] += unchanged
            continue
        detection_ids = [detection_id for _, detection_id in chunk]
        existing = model.objects.filter(detection_id__in=detection_ids, algorithm=algorithm)
        if "key" in fields:
            existing = existing.filter(key=vector_key)
        existing_ids = set(existing.values_list("detection_id", flat=True))
        if replace and existing_ids:
            existing.delete()
            report.replaced[SOURCE_EMBEDDING] += len(existing_ids)
        rows = [build(row, detection_id) for row, detection_id in chunk if detection_id not in existing_ids or replace]
        report.skipped_existing[SOURCE_EMBEDDING] += len(chunk) - len(rows)
        model.objects.bulk_create(rows, batch_size=WRITE_BATCH)
        report.written[SOURCE_EMBEDDING] += len(rows)


def _write_classifier_features(
    algorithm: Algorithm,
    matrix: np.ndarray,
    found: list[tuple[int, int]],
    replace: bool,
    report: EmbeddingImportReport,
) -> None:
    """Put each feature vector back on the newest classification the algorithm made of its detection."""
    for chunk in _chunks(found, WRITE_BATCH):
        detection_ids = [detection_id for _, detection_id in chunk]
        newest: dict[int, Classification] = {}
        for classification in (
            Classification.objects.filter(detection_id__in=detection_ids, algorithm=algorithm)
            .order_by("detection_id", "-timestamp", "-pk")
            .distinct("detection_id")
            .only("pk", "detection_id", "features_2048")
        ):
            newest[classification.detection_id] = classification
        to_update = []
        for row, detection_id in chunk:
            classification = newest.get(detection_id)
            if classification is None:
                report.skipped_no_classification += 1
                continue
            if classification.features_2048 is not None:
                if not replace:
                    report.skipped_existing[SOURCE_CLASSIFIER_FEATURES] += 1
                    continue
                report.replaced[SOURCE_CLASSIFIER_FEATURES] += 1
            classification.features_2048 = matrix[row].tolist()
            to_update.append(classification)
        Classification.objects.bulk_update(to_update, ["features_2048"], batch_size=WRITE_BATCH)
        report.written[SOURCE_CLASSIFIER_FEATURES] += len(to_update)


def import_embeddings(
    project: Project,
    directory: pathlib.Path,
    execute: bool = False,
    iou_threshold: float = DEFAULT_IOU_THRESHOLD,
    replace: bool = False,
    algorithm: Algorithm | None = None,
) -> EmbeddingImportReport:
    """Put the vectors in ``directory`` back on ``project``'s detections, each in its own store.

    Detections are found by natural key. A vector the target already holds (an embedding
    from the same algorithm and key, or a classification that already has features) is
    skipped unless ``replace`` is set. Rows of a source this branch has no table or column
    for are counted as ``skipped_no_field``. A dry run only matches.
    """
    manifest = EmbeddingManifest.read(directory)
    algorithm = algorithm or resolve_algorithm(manifest.algorithm_key)
    entries = read_index(directory)
    if len(entries) != manifest.count:
        raise ValueError(f"{INDEX_FILE} has {len(entries)} rows but the manifest says {manifest.count}.")
    # A detection with a vector in both stores appears twice in the index under one key. Match each
    # key once: the matcher claims a target detection for one key only, which is right between
    # different boxes and wrong between two rows of the same box.
    unique_keys = list(dict.fromkeys(entry.key for entry in entries))
    match_by_key: dict[DetectionKey, DetectionMatch] = {}
    for chunk in _chunks(unique_keys, MATCH_CHUNK):
        for match in match_detections(project, chunk, iou_threshold):
            match_by_key[match.key] = match
    matches = [match_by_key[entry.key] for entry in entries]
    report = EmbeddingImportReport(entries=entries, matches=matches, execute=execute)
    if not execute:
        return report

    found_by_source: dict[str, list[tuple[int, int]]] = {source: [] for source in SOURCES}
    for entry, match in zip(entries, matches):
        if match.found:
            found_by_source[entry.source].append((entry.row, match.detection_id))
    if found_by_source[SOURCE_EMBEDDING]:
        if embedding_model() is None:
            report.skipped_no_field[SOURCE_EMBEDDING] += len(found_by_source[SOURCE_EMBEDDING])
        else:
            matrix = _load_matrix(directory, manifest, SOURCE_EMBEDDING)
            _write_embeddings(
                project, algorithm, manifest.vector_key, matrix, found_by_source[SOURCE_EMBEDDING], replace, report
            )
    if found_by_source[SOURCE_CLASSIFIER_FEATURES]:
        if not classifier_features_available():
            report.skipped_no_field[SOURCE_CLASSIFIER_FEATURES] += len(found_by_source[SOURCE_CLASSIFIER_FEATURES])
        else:
            matrix = _load_matrix(directory, manifest, SOURCE_CLASSIFIER_FEATURES)
            _write_classifier_features(algorithm, matrix, found_by_source[SOURCE_CLASSIFIER_FEATURES], replace, report)
    return report
