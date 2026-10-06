"""How detection feature vectors are stored and read back.

These pin that a vector is stored once per detection, algorithm and key on the detection it
was sent with, never as a classification; that its project is copied from the detection's
capture; that writes are insert-mostly; and that readers return one (algorithm, key) at a time.
"""

import datetime

import numpy as np
import pydantic
from django.db import connection
from django.test import SimpleTestCase, TestCase
from django.test.utils import CaptureQueriesContext

from ami.jobs.models import Job
from ami.main.models import Classification, Deployment, Detection, SourceImage
from ami.main.models_future.embeddings import vectors_for_detections
from ami.ml.exceptions import PipelineNotConfigured
from ami.ml.models import Algorithm, DetectionEmbedding, Pipeline
from ami.ml.models.pipeline import (
    EmbeddingDimensionMismatch,
    create_detection_embeddings,
    get_or_create_algorithm_and_category_map,
    save_results,
)
from ami.ml.schemas import DetectionResponse, PipelineResultsResponse
from ami.tests.fixtures.main import setup_test_project
from ami.tests.fixtures.ml import ALGORITHM_CHOICES

DETECTOR = ALGORITHM_CHOICES["random-detector"]
BINARY = ALGORITHM_CHOICES["random-binary-classifier"]  # labels: "Moth", "Not a moth"
SPECIES = ALGORITHM_CHOICES["random-species-classifier"]
LENGTH = 2048


def _embedding_payload(vector: list[float], algorithm=SPECIES) -> list[dict]:
    return [{"algorithm": {"name": algorithm.name, "key": algorithm.key}, "features": vector}]


class TestEmbeddingSchema(SimpleTestCase):
    """The per-detection ``embeddings`` field of the processing-service results schema."""

    def _detection(self, **extra) -> dict:
        return {
            "source_image_id": "1",
            "bbox": {"x1": 0.0, "y1": 0.0, "x2": 10.0, "y2": 10.0},
            "algorithm": {"name": DETECTOR.name, "key": DETECTOR.key},
            "timestamp": datetime.datetime.now().isoformat(),
            **extra,
        }

    def test_a_detection_carries_each_vector_with_its_algorithm(self):
        """The field is optional, so a service that sends no embeddings still parses."""
        parsed = DetectionResponse.parse_obj(self._detection(embeddings=_embedding_payload([0.5] * LENGTH)))
        self.assertEqual(
            [(e.algorithm.key, len(e.features)) for e in parsed.embeddings or []], [(SPECIES.key, LENGTH)]
        )
        self.assertIsNone(DetectionResponse.parse_obj(self._detection()).embeddings)

    def test_an_empty_vector_is_refused(self):
        """Any length parses (extractors differ; each algorithm's length is checked on save), but not none."""
        parsed = DetectionResponse.parse_obj(self._detection(embeddings=_embedding_payload([0.5] * 512)))
        self.assertEqual(len(parsed.embeddings or []), 1)
        with self.assertRaises(pydantic.ValidationError):
            DetectionResponse.parse_obj(self._detection(embeddings=_embedding_payload([])))


class ClassifierPipelineMixin:
    """A classifier pipeline whose results carry a vector on each detection, as the processing service sends them."""

    LOW = [0.25] * LENGTH
    HIGH = [0.75] * LENGTH

    def _set_up_pipeline(self) -> None:
        self.project, self.deployment = setup_test_project(reuse=False)
        self.pipeline = Pipeline.objects.create(name="Embedding test pipeline")
        self.pipeline.algorithms.set(
            [get_or_create_algorithm_and_category_map(algorithm) for algorithm in (DETECTOR, BINARY, SPECIES)]
        )
        self.species = Algorithm.objects.get(key=SPECIES.key)
        self.images = 0

    def _image(self) -> SourceImage:
        self.images += 1
        return SourceImage.objects.create(
            path=f"emb-{self.images}-20240101000{self.images}00.jpg", deployment=self.deployment, project=self.project
        )

    @staticmethod
    def _classification(algorithm, label: str, score: float, terminal: bool) -> dict:
        return {
            "classification": label,
            "scores": [score],
            "algorithm": {"name": algorithm.name, "key": algorithm.key},
            "terminal": terminal,
            "timestamp": datetime.datetime.now().isoformat(),
        }

    def _detection(self, image: SourceImage, classifications: list[dict], embeddings=None, box: float = 0.0) -> dict:
        payload = {
            "source_image_id": str(image.pk),
            "bbox": {"x1": box, "y1": box, "x2": box + 10.0, "y2": box + 10.0},
            "algorithm": {"name": DETECTOR.name, "key": DETECTOR.key},
            "timestamp": datetime.datetime.now().isoformat(),
            "classifications": classifications,
        }
        if embeddings is not None:
            payload["embeddings"] = embeddings
        return payload

    def _rejected(self, image: SourceImage, embeddings=None, box: float = 0.0) -> dict:
        """A crop the moth/non-moth filter rejected, labelled as the service labels it: non-terminal."""
        label = self._classification(BINARY, "Not a moth", 0.8, terminal=False)
        return self._detection(image, [label], embeddings, box)

    def _moth(self, image: SourceImage, embeddings=None, box: float = 0.0) -> dict:
        labels = [
            self._classification(BINARY, "Moth", 0.95, terminal=False),
            self._classification(SPECIES, "Vanessa cardui", 0.6, terminal=True),
        ]
        return self._detection(image, labels, embeddings, box)

    def _save(self, *detections: dict, job_id: int | None = None) -> None:
        image_ids = list(dict.fromkeys(d["source_image_id"] for d in detections))
        payload = {
            "pipeline": self.pipeline.slug,
            "total_time": 0.01,
            "source_images": [{"id": image_id, "url": f"test/{image_id}.jpg"} for image_id in image_ids],
            "detections": list(detections),
        }
        save_results(PipelineResultsResponse.parse_obj(payload), job_id=job_id)

    @staticmethod
    def _stored(image: SourceImage) -> dict[tuple[float, str], list[float]]:
        """{(box corner, algorithm key): vector} for the image's stored embeddings."""
        rows = DetectionEmbedding.objects.filter(detection__source_image=image).select_related(
            "detection", "algorithm"
        )
        return {(row.detection.bbox[0], row.algorithm.key): list(row.vector) for row in rows}


class TestDetectionEmbeddings(ClassifierPipelineMixin, TestCase):
    """Storing the feature vector a processing service sends with each detection.

    The vector is what similarity search and tracking compare, and it arrives for every
    detection, including those the moth/non-moth filter rejected. What these pin is that it
    is stored once per detection and algorithm, on the detection it was sent with, and that
    storing it never adds a classification or moves a determination.
    """

    def setUp(self) -> None:
        self._set_up_pipeline()

    def test_every_detection_stores_one_vector_per_algorithm(self):
        """Including the rejected crop, which has no species classification that could carry one."""
        image = self._image()
        self._save(
            self._moth(image, _embedding_payload(self.LOW)),
            self._rejected(image, _embedding_payload(self.HIGH), box=100.0),
        )
        self.assertEqual(self._stored(image), {(0.0, SPECIES.key): self.LOW, (100.0, SPECIES.key): self.HIGH})
        self.assertEqual(set(DetectionEmbedding.objects.values_list("project_id", flat=True)), {self.project.pk})

    def test_a_vector_adds_no_classification_and_moves_no_determination(self):
        """The rejected crop's binary label is non-terminal, so a species classification sent in
        the vector's place would become its determination. An embedding must not."""
        control, treated = self._image(), self._image()
        self._save(self._rejected(control))
        self._save(self._rejected(treated, _embedding_payload(self.HIGH)))

        for image in (control, treated):
            detection = Detection.objects.select_related("occurrence__determination").get(source_image=image)
            self.assertEqual(detection.occurrence.determination.name, "Not a moth")
            self.assertEqual(detection.classifications.count(), 1)
        self.assertEqual(DetectionEmbedding.objects.filter(detection__source_image=treated).count(), 1)

    def test_each_row_records_the_job_that_saved_it_and_outlives_the_job(self):
        image = self._image()
        first, second = (
            Job.objects.create(project=self.project, name=f"Embedding job {n}", pipeline=self.pipeline) for n in (1, 2)
        )
        self._save(self._moth(image, _embedding_payload(self.LOW)), job_id=first.pk)
        self._save(self._moth(image, _embedding_payload(self.HIGH)), job_id=second.pk)

        detection = Detection.objects.get(source_image=image)
        embedding = DetectionEmbedding.objects.get(detection=detection)
        self.assertEqual(embedding.job_id, second.pk, "A replaced vector records the job that replaced it")

        second.delete()
        embedding.refresh_from_db()
        self.assertIsNone(embedding.job_id)
        self.assertEqual(list(embedding.vector), self.HIGH)

    def test_a_vector_lands_on_its_own_detection_when_some_detections_already_exist(self):
        """Detection creation returns existing detections ahead of new ones, so pairing responses
        with detections by position would swap these two vectors."""
        image = self._image()
        self._save(self._rejected(image, box=0.0))
        self._save(
            self._rejected(image, _embedding_payload(self.HIGH), box=100.0),
            self._rejected(image, _embedding_payload(self.LOW), box=0.0),
        )
        self.assertEqual(self._stored(image), {(0.0, SPECIES.key): self.LOW, (100.0, SPECIES.key): self.HIGH})

    def test_a_vector_from_an_unregistered_algorithm_stops_the_batch_like_a_classification(self):
        """It raises where an unregistered classification algorithm does: after detections are
        saved and before any classification is."""
        image = self._image()
        unregistered = {"algorithm": {"name": "Unregistered", "key": "unregistered-embedder"}, "features": self.LOW}
        with self.assertRaises(PipelineNotConfigured):
            self._save(self._rejected(image, [unregistered]))
        self.assertFalse(DetectionEmbedding.objects.exists())
        self.assertFalse(Classification.objects.filter(detection__source_image=image).exists())

    def test_saving_the_same_results_twice_changes_nothing_and_a_new_vector_replaces_the_row(self):
        image = self._image()
        self._save(self._moth(image, _embedding_payload(self.LOW)))
        first = DetectionEmbedding.objects.get()

        self._save(self._moth(image, _embedding_payload(self.LOW)))
        unchanged = DetectionEmbedding.objects.get()
        self.assertEqual((unchanged.pk, unchanged.updated_at), (first.pk, first.updated_at))

        self._save(self._moth(image, _embedding_payload(self.HIGH)))
        replaced = DetectionEmbedding.objects.get()
        self.assertEqual(replaced.pk, first.pk, "The row is updated in place, not deleted and re-inserted")
        self.assertEqual(list(replaced.vector), self.HIGH)
        self.assertGreater(replaced.updated_at, first.updated_at)

    def test_an_algorithm_keeps_the_length_of_its_first_vector(self):
        """Vectors of another length are refused, because they could never be compared."""
        image, other = self._image(), self._image()
        self._save(self._moth(image, _embedding_payload([0.5] * 512)))
        self.species.refresh_from_db()
        self.assertEqual(self.species.embedding_dimensions, 512)

        with self.assertRaises(EmbeddingDimensionMismatch):
            self._save(self._moth(other, _embedding_payload(self.LOW)))
        self.assertFalse(DetectionEmbedding.objects.filter(detection__source_image=other).exists())
        self.species.refresh_from_db()
        self.assertEqual(self.species.embedding_dimensions, 512)

    def test_a_vector_half_precision_cannot_hold_is_skipped_with_a_warning(self):
        image = self._image()
        too_large = [1e6] + [0.5] * (LENGTH - 1)
        not_a_number = [float("nan")] + [0.5] * (LENGTH - 1)
        with self.assertLogs("ami.ml.models.pipeline", level="WARNING") as logs:
            self._save(
                self._rejected(image, _embedding_payload(too_large), box=0.0),
                self._rejected(image, _embedding_payload(not_a_number), box=100.0),
                self._rejected(image, _embedding_payload(self.LOW), box=200.0),
            )
        self.assertIn("Skipped 2 vectors", "\n".join(logs.output))
        self.assertEqual(self._stored(image), {(200.0, SPECIES.key): self.LOW})

    def test_storing_vectors_takes_the_same_queries_however_many_detections(self):
        image = self._image()
        boxes = [float(20 * i) for i in range(5)]
        self._save(*[self._rejected(image, box=box) for box in boxes])
        detections = list(Detection.objects.filter(source_image=image).order_by("bbox"))
        parsed = [
            DetectionResponse.parse_obj(self._rejected(image, _embedding_payload(self.LOW), box=b)) for b in boxes
        ]
        algorithms_known = {algorithm.key: algorithm for algorithm in self.pipeline.algorithms.all()}

        # The first vector records the algorithm's length; measure after that, on other
        # detections so no read is served from the query cache.
        create_detection_embeddings(detections[:1], parsed[:1], algorithms_known)
        DetectionEmbedding.objects.all().delete()
        with CaptureQueriesContext(connection) as one:
            create_detection_embeddings(detections[1:2], parsed[1:2], algorithms_known)
        DetectionEmbedding.objects.all().delete()
        with CaptureQueriesContext(connection) as five:
            stored = create_detection_embeddings(detections, parsed, algorithms_known)
        self.assertEqual(len(five), len(one))
        self.assertEqual(len(stored), 5)

        # A rerun with identical vectors reads the stored rows and writes nothing.
        with self.assertNumQueries(1):
            create_detection_embeddings(detections, parsed, algorithms_known)


class TestEmbeddingProject(TestCase):
    """An embedding's project is its capture's, falling back to the capture's station's."""

    def setUp(self) -> None:
        self.project, self.deployment = setup_test_project(reuse=False)
        self.image = SourceImage.objects.create(
            path="project-fill.jpg", deployment=self.deployment, project=self.project
        )
        self.detection = Detection.objects.create(source_image=self.image, bbox=[0.0, 0.0, 10.0, 10.0])
        self.algorithm = Algorithm.objects.create(name="Backbone", key="backbone", task_type="embedding")

    def _embedding(self, **fields) -> DetectionEmbedding:
        return DetectionEmbedding(detection=self.detection, algorithm=self.algorithm, vector=[0.5] * 4, **fields)

    def test_the_captures_project_is_copied_on_save_and_on_store(self):
        self._embedding().save()
        self.assertEqual(DetectionEmbedding.objects.get().project_id, self.project.pk)

        DetectionEmbedding.objects.all().delete()
        DetectionEmbedding.objects.store([self._embedding()])
        self.assertEqual(DetectionEmbedding.objects.get().project_id, self.project.pk)

    def test_a_capture_without_a_project_falls_back_to_its_station(self):
        SourceImage.objects.filter(pk=self.image.pk).update(project=None)
        DetectionEmbedding.objects.store([self._embedding()])
        self.assertEqual(DetectionEmbedding.objects.get().project_id, self.project.pk)

    def test_no_project_anywhere_refuses_the_write(self):
        SourceImage.objects.filter(pk=self.image.pk).update(project=None)
        Deployment.objects.filter(pk=self.deployment.pk).update(project=None)
        with self.assertRaises(ValueError):
            DetectionEmbedding.objects.store([self._embedding()])
        with self.assertRaises(ValueError):
            self._embedding().save()
        self.assertFalse(DetectionEmbedding.objects.exists())


class TestEmbeddingReaders(TestCase):
    """Readers return vectors of one (algorithm, key) at a time, as float32 arrays."""

    def setUp(self) -> None:
        self.project, self.deployment = setup_test_project(reuse=False)
        image = SourceImage.objects.create(path="readers.jpg", deployment=self.deployment, project=self.project)
        self.detections = [
            Detection.objects.create(source_image=image, bbox=[float(i), 0.0, float(i) + 10.0, 10.0]) for i in range(3)
        ]
        self.backbone = Algorithm.objects.create(name="Backbone", key="backbone", task_type="embedding")
        self.other = Algorithm.objects.create(name="Other backbone", key="other-backbone", task_type="embedding")
        DetectionEmbedding.objects.store(
            [
                DetectionEmbedding(detection=self.detections[0], algorithm=self.backbone, vector=[0.25] * 4),
                DetectionEmbedding(detection=self.detections[1], algorithm=self.backbone, vector=[0.5] * 4),
                DetectionEmbedding(detection=self.detections[0], algorithm=self.other, vector=[0.75] * 8),
                DetectionEmbedding(
                    detection=self.detections[2], algorithm=self.backbone, key="projection", vector=[1.0] * 2
                ),
            ]
        )

    def test_vectors_come_back_for_one_algorithm_and_key_only(self):
        ids = [detection.pk for detection in self.detections]
        with self.assertNumQueries(1):
            vectors = vectors_for_detections(ids, self.backbone.pk)
        self.assertEqual(sorted(vectors), ids[:2])
        self.assertEqual({v.shape for v in vectors.values()}, {(4,)})
        self.assertEqual({v.dtype for v in vectors.values()}, {np.dtype(np.float32)})
        self.assertEqual(float(vectors[ids[1]][0]), 0.5)

        self.assertEqual(list(vectors_for_detections(ids, self.other.pk)), ids[:1])
        self.assertEqual(list(vectors_for_detections(ids, self.backbone.pk, key="projection")), ids[2:])


class TestPgvectorGuard(SimpleTestCase):
    """The extension migration stops with one clear message unless the server offers pgvector 0.8+."""

    @staticmethod
    def _run(row):
        import importlib
        from unittest import mock

        migration = importlib.import_module("ami.ml.migrations.0029_enable_pgvector")
        cursor = mock.MagicMock()
        cursor.__enter__.return_value.fetchone.return_value = row
        schema_editor = mock.Mock()
        schema_editor.connection.cursor.return_value = cursor
        migration.check_pgvector_is_installed(apps=None, schema_editor=schema_editor)

    def test_a_missing_or_old_package_is_refused_and_a_current_one_passes(self):
        with self.assertRaisesRegex(RuntimeError, "not installed"):
            self._run(None)
        with self.assertRaisesRegex(RuntimeError, "found 0.7.4"):
            self._run(("0.7.4",))
        self._run(("0.8.6",))
        self._run(("1.0.0",))


class TestEmbeddingColumn(TestCase):
    def test_the_vector_column_is_an_unsized_halfvec_stored_out_of_line_uncompressed(self):
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT format_type(atttypid, atttypmod), attstorage FROM pg_attribute
                WHERE attrelid = 'ml_detectionembedding'::regclass AND attname = 'vector'
                """
            )
            self.assertEqual(cursor.fetchone(), ("halfvec", "e"))
