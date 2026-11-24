"""
Export the verified species detections of every project that opted in, as Parquet files.

One snapshot is a folder in storage:

- ``manifest.parquet``: one row per detection under a verified occurrence, with its label,
  split, box, crop and capture locations. No vectors.
- ``vectors/algorithm=<key>/part-00000.parquet``: ``detection_id`` and ``vector`` for one
  algorithm. Vectors of different algorithms are in different spaces, so each has its own file.
- ``metadata.json``: the selection rules, the projects and the counts.

A project opts in with the ``share_verified_data_for_training`` feature flag. The rows follow
the same rule as ``verified_occurrence_ids`` in ``ami.ml.training.dataset``.
"""

import collections
import json
import logging
import pathlib
import tempfile
import typing

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
from django.conf import settings
from django.core.files.storage import default_storage
from django.db import connection
from django.db.models import Count, F, OuterRef, QuerySet, Subquery
from django.utils import timezone
from django.utils.text import slugify

from ami.main.models import Detection, Identification, Project, SourceImage, TaxonRank, get_media_url
from ami.ml.models.algorithm import Algorithm
from ami.ml.models.embedding import DetectionEmbedding
from ami.ml.models.training_data import TrainingDataSnapshot, TrainingDataSnapshotProject, TrainingDataSnapshotStatus
from ami.ml.training.dataset import DEFAULT_SPLIT_SALT, DEFAULT_TEST_FRACTION, _vector_as_array, split_for

logger = logging.getLogger(__name__)

SNAPSHOT_DIRECTORY = "training-data"
SCHEMA_VERSION = 1
# Rows read from the database per round trip, and rows per Parquet row group.
FETCH_CHUNK_SIZE = 5000
ROW_GROUP_SIZE = 50_000
# Any value: it only has to differ from the other advisory locks in the app.
EXPORT_LOCK_KEY = 7_401_001

MANIFEST_SCHEMA = pa.schema(
    [
        ("detection_id", pa.int64()),
        ("occurrence_id", pa.int64()),
        ("source_image_id", pa.int64()),
        ("deployment_id", pa.int64()),
        ("project_id", pa.int64()),
        ("site_id", pa.int64()),
        ("device_id", pa.int64()),
        ("taxon_id", pa.int64()),
        ("taxon_name", pa.string()),
        ("taxon_rank", pa.string()),
        ("identification_id", pa.int64()),
        ("identified_at", pa.timestamp("us")),
        ("split", pa.string()),
        ("bbox", pa.list_(pa.float32())),
        ("captured_at", pa.timestamp("us")),
        ("crop_url", pa.string()),
        ("capture_path", pa.string()),
        ("capture_url", pa.string()),
    ]
)


class SnapshotAlreadyRunning(Exception):
    """Another export holds the lock. Two exports at once would double the database load."""


def shared_project_ids() -> list[int]:
    """Projects whose managers opted in to share verified data for training."""
    projects = Project.objects.only("pk", "feature_flags").order_by("pk")
    return [p.pk for p in projects if p.feature_flags.share_verified_data_for_training]


def verified_identifications(project_ids: typing.Collection[int]) -> QuerySet:
    """
    Identifications that make an occurrence a training example: not withdrawn, and the
    occurrence determined to a species. Same rule as ``dataset.verified_occurrence_ids``.
    """
    return Identification.objects.filter(
        withdrawn=False,
        occurrence__project_id__in=project_ids,
        occurrence__determination__isnull=False,
        occurrence__determination__rank=TaxonRank.SPECIES.name,
    ).order_by()


def verified_detections(project_ids: typing.Collection[int]) -> QuerySet:
    """One dict per detection under a verified occurrence, in detection order."""
    latest = Identification.objects.filter(occurrence_id=OuterRef("occurrence_id"), withdrawn=False).order_by(
        "-created_at", "-pk"
    )
    return (
        Detection.objects.filter(
            occurrence_id__in=verified_identifications(project_ids).values("occurrence_id"),
        )
        .annotate(
            identification_id=Subquery(latest.values("pk")[:1]),
            identified_at=Subquery(latest.values("created_at")[:1]),
        )
        .order_by("pk")
        .values(
            "pk",
            "occurrence_id",
            "source_image_id",
            "bbox",
            "path",
            "identification_id",
            "identified_at",
            deployment_id=F("source_image__deployment_id"),
            project_id=F("occurrence__project_id"),
            site_id=F("source_image__deployment__research_site_id"),
            device_id=F("source_image__deployment__device_id"),
            taxon_id=F("occurrence__determination_id"),
            taxon_name=F("occurrence__determination__name"),
            taxon_rank=F("occurrence__determination__rank"),
            captured_at=F("source_image__timestamp"),
            capture_path=F("source_image__path"),
            capture_base_url=F("source_image__public_base_url"),
        )
    )


def _bbox(value) -> list[float] | None:
    if isinstance(value, (list, tuple)) and len(value) == 4:
        try:
            return [float(v) for v in value]
        except (TypeError, ValueError):
            return None
    return None


def _manifest_record(row: dict, salt: str, test_fraction: float) -> dict:
    capture_path = row["capture_path"]
    base_url = row["capture_base_url"]
    return {
        "detection_id": row["pk"],
        "occurrence_id": row["occurrence_id"],
        "source_image_id": row["source_image_id"],
        "deployment_id": row["deployment_id"],
        "project_id": row["project_id"],
        "site_id": row["site_id"],
        "device_id": row["device_id"],
        "taxon_id": row["taxon_id"],
        "taxon_name": row["taxon_name"],
        "taxon_rank": row["taxon_rank"],
        "identification_id": row["identification_id"],
        "identified_at": row["identified_at"],
        "split": split_for(row["occurrence_id"], salt, test_fraction),
        "bbox": _bbox(row["bbox"]),
        "captured_at": row["captured_at"],
        "crop_url": get_media_url(row["path"]) if row["path"] else None,
        "capture_path": capture_path,
        # Public URLs only: a presigned URL expires long before the snapshot is read.
        "capture_url": SourceImage.build_public_url(base_url, capture_path) if base_url and capture_path else None,
    }


def write_manifest(path: pathlib.Path, project_ids: list[int], salt: str, test_fraction: float) -> dict[int, int]:
    """Stream the manifest to ``path``. Returns the number of rows per project."""
    rows_per_project: collections.Counter[int] = collections.Counter()
    buffer: list[dict] = []
    with pq.ParquetWriter(path, MANIFEST_SCHEMA) as writer:
        for row in verified_detections(project_ids).iterator(chunk_size=FETCH_CHUNK_SIZE):
            record = _manifest_record(row, salt, test_fraction)
            rows_per_project[record["project_id"]] += 1
            buffer.append(record)
            if len(buffer) >= ROW_GROUP_SIZE:
                writer.write_table(pa.Table.from_pylist(buffer, schema=MANIFEST_SCHEMA))
                buffer = []
        if buffer or not rows_per_project:
            # An empty manifest still gets its schema, so a reader never meets a missing file.
            writer.write_table(pa.Table.from_pylist(buffer, schema=MANIFEST_SCHEMA))
    return dict(rows_per_project)


def exported_algorithms(project_ids: list[int]) -> list[Algorithm]:
    """Algorithms with at least one stored vector in the shared projects."""
    with_vectors = DetectionEmbedding.objects.filter(project_id__in=project_ids).values("algorithm_id")
    return list(Algorithm.objects.filter(pk__in=with_vectors).order_by("pk"))


def write_vectors(path: pathlib.Path, algorithm: Algorithm, project_ids: list[int]) -> dict[str, int]:
    """
    Stream one algorithm's vectors for the manifest's detections to ``path``.

    Only this algorithm's vectors: vectors from different algorithms cannot be compared.
    A vector whose length differs from the algorithm's declared length is left out and counted.
    """
    rows = (
        DetectionEmbedding.objects.filter(
            algorithm_id=algorithm.pk,
            project_id__in=project_ids,
            detection__occurrence_id__in=verified_identifications(project_ids).values("occurrence_id"),
        )
        .order_by("detection_id")
        .values_list("detection_id", "vector")
    )
    dimensions = algorithm.embedding_dimensions
    writer: pq.ParquetWriter | None = None
    ids: list[int] = []
    vectors: list[np.ndarray] = []
    written = skipped = 0

    def flush():
        nonlocal writer, ids, vectors
        if writer is None:
            writer = pq.ParquetWriter(path, _vector_schema(dimensions or 0))
        flat = np.concatenate(vectors).astype(np.float16) if vectors else np.zeros(0, dtype=np.float16)
        table = pa.Table.from_arrays(
            [
                pa.array(ids, type=pa.int64()),
                pa.FixedSizeListArray.from_arrays(pa.array(flat, type=pa.float16()), dimensions or 0),
            ],
            schema=_vector_schema(dimensions or 0),
        )
        writer.write_table(table)
        ids, vectors = [], []

    try:
        for detection_id, vector in rows.iterator(chunk_size=FETCH_CHUNK_SIZE):
            array = _vector_as_array(vector)
            if dimensions is None:
                # The algorithm never declared a length; the first vector decides it.
                dimensions = len(array)
            if len(array) != dimensions:
                skipped += 1
                continue
            ids.append(detection_id)
            vectors.append(array)
            written += 1
            if len(ids) >= ROW_GROUP_SIZE:
                flush()
        if ids or writer is None:
            flush()
    finally:
        if writer is not None:
            writer.close()
    return {"rows": written, "skipped": skipped, "dimensions": dimensions or 0}


def _vector_schema(dimensions: int) -> pa.Schema:
    return pa.schema([("detection_id", pa.int64()), ("vector", pa.list_(pa.float16(), dimensions))])


def project_counts(project_ids: list[int]) -> dict[int, dict[str, int]]:
    """Verified occurrences and species per project, in one query."""
    rows = (
        verified_identifications(project_ids)
        .values("occurrence__project_id")
        .annotate(
            occurrences=Count("occurrence_id", distinct=True),
            taxa=Count("occurrence__determination_id", distinct=True),
        )
    )
    return {r["occurrence__project_id"]: {"occurrences": r["occurrences"], "taxa": r["taxa"]} for r in rows}


def _upload(local: pathlib.Path, storage_path: str) -> tuple[str, int]:
    if default_storage.exists(storage_path):
        default_storage.delete(storage_path)
    with open(local, "rb") as f:
        saved = default_storage.save(storage_path, f)
    return saved, local.stat().st_size


def export_snapshot(snapshot: TrainingDataSnapshot) -> TrainingDataSnapshot:
    """Write the snapshot's files and record what they hold. Raises on any failure."""
    salt, test_fraction = DEFAULT_SPLIT_SALT, DEFAULT_TEST_FRACTION
    project_ids = shared_project_ids()
    prefix = f"{SNAPSHOT_DIRECTORY}/snapshot-{snapshot.pk}/"
    files: dict[str, str] = {}
    total_size = 0
    algorithms_meta = []

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = pathlib.Path(tmp)
        manifest = tmp_dir / "manifest.parquet"
        rows_per_project = write_manifest(manifest, project_ids, salt, test_fraction)
        files["manifest"], size = _upload(manifest, f"{prefix}manifest.parquet")
        total_size += size

        algorithms = exported_algorithms(project_ids)
        for algorithm in algorithms:
            local = tmp_dir / f"vectors-{algorithm.pk}.parquet"
            stats = write_vectors(local, algorithm, project_ids)
            name = f"vectors/algorithm={slugify(algorithm.key)}/part-00000.parquet"
            files[f"vectors:{algorithm.key}"], size = _upload(local, f"{prefix}{name}")
            total_size += size
            algorithms_meta.append(
                {"id": algorithm.pk, "key": algorithm.key, "path": files[f"vectors:{algorithm.key}"]}
            )
            algorithms_meta[-1].update(stats)

        counts = project_counts(project_ids)
        projects = {p.pk: p.name for p in Project.objects.filter(pk__in=project_ids).only("pk", "name")}
        rules = {
            "schema_version": SCHEMA_VERSION,
            "verified": "non-withdrawn identification, occurrence determined to species",
            "rank": TaxonRank.SPECIES.name,
            "split_salt": salt,
            "test_fraction": test_fraction,
            "split_by": "occurrence",
        }
        metadata = {
            "snapshot_id": snapshot.pk,
            "created_at": timezone.now().isoformat(),
            "rules": rules,
            "files": files,
            "algorithms": algorithms_meta,
            "projects": [
                {"id": pk, "name": projects.get(pk, ""), "rows": rows_per_project.get(pk, 0), **counts.get(pk, {})}
                for pk in project_ids
            ],
        }
        meta_path = tmp_dir / "metadata.json"
        meta_path.write_text(json.dumps(metadata, indent=2))
        files["metadata"], size = _upload(meta_path, f"{prefix}metadata.json")
        total_size += size

    TrainingDataSnapshotProject.objects.bulk_create(
        [
            TrainingDataSnapshotProject(
                snapshot=snapshot,
                project_id=pk,
                project_name=projects.get(pk, ""),
                rows=rows_per_project.get(pk, 0),
                occurrences=counts.get(pk, {}).get("occurrences", 0),
                taxa=counts.get(pk, {}).get("taxa", 0),
            )
            for pk in project_ids
        ]
    )
    snapshot.algorithms.set(algorithms)
    snapshot.storage_prefix = prefix
    snapshot.files = files
    snapshot.file_size = total_size
    snapshot.rows = sum(rows_per_project.values())
    snapshot.occurrences = sum(c["occurrences"] for c in counts.values())
    snapshot.taxa = verified_identifications(project_ids).values("occurrence__determination_id").distinct().count()
    snapshot.rules = rules
    return snapshot


def run_snapshot(snapshot_id: int | None = None, triggered_by=None) -> TrainingDataSnapshot:
    """
    Run one export under a database lock, recording success or failure on the snapshot.

    Raises ``SnapshotAlreadyRunning`` when another export holds the lock, and re-raises any
    export error after recording it.
    """
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_try_advisory_lock(%s)", [EXPORT_LOCK_KEY])
        (locked,) = cursor.fetchone()
    if not locked:
        raise SnapshotAlreadyRunning("Another training-data export is running.")
    try:
        if snapshot_id is None:
            snapshot = TrainingDataSnapshot.objects.create(triggered_by=triggered_by)
        else:
            snapshot = TrainingDataSnapshot.objects.get(pk=snapshot_id)
        snapshot.status = TrainingDataSnapshotStatus.RUNNING
        snapshot.started_at = timezone.now()
        snapshot.save(update_fields=["status", "started_at", "updated_at"])
        try:
            export_snapshot(snapshot)
        except Exception as e:
            snapshot.status = TrainingDataSnapshotStatus.FAILED
            snapshot.error = f"{type(e).__name__}: {e}"
            snapshot.finished_at = timezone.now()
            snapshot.save()
            logger.exception(f"Training-data snapshot #{snapshot.pk} failed")
            raise
        snapshot.status = TrainingDataSnapshotStatus.SUCCESS
        snapshot.finished_at = timezone.now()
        snapshot.save()
        logger.info(f"Training-data snapshot #{snapshot.pk}: {snapshot.rows} rows in {snapshot.storage_prefix}")
        prune_snapshots(settings.TRAINING_DATA_SNAPSHOTS_KEPT)
        return snapshot
    finally:
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_unlock(%s)", [EXPORT_LOCK_KEY])


def prune_snapshots(keep: int) -> int:
    """Delete the files of successful snapshots older than the newest ``keep``. Returns how many."""
    old = TrainingDataSnapshot.objects.filter(
        status=TrainingDataSnapshotStatus.SUCCESS, pruned_at__isnull=True
    ).order_by("-created_at", "-pk")[keep:]
    pruned = 0
    for snapshot in old:
        for path in snapshot.files.values():
            if default_storage.exists(path):
                default_storage.delete(path)
        snapshot.pruned_at = timezone.now()
        snapshot.files = {}
        snapshot.save(update_fields=["pruned_at", "files", "updated_at"])
        pruned += 1
    return pruned
