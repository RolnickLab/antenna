"""Moving detection feature vectors between projects by detection key.

Vectors live in two stores that come and go with the schema: ``DetectionEmbedding`` rows
and the ``features_2048`` column on classifications. These tests run on any branch: each
store's test skips where the branch lacks it, and the fallbacks for a missing store are
tested with the store detection patched out.
"""

import datetime
import pathlib
import tempfile
from unittest import mock

import numpy as np
from django.db import connection
from django.test import TestCase

from ami.main.models import (
    Classification,
    Detection,
    Occurrence,
    SourceImage,
    Taxon,
    TaxonRank,
    group_images_into_events,
)
from ami.main.models_future.detection_matching import MATCH_EXACT
from ami.main.models_future.embedding_transfer import (
    SOURCE_CLASSIFIER_FEATURES,
    SOURCE_EMBEDDING,
    EmbeddingManifest,
    classifier_features_available,
    embedding_model,
    export_embeddings,
    import_embeddings,
    read_index,
    vectors_file,
)
from ami.ml.models import Algorithm
from ami.tests.fixtures.main import create_taxa, setup_test_project

BOX = [10.0, 10.0, 40.0, 40.0]


def pgvector_is_available() -> bool:
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1 FROM pg_extension WHERE extname = 'vector'")
        return cursor.fetchone() is not None


class TestEmbeddingTransfer(TestCase):
    def setUp(self) -> None:
        if not pgvector_is_available():
            self.skipTest("pgvector is not installed in this database")
        self.source_project, self.source_deployment = setup_test_project(reuse=False)
        self.target_project, self.target_deployment = setup_test_project(reuse=False)
        create_taxa(self.source_project)
        self.taxon = (
            Taxon.objects.filter(rank=TaxonRank.SPECIES.name, projects=self.source_project).order_by("pk").first()
        )
        self.source_captures = self._make_captures(self.source_deployment)
        self.target_captures = self._make_captures(self.target_deployment)
        self.algorithm = Algorithm.objects.create(key="replay-test-backbone", name="Replay Test Backbone")
        rng = np.random.default_rng(7)
        self.features: dict[str, np.ndarray] = {}
        self.embeddings: dict[str, np.ndarray] = {}
        for index, detection in enumerate(self._detections(self.source_project)):
            if classifier_features_available():
                vector = rng.standard_normal(2048).astype(np.float32)
                detection.classifications.create(
                    taxon=self.taxon,
                    score=0.5,
                    algorithm=self.algorithm,
                    timestamp=detection.timestamp,
                    features_2048=vector.tolist(),
                )
                self.features[detection.source_image.path] = vector
            # Where the embeddings table exists, half the detections also carry an extractor vector.
            if embedding_model() is not None and index < 3:
                embedding = rng.standard_normal(16).astype(np.float32)
                self._store_embedding(detection, embedding)
                self.embeddings[detection.source_image.path] = embedding

    def _make_captures(self, deployment) -> list[SourceImage]:
        """Six captures one minute apart, each with one detection in its own occurrence."""
        start = datetime.datetime(2024, 6, 1, 22, 0)
        captures = [
            SourceImage.objects.create(
                deployment=deployment,
                project=deployment.project,
                timestamp=start + datetime.timedelta(minutes=i),
                path=f"replay/capture-{i}.jpg",
                width=640,
                height=480,
            )
            for i in range(6)
        ]
        group_images_into_events(deployment)
        for capture in captures:
            capture.refresh_from_db()
            occurrence = Occurrence.objects.create(
                event=capture.event, deployment=deployment, project=deployment.project
            )
            Detection.objects.create(
                source_image=capture, timestamp=capture.timestamp, bbox=BOX, occurrence=occurrence
            )
        return captures

    def _detections(self, project):
        return Detection.objects.filter(source_image__project=project).order_by("source_image__timestamp")

    def _store_embedding(self, detection, vector) -> None:
        model = embedding_model()
        fields = {f.name for f in model._meta.get_fields()}
        values = {"detection": detection, "algorithm": self.algorithm, "vector": vector.tolist()}
        if "key" in fields:
            values["key"] = "embedding"
        if "project" in fields:
            values["project"] = detection.source_image.project
        model.objects.create(**values)

    def _target_classifications(self) -> None:
        for detection in self._detections(self.target_project):
            detection.classifications.create(
                taxon=self.taxon, score=0.4, algorithm=self.algorithm, timestamp=detection.timestamp
            )

    def test_classifier_features_are_exported_and_put_back_on_the_classification(self):
        if not classifier_features_available():
            self.skipTest("Classifications on this branch have no feature vector column")
        with tempfile.TemporaryDirectory() as directory:
            directory = pathlib.Path(directory)
            manifest = export_embeddings(self.source_project, self.algorithm, directory)

            self.assertEqual(manifest.sources[SOURCE_CLASSIFIER_FEATURES]["count"], 6)
            self.assertEqual(manifest.sources[SOURCE_CLASSIFIER_FEATURES]["dimensions"], 2048)
            self.assertEqual(EmbeddingManifest.read(directory).count, manifest.count)
            matrix = np.load(directory / vectors_file(SOURCE_CLASSIFIER_FEATURES))
            for entry in read_index(directory):
                if entry.source == SOURCE_CLASSIFIER_FEATURES:
                    np.testing.assert_array_equal(matrix[entry.row], self.features[entry.key.capture_path])

            # No classification on the target yet: nowhere to put the features, so they are skipped, not lost.
            report = import_embeddings(self.target_project, directory, execute=True)
            self.assertEqual(report.summary()["detections"][MATCH_EXACT], manifest.count)
            self.assertEqual(report.skipped_no_classification, 6)
            self.assertEqual(report.written[SOURCE_CLASSIFIER_FEATURES], 0)

            self._target_classifications()
            report = import_embeddings(self.target_project, directory, execute=True)
            self.assertEqual(report.written[SOURCE_CLASSIFIER_FEATURES], 6)
            stored = Classification.objects.get(detection__source_image=self.target_captures[0])
            # pgvector hands back decimal text parsed as float64; compare at the stored float32 precision.
            np.testing.assert_array_equal(
                np.asarray(list(stored.features_2048), dtype=np.float32), self.features[self.target_captures[0].path]
            )

            again = import_embeddings(self.target_project, directory, execute=True)
            self.assertEqual(
                (again.written[SOURCE_CLASSIFIER_FEATURES], again.skipped_existing[SOURCE_CLASSIFIER_FEATURES]), (0, 6)
            )

    def test_embeddings_are_exported_and_rewritten_as_rows(self):
        if embedding_model() is None:
            self.skipTest("This branch has no DetectionEmbedding table")
        with tempfile.TemporaryDirectory() as directory:
            directory = pathlib.Path(directory)
            manifest = export_embeddings(self.source_project, self.algorithm, directory)

            self.assertEqual(manifest.sources[SOURCE_EMBEDDING]["count"], 3)
            self.assertEqual(manifest.sources[SOURCE_EMBEDDING]["dimensions"], 16)
            if classifier_features_available():
                self.assertEqual(
                    manifest.sources[SOURCE_CLASSIFIER_FEATURES]["count"], 6, "both stores, no double counting"
                )
                self.assertEqual(manifest.count, 9)
            else:
                self.assertIn(SOURCE_CLASSIFIER_FEATURES, manifest.skipped_sources)
                self.assertEqual(manifest.count, 3)

            report = import_embeddings(self.target_project, directory, execute=True)
            self.assertEqual(report.written[SOURCE_EMBEDDING], 3)
            rows = embedding_model().objects.filter(
                detection__source_image__project=self.target_project, algorithm=self.algorithm
            )
            self.assertEqual(rows.count(), 3)
            row = rows.get(detection__source_image=self.target_captures[0])
            if {f.name for f in embedding_model()._meta.get_fields()} >= {"key", "project"}:
                self.assertEqual((row.key, row.project_id), ("embedding", self.target_project.pk))
            # The settled schema stores half precision; compare at that precision.
            np.testing.assert_allclose(
                np.asarray(list(row.vector), dtype=np.float32),
                self.embeddings[self.target_captures[0].path],
                rtol=2e-3,
            )

            again = import_embeddings(self.target_project, directory, execute=True)
            self.assertEqual((again.written[SOURCE_EMBEDDING], again.skipped_existing[SOURCE_EMBEDDING]), (0, 3))

    def test_a_store_the_branch_lacks_is_noted_on_export_and_skipped_on_import(self):
        if not classifier_features_available():
            self.skipTest("Needs a branch with classifier features to build the export from")
        with tempfile.TemporaryDirectory() as directory:
            directory = pathlib.Path(directory)
            export_embeddings(self.source_project, self.algorithm, directory)
            self._target_classifications()

            with mock.patch(
                "ami.main.models_future.embedding_transfer.classifier_features_available", return_value=False
            ):
                report = import_embeddings(self.target_project, directory, execute=True)
                self.assertEqual(report.skipped_no_field[SOURCE_CLASSIFIER_FEATURES], 6)
                self.assertEqual(report.written[SOURCE_CLASSIFIER_FEATURES], 0)

                manifest = export_embeddings(self.source_project, self.algorithm, directory / "again")
            self.assertNotIn(SOURCE_CLASSIFIER_FEATURES, manifest.sources)
            self.assertIn("features_2048", manifest.skipped_sources[SOURCE_CLASSIFIER_FEATURES])
            if embedding_model() is None:
                self.assertIn(SOURCE_EMBEDDING, manifest.skipped_sources)
