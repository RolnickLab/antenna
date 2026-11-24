"""The platform-wide training-data export: which rows go in, and the files it writes."""

import datetime
import io
import json
import uuid

import pyarrow as pa
import pyarrow.parquet as pq
from django.core.files.storage import default_storage
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from ami.main.models import (
    Classification,
    Deployment,
    Detection,
    Event,
    Identification,
    Occurrence,
    Project,
    S3StorageSource,
    SourceImage,
    Taxon,
    TaxonRank,
)
from ami.ml.models import Algorithm, DetectionEmbedding, TrainingDataSnapshot
from ami.ml.models.training_data import TrainingDataSnapshotStatus
from ami.ml.training import verified_occurrence_ids
from ami.ml.training.export import prune_snapshots, run_snapshot
from ami.tests.fixtures.queries import no_query_cache
from ami.users.models import User

VECTOR_LENGTH = 4


def read_parquet(path: str):
    with default_storage.open(path, "rb") as f:
        return pq.read_table(io.BytesIO(f.read()))


class ExportFixture(TestCase):
    """Two projects with verified occurrences built directly, without capture fixtures."""

    def setUp(self) -> None:
        self.user = User.objects.create_user(email="exporter@example.com", password="testpass123")
        self.night = datetime.datetime(2026, 6, 1, 22, 0, 0)
        self.algorithm = Algorithm.objects.create(name="Backbone", key="backbone", embedding_dimensions=VECTOR_LENGTH)
        self.species = Taxon.objects.create(name="Exportus alpha", rank=TaxonRank.SPECIES.name)
        self.stations: dict[int, tuple[Deployment, Event]] = {}
        self.shared = self.make_project("Shared", share=True)
        self.private = self.make_project("Private", share=False)

    def make_project(self, name: str, share: bool) -> Project:
        project = Project.objects.create(name=name, owner=self.user)
        project.feature_flags.share_verified_data_for_training = share
        project.save()
        storage = S3StorageSource.objects.create(
            name="src", project=project, bucket="test", public_base_url="https://example.org/captures/"
        )
        deployment = Deployment.objects.create(name="station", project=project, data_source=storage)
        event = Event.objects.create(deployment=deployment, project=project, start=self.night)
        self.stations[project.pk] = (deployment, event)
        self.species.projects.add(project)
        return project

    def make_occurrence(
        self, project: Project, taxon: Taxon | None = None, identified: bool = True, vector_from=None
    ) -> Occurrence:
        """One occurrence with one detection, identified by a person unless told otherwise."""
        taxon = taxon or self.species
        deployment, event = self.stations[project.pk]
        image = SourceImage.objects.create(
            deployment=deployment,
            project=project,
            event=event,
            timestamp=self.night,
            path=f"night/{uuid.uuid4().hex[:8]}.jpg",
            public_base_url="https://example.org/captures/",
        )
        detection = Detection.objects.create(
            source_image=image, timestamp=self.night, bbox=[0.1, 0.1, 0.3, 0.3], path="detections/crop.jpg"
        )
        Classification.objects.create(detection=detection, taxon=taxon, score=0.9, timestamp=self.night)
        occurrence = detection.associate_new_occurrence()
        if identified:
            Identification.objects.create(occurrence=occurrence, taxon=taxon, user=self.user)
        for algorithm in vector_from if vector_from is not None else [self.algorithm]:
            DetectionEmbedding.objects.create(
                detection=detection, algorithm=algorithm, project=project, vector=[float(algorithm.pk)] * VECTOR_LENGTH
            )
        occurrence.refresh_from_db()
        return occurrence

    def manifest(self, snapshot: TrainingDataSnapshot):
        return read_parquet(snapshot.files["manifest"])


class TestWhichRowsAreExported(ExportFixture):
    def test_only_opted_in_projects_are_exported(self):
        shared = self.make_occurrence(self.shared)
        self.make_occurrence(self.private)

        snapshot = run_snapshot()

        manifest = self.manifest(snapshot)
        self.assertEqual(manifest.column("occurrence_id").to_pylist(), [shared.pk])
        self.assertEqual(set(manifest.column("project_id").to_pylist()), {self.shared.pk})
        vectors = read_parquet(snapshot.files[f"vectors:{self.algorithm.key}"])
        self.assertEqual(vectors.column("detection_id").to_pylist(), [shared.detections.get().pk])
        self.assertEqual(list(snapshot.project_counts.values_list("project_id", flat=True)), [self.shared.pk])

    def test_only_species_identified_by_a_person_are_exported(self):
        species = self.make_occurrence(self.shared)
        self.make_occurrence(self.shared, Taxon.objects.create(name="Exportus", rank=TaxonRank.GENUS.name))
        self.make_occurrence(self.shared, Taxon.objects.create(name="Not Identifiable", rank=TaxonRank.UNKNOWN.name))
        self.make_occurrence(self.shared, identified=False)
        withdrawn = self.make_occurrence(self.shared)
        withdrawn.identifications.update(withdrawn=True)

        manifest = self.manifest(run_snapshot())

        self.assertEqual(manifest.column("occurrence_id").to_pylist(), [species.pk])
        self.assertEqual(manifest.column("taxon_rank").to_pylist(), [TaxonRank.SPECIES.name])

    def test_rows_follow_the_training_set_rule(self):
        """The export and a single-project training set must agree on what is verified."""
        self.make_occurrence(self.shared)
        self.make_occurrence(self.shared, Taxon.objects.create(name="Exportus", rank=TaxonRank.GENUS.name))
        self.make_occurrence(self.shared, identified=False)

        manifest = self.manifest(run_snapshot())

        self.assertEqual(set(manifest.column("occurrence_id").to_pylist()), set(verified_occurrence_ids(self.shared)))

    def test_each_vector_file_holds_one_algorithm(self):
        other = Algorithm.objects.create(name="Other", key="other", embedding_dimensions=VECTOR_LENGTH)
        both = self.make_occurrence(self.shared, vector_from=[self.algorithm, other])
        only_first = self.make_occurrence(self.shared, vector_from=[self.algorithm])

        snapshot = run_snapshot()

        first = read_parquet(snapshot.files["vectors:backbone"])
        second = read_parquet(snapshot.files["vectors:other"])
        self.assertEqual(
            first.column("detection_id").to_pylist(),
            sorted([both.detections.get().pk, only_first.detections.get().pk]),
        )
        self.assertEqual(second.column("detection_id").to_pylist(), [both.detections.get().pk])
        # Each file holds that algorithm's own values, never the other's.
        self.assertEqual({v for row in first.column("vector").to_pylist() for v in row}, {float(self.algorithm.pk)})
        self.assertEqual({v for row in second.column("vector").to_pylist() for v in row}, {float(other.pk)})
        self.assertEqual(set(snapshot.algorithms.all()), {self.algorithm, other})

    def test_no_opted_in_project_gives_an_empty_snapshot(self):
        self.make_occurrence(self.private)

        snapshot = run_snapshot()

        self.assertEqual(snapshot.status, TrainingDataSnapshotStatus.SUCCESS)
        self.assertEqual(snapshot.rows, 0)
        self.assertEqual(self.manifest(snapshot).num_rows, 0)


class TestTheFiles(ExportFixture):
    def test_the_files_read_back_with_pyarrow(self):
        occurrence = self.make_occurrence(self.shared)

        snapshot = run_snapshot()

        manifest = self.manifest(snapshot)
        row = manifest.to_pylist()[0]
        self.assertEqual(row["occurrence_id"], occurrence.pk)
        self.assertEqual(row["taxon_id"], self.species.pk)
        self.assertIn(row["split"], {"train", "test"})
        # float32 on disk, so compare to 6 places.
        for got, expected in zip(row["bbox"], [0.1, 0.1, 0.3, 0.3], strict=True):
            self.assertAlmostEqual(got, expected, places=6)
        self.assertTrue(row["capture_url"].startswith("https://example.org/captures/night/"))
        self.assertTrue(row["crop_url"].endswith("detections/crop.jpg"))
        self.assertIsNotNone(row["identification_id"])

        vectors = read_parquet(snapshot.files["vectors:backbone"])
        vector_type = vectors.schema.field("vector").type
        self.assertTrue(pa.types.is_fixed_size_list(vector_type))
        self.assertEqual((vector_type.value_type, vector_type.list_size), (pa.float16(), VECTOR_LENGTH))

        with default_storage.open(snapshot.files["metadata"], "rb") as f:
            metadata = json.load(f)
        self.assertEqual(metadata["snapshot_id"], snapshot.pk)
        self.assertEqual([p["id"] for p in metadata["projects"]], [self.shared.pk])
        self.assertEqual(metadata["rules"]["rank"], TaxonRank.SPECIES.name)

        self.assertEqual((snapshot.rows, snapshot.occurrences, snapshot.taxa), (1, 1, 1))
        self.assertGreater(snapshot.file_size, 0)

    def test_query_count_does_not_grow_with_rows(self):
        """Rows are streamed: the number of queries depends on algorithms, not on detections."""
        self.make_occurrence(self.shared)
        with no_query_cache(), CaptureQueriesContext(connection) as few:
            run_snapshot()

        for _ in range(6):
            self.make_occurrence(self.shared)
        with no_query_cache(), CaptureQueriesContext(connection) as many:
            snapshot = run_snapshot()

        self.assertEqual(snapshot.rows, 7)
        self.assertEqual(len(many), len(few))

    def test_old_snapshots_lose_their_files_but_keep_their_counts(self):
        self.make_occurrence(self.shared)
        first = run_snapshot()
        second = run_snapshot()

        self.assertEqual(prune_snapshots(keep=1), 1)

        first.refresh_from_db()
        second.refresh_from_db()
        self.assertIsNotNone(first.pruned_at)
        self.assertEqual(first.files, {})
        self.assertEqual(first.rows, 1)
        self.assertIsNone(second.pruned_at)
        self.assertTrue(default_storage.exists(second.files["manifest"]))
