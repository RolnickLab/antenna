"""
Building a classifier-head training set from an exported platform-wide snapshot.

The export framework writes the verified labels and their vectors as Parquet; these tests
check that the retrain feature can read that snapshot back into the same npz the training
service already consumes.
"""

import io
import tempfile

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
from django.core.files.storage import default_storage
from django.test import TestCase

from ami.ml.models import Algorithm, TrainingDataSnapshot
from ami.ml.models.training_data import TrainingDataSnapshotStatus
from ami.ml.training import NotEnoughVerifiedData, build_training_dataset_from_snapshot
from ami.ml.training.config import TrainClassifierJobConfig

VECTOR_LENGTH = 4

# One row per detection: (detection_id, occurrence_id, taxon_name, split). Two species, each
# with enough rows to be kept, and both sides of the split populated.
MANIFEST_ROWS = [
    (1, 10, "Snapshotus alpha", "train"),
    (2, 11, "Snapshotus alpha", "train"),
    (3, 12, "Snapshotus alpha", "test"),
    (4, 13, "Snapshotus beta", "train"),
    (5, 14, "Snapshotus beta", "test"),
]


def _save_parquet(table: pa.Table, storage_path: str) -> str:
    with tempfile.NamedTemporaryFile(suffix=".parquet") as tmp:
        pq.write_table(table, tmp.name)
        with open(tmp.name, "rb") as f:
            return default_storage.save(storage_path, f)


class SnapshotFixture(TestCase):
    """A tiny snapshot written straight to the test storage, without the export machinery."""

    def setUp(self) -> None:
        self.algorithm = Algorithm.objects.create(
            name="Backbone", key="backbone", trainable=True, embedding_dimensions=VECTOR_LENGTH
        )
        from ami.main.models import Project
        from ami.users.models import User

        self.user = User.objects.create_user(email="snapshot@example.com", password="testpass123")
        self.project = Project.objects.create(name="Snapshot Project", owner=self.user)

    def make_snapshot(self, manifest_rows=MANIFEST_ROWS, with_vectors=True) -> TrainingDataSnapshot:
        snapshot = TrainingDataSnapshot.objects.create(status=TrainingDataSnapshotStatus.SUCCESS)
        prefix = f"training-data/snapshot-{snapshot.pk}/"

        manifest_schema = pa.schema(
            [
                ("detection_id", pa.int64()),
                ("occurrence_id", pa.int64()),
                ("taxon_name", pa.string()),
                ("split", pa.string()),
            ]
        )
        manifest = pa.Table.from_pylist(
            [
                {"detection_id": d, "occurrence_id": o, "taxon_name": name, "split": split}
                for (d, o, name, split) in manifest_rows
            ],
            schema=manifest_schema,
        )
        files = {"manifest": _save_parquet(manifest, f"{prefix}manifest.parquet")}

        if with_vectors:
            detection_ids = [row[0] for row in manifest_rows]
            # A distinct vector per detection, so the join can be checked if needed.
            flat = np.concatenate([np.full(VECTOR_LENGTH, float(d), dtype=np.float16) for d in detection_ids])
            vector_schema = pa.schema(
                [("detection_id", pa.int64()), ("vector", pa.list_(pa.float16(), VECTOR_LENGTH))]
            )
            vectors = pa.Table.from_arrays(
                [
                    pa.array(detection_ids, type=pa.int64()),
                    pa.FixedSizeListArray.from_arrays(pa.array(flat, type=pa.float16()), VECTOR_LENGTH),
                ],
                schema=vector_schema,
            )
            files[f"vectors:{self.algorithm.key}"] = _save_parquet(vectors, f"{prefix}vectors.parquet")

        snapshot.files = files
        snapshot.save(update_fields=["files"])
        return snapshot

    def load_npz(self, path: str):
        with default_storage.open(path) as f:
            return np.load(io.BytesIO(f.read()), allow_pickle=True)


class TestBuildingFromASnapshot(SnapshotFixture):
    def test_the_snapshot_builds_the_same_npz_the_service_consumes(self):
        snapshot = self.make_snapshot()

        dataset = build_training_dataset_from_snapshot(snapshot, self.project, self.algorithm)

        data = self.load_npz(dataset["path"])
        classes = list(data["classes"])
        self.assertEqual(classes, ["Snapshotus alpha", "Snapshotus beta"])

        # Every row is kept, each label indexes back to its species name.
        self.assertEqual(len(data["labels"]), len(MANIFEST_ROWS))
        self.assertEqual(data["features"].shape, (len(MANIFEST_ROWS), VECTOR_LENGTH))
        for detection_id, label in zip(data["detection_ids"].tolist(), data["labels"].tolist()):
            expected = next(name for (d, _o, name, _s) in MANIFEST_ROWS if d == detection_id)
            self.assertEqual(classes[label], expected)

        # Both sides of the split carry rows, as the sibling builder also insists on.
        split = list(data["split"])
        self.assertIn("train", split)
        self.assertIn("test", split)

        metadata = dataset["metadata"]
        self.assertEqual(metadata.rows, len(MANIFEST_ROWS))
        self.assertEqual(metadata.dimensions, VECTOR_LENGTH)
        self.assertEqual(metadata.classes, classes)
        self.assertEqual(dataset["occurrences"], {})

    def test_a_snapshot_without_this_algorithms_vectors_has_nothing_to_train_on(self):
        snapshot = self.make_snapshot(with_vectors=False)

        with self.assertRaises(NotEnoughVerifiedData):
            build_training_dataset_from_snapshot(snapshot, self.project, self.algorithm)


class TestSnapshotIsAValidSourceOnItsOwn(TestCase):
    def test_a_config_with_only_a_snapshot_passes_validation(self):
        config = TrainClassifierJobConfig.parse_obj(
            {
                "algorithm_key": "backbone",
                "use_project_occurrences": False,
                "use_offline_inat": False,
                "training_snapshot_id": 123,
            }
        )
        self.assertEqual(config.training_snapshot_id, 123)
