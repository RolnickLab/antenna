"""How detection feature vectors are validated, stored and read back.

These pin that a vector is stored once per detection and algorithm, on the detection it was sent
with, never as a classification; that the first vector stored is kept; that a vector which cannot be
stored stops the batch before anything is written; and that concurrent writers neither fail nor
store two vectors for one detection and algorithm.
"""

import datetime
import random
import threading

import numpy as np
import pydantic
from django.db import connection
from django.test import SimpleTestCase, TestCase, TransactionTestCase
from django.test.utils import CaptureQueriesContext

from ami.jobs.models import Job
from ami.main.models import Classification, Detection, SourceImage
from ami.ml.embeddings.writer import (
    EmbeddingDimensionMismatch,
    create_detection_embeddings,
    validate_detection_embeddings,
)
from ami.ml.exceptions import PipelineNotConfigured
from ami.ml.models import Algorithm, DetectionEmbedding, Pipeline
from ami.ml.models.pipeline import get_or_create_algorithm_and_category_map, save_results
from ami.ml.schemas import AlgorithmConfigResponse, DetectionResponse, PipelineResultsResponse
from ami.tests.fixtures.main import no_processing_service_http, setup_test_project
from ami.tests.fixtures.ml import ALGORITHM_CHOICES
from ami.tests.fixtures.queries import no_query_cache
from ami.users.models import User

LENGTH = 2048
DETECTOR = ALGORITHM_CHOICES["random-detector"]
# Labels "Moth" and "Not a moth"; it also returns 8-dimension vectors in these tests.
BINARY = ALGORITHM_CHOICES["random-binary-classifier"].copy(update={"embedding_dimensions": 8})
SPECIES = ALGORITHM_CHOICES["random-species-classifier"].copy(update={"embedding_dimensions": LENGTH})


def _embedding_payload(vector: list[float], algorithm: AlgorithmConfigResponse = SPECIES) -> list[dict]:
    return [{"algorithm": {"name": algorithm.name, "key": algorithm.key}, "features": vector}]


class TestEmbeddingSchema(SimpleTestCase):
    """The checks the results schema makes, which reject a bad vector before any result is saved."""

    def _detection(self, **extra) -> dict:
        return {
            "source_image_id": "1",
            "bbox": {"x1": 0.0, "y1": 0.0, "x2": 10.0, "y2": 10.0},
            "algorithm": {"name": DETECTOR.name, "key": DETECTOR.key},
            "timestamp": datetime.datetime.now().isoformat(),
            **extra,
        }

    def test_embeddings_are_optional(self):
        self.assertIsNone(DetectionResponse.parse_obj(self._detection()).embeddings)
        parsed = DetectionResponse.parse_obj(self._detection(embeddings=_embedding_payload([0.5] * 512)))
        self.assertEqual(len(parsed.embeddings or []), 1)

    def test_a_vector_half_precision_cannot_store_is_refused(self):
        for vector in ([], [float("nan")] * 4, [float("inf")] * 4, [1e6] * 4):
            with self.subTest(vector=vector[:1]), self.assertRaises(pydantic.ValidationError):
                DetectionResponse.parse_obj(self._detection(embeddings=_embedding_payload(vector)))
        DetectionResponse.parse_obj(self._detection(embeddings=_embedding_payload([65504.0, -65504.0])))

    def test_two_vectors_from_one_algorithm_on_one_detection_are_refused(self):
        with self.assertRaises(pydantic.ValidationError):
            DetectionResponse.parse_obj(
                self._detection(embeddings=_embedding_payload([0.5] * 4) + _embedding_payload([0.25] * 4))
            )

    def test_a_declared_vector_length_must_be_positive(self):
        with self.assertRaises(pydantic.ValidationError):
            AlgorithmConfigResponse.parse_obj({**SPECIES.dict(), "embedding_dimensions": 0})


class TestDeclaredVectorLength(TestCase):
    """Registration records the vector length a processing service declares for each algorithm."""

    def test_a_new_algorithm_records_its_declared_length(self):
        self.assertEqual(get_or_create_algorithm_and_category_map(SPECIES).embedding_dimensions, LENGTH)

    def test_an_existing_algorithm_without_a_length_takes_the_declared_one(self):
        undeclared = get_or_create_algorithm_and_category_map(SPECIES.copy(update={"embedding_dimensions": None}))
        self.assertIsNone(undeclared.embedding_dimensions)
        self.assertEqual(get_or_create_algorithm_and_category_map(SPECIES).embedding_dimensions, LENGTH)
        # A service that stops declaring the length leaves the stored one in place.
        get_or_create_algorithm_and_category_map(SPECIES.copy(update={"embedding_dimensions": None}))
        self.assertEqual(Algorithm.objects.get(key=SPECIES.key).embedding_dimensions, LENGTH)

    def test_a_different_length_for_a_registered_algorithm_refuses_registration(self):
        """A new length is a new model, whose vectors could not be compared with the stored ones."""
        get_or_create_algorithm_and_category_map(SPECIES)
        with self.assertRaises(PipelineNotConfigured) as raised:
            get_or_create_algorithm_and_category_map(SPECIES.copy(update={"embedding_dimensions": 1024}))
        self.assertIn("new algorithm key", str(raised.exception))
        self.assertEqual(Algorithm.objects.get(key=SPECIES.key).embedding_dimensions, LENGTH)


class ClassifierPipelineMixin:
    """A classifier pipeline whose results carry a vector on each detection, as the processing service sends them."""

    LOW = [0.25] * LENGTH
    HIGH = [0.75] * LENGTH

    @classmethod
    def _set_up_pipeline(cls) -> None:
        with no_processing_service_http():
            cls.project, cls.deployment = setup_test_project(reuse=False)
        cls.pipeline = Pipeline.objects.create(name="Embedding test pipeline")
        cls.pipeline.algorithms.set(
            [get_or_create_algorithm_and_category_map(algorithm) for algorithm in (DETECTOR, BINARY, SPECIES)]
        )
        cls.species = Algorithm.objects.get(key=SPECIES.key)
        cls.images = 0

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
    detection, including those the moth/non-moth filter rejected. It must be stored once per
    detection and algorithm, on the detection it was sent with, and storing it must never add a
    classification or move a determination.
    """

    @classmethod
    def setUpTestData(cls) -> None:
        cls._set_up_pipeline()

    def test_every_detection_stores_its_vector_with_its_captures_project(self):
        """Including the rejected crop, which has no species classification that could carry one."""
        image = self._image()
        self._save(
            self._moth(image, _embedding_payload(self.LOW)),
            self._rejected(image, _embedding_payload(self.HIGH), box=100.0),
        )
        self.assertEqual(self._stored(image), {(0.0, SPECIES.key): self.LOW, (100.0, SPECIES.key): self.HIGH})
        self.assertEqual(set(DetectionEmbedding.objects.values_list("project_id", flat=True)), {self.project.pk})

    def test_two_models_store_their_vectors_side_by_side_on_one_detection(self):
        image = self._image()
        self._save(self._moth(image, _embedding_payload(self.LOW) + _embedding_payload([0.5] * 8, algorithm=BINARY)))
        self.assertEqual(self._stored(image), {(0.0, SPECIES.key): self.LOW, (0.0, BINARY.key): [0.5] * 8})

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

    def test_the_first_vector_and_its_job_are_kept(self):
        """A later run of the same algorithm writes nothing, so the row keeps the vector and job that
        stored it first. Deleting that job keeps the vector."""
        image = self._image()
        first, second = (
            Job.objects.create(project=self.project, name=f"Embedding job {n}", pipeline=self.pipeline) for n in (1, 2)
        )
        self._save(self._moth(image, _embedding_payload(self.LOW)), job_id=first.pk)
        stored = DetectionEmbedding.objects.get()
        self._save(self._moth(image, _embedding_payload(self.HIGH)), job_id=second.pk)

        kept = DetectionEmbedding.objects.get()
        self.assertEqual((kept.pk, list(kept.vector), kept.job_id), (stored.pk, self.LOW, first.pk))
        self.assertEqual(kept.updated_at, stored.updated_at)

        first.delete()
        kept.refresh_from_db()
        self.assertIsNone(kept.job_id)
        self.assertEqual(list(kept.vector), self.LOW)

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

    def test_an_existing_box_returned_twice_stores_one_vector(self):
        """Both copies of a repeated box are saved as the one stored detection, so one insert holds the
        same (detection, algorithm) twice; the first is kept and the insert does not fail."""
        image = self._image()
        self._save(self._rejected(image, box=5.0))
        self._save(
            self._rejected(image, _embedding_payload(self.LOW), box=5.0),
            self._rejected(image, _embedding_payload(self.HIGH), box=5.0),
        )
        self.assertEqual(len(self._stored(image)), 1)

    def test_a_vector_that_cannot_be_stored_stops_the_batch_before_anything_is_saved(self):
        """An unregistered algorithm, a vector of another length than its algorithm declares, and an
        algorithm that declares no length each raise before any detection or classification is written."""
        undeclared = get_or_create_algorithm_and_category_map(
            AlgorithmConfigResponse(name="Undeclared extractor", key="undeclared-extractor", task_type="embedding")
        )
        self.pipeline.algorithms.add(undeclared)
        unregistered = AlgorithmConfigResponse(name="Unregistered", key="unregistered-embedder")
        cases = [
            (PipelineNotConfigured, _embedding_payload(self.LOW, algorithm=unregistered)),
            (EmbeddingDimensionMismatch, _embedding_payload([0.5] * 512)),
            (EmbeddingDimensionMismatch, [{"algorithm": {"name": "x", "key": undeclared.key}, "features": [0.5]}]),
        ]
        for error, embeddings in cases:
            image = self._image()
            with self.subTest(error=error.__name__, key=embeddings[0]["algorithm"]["key"]):
                with self.assertRaises(error):
                    self._save(self._moth(image, embeddings), self._moth(image, box=100.0))
                self.assertFalse(Detection.objects.filter(source_image=image).exists())
                self.assertFalse(Classification.objects.filter(detection__source_image=image).exists())
        self.assertFalse(DetectionEmbedding.objects.exists())

    def test_a_capture_without_a_project_refuses_its_vectors(self):
        """A vector's project is its capture's, with no fallback, so a capture without one cannot store vectors."""
        image = self._image()
        SourceImage.objects.filter(pk=image.pk).update(project=None)
        with self.assertRaisesMessage(ValueError, f"Capture #{image.pk} belongs to no project"):
            self._save(self._moth(image, _embedding_payload(self.LOW)))
        self.assertFalse(DetectionEmbedding.objects.exists())

    def test_storing_vectors_takes_one_insert_however_many_detections(self):
        image = self._image()
        boxes = [float(20 * i) for i in range(5)]
        self._save(*[self._rejected(image, box=box) for box in boxes])
        detections = list(Detection.objects.filter(source_image=image).select_related("source_image").order_by("bbox"))
        parsed = [
            DetectionResponse.parse_obj(self._rejected(image, _embedding_payload(self.LOW), box=b)) for b in boxes
        ]
        algorithms_known = {algorithm.key: algorithm for algorithm in self.pipeline.algorithms.all()}
        pairs = list(zip(detections, parsed))

        with self.assertNumQueries(0):
            validate_detection_embeddings(parsed, algorithms_known)
        with self.assertNumQueries(1):
            create_detection_embeddings(pairs[:1], algorithms_known)
        with self.assertNumQueries(1):
            create_detection_embeddings(pairs, algorithms_known)
        self.assertEqual(DetectionEmbedding.objects.count(), 5)


class TestReadingVectors(TestCase):
    """The pattern to copy for reading vectors: one algorithm, a set of detections, one query.

    The unique index on (detection, algorithm) serves it at any scale; see
    docs/claude/reference/feature-vectors.md for the measured plans of this and the other known reads.
    """

    @classmethod
    def setUpTestData(cls) -> None:
        with no_processing_service_http():
            cls.project, cls.deployment = setup_test_project(reuse=False)
        image = SourceImage.objects.create(path="read.jpg", deployment=cls.deployment, project=cls.project)
        cls.eight = Algorithm.objects.create(name="Eight", key="eight", task_type="embedding", embedding_dimensions=8)
        cls.four = Algorithm.objects.create(name="Four", key="four", task_type="embedding", embedding_dimensions=4)
        cls.detections = [
            Detection.objects.create(source_image=image, bbox=[float(i), 0.0, 500.0 + i, 10.0]) for i in range(12)
        ]
        rows = [
            DetectionEmbedding(detection=d, algorithm=cls.eight, project=cls.project, vector=[i / 4] * 8)
            for i, d in enumerate(cls.detections)
        ]
        rows += [
            DetectionEmbedding(detection=d, algorithm=cls.four, project=cls.project, vector=[0.5] * 4)
            for d in cls.detections[::2]
        ]
        DetectionEmbedding.objects.bulk_create(rows)

    @staticmethod
    def _vectors(detection_ids: list[int], algorithm_id: int) -> dict[int, np.ndarray]:
        rows = (
            DetectionEmbedding.objects.for_algorithm(algorithm_id)
            .filter(detection_id__in=detection_ids)
            .order_by()
            .values_list("detection_id", "vector")
        )
        return {detection_id: np.asarray(vector, dtype=np.float32) for detection_id, vector in rows}

    def test_one_algorithms_vectors_for_a_set_of_detections_in_one_query(self):
        """The vector table is never cached (CACHALOT_UNCACHABLE_TABLES), so each read runs its query."""
        for size in (3, 12):
            ids = [d.pk for d in self.detections[:size]]
            with self.assertNumQueries(1):
                eight = self._vectors(ids, self.eight.pk)
            self.assertEqual(len(eight), size)
            self.assertEqual({v.shape for v in eight.values()}, {(8,)})
            self.assertEqual({v.dtype for v in eight.values()}, {np.dtype(np.float32)})
            self.assertEqual(float(eight[ids[1]][0]), 0.25)
            # Detections without a vector from the other model are absent, never filled with another model's.
            self.assertEqual(sorted(self._vectors(ids, self.four.pk)), ids[::2])


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


class TestEmbeddingAdmin(TestCase):
    """The admin lists vectors without loading them and cannot change them."""

    @classmethod
    def setUpTestData(cls) -> None:
        with no_processing_service_http():
            cls.project, cls.deployment = setup_test_project(reuse=False)
        image = SourceImage.objects.create(path="admin.jpg", deployment=cls.deployment, project=cls.project)
        cls.algorithm = Algorithm.objects.create(
            name="Admin backbone", key="admin-backbone", task_type="embedding", embedding_dimensions=4
        )
        cls.detections = [
            Detection.objects.create(source_image=image, bbox=[float(i), 0.0, float(i) + 10.0, 10.0]) for i in range(6)
        ]
        cls.superuser = User.objects.create_superuser(email="vector-admin@insectai.org", password="secret")

    def _store(self, count: int) -> None:
        DetectionEmbedding.objects.all().delete()
        DetectionEmbedding.objects.bulk_create(
            DetectionEmbedding(detection=detection, algorithm=self.algorithm, project=self.project, vector=[0.5] * 4)
            for detection in self.detections[:count]
        )

    def _changelist(self):
        self.client.force_login(self.superuser)
        with no_query_cache(), CaptureQueriesContext(connection) as queries:
            response = self.client.get("/admin/ml/detectionembedding/")
        self.assertEqual(response.status_code, 200)
        return response, queries.captured_queries

    def test_the_changelist_takes_the_same_queries_for_any_number_of_rows_and_never_selects_the_vector(self):
        self._store(2)
        response, two = self._changelist()
        self.assertContains(response, "Admin backbone")
        self._store(6)
        _, six = self._changelist()
        self.assertEqual(len(two), len(six))
        for query in six:
            self.assertNotIn('"ml_detectionembedding"."vector"', query["sql"])

    def test_the_admin_cannot_add_change_or_delete_vectors_and_shows_only_the_length(self):
        self._store(1)
        embedding = DetectionEmbedding.objects.get()
        self.client.force_login(self.superuser)
        self.assertEqual(self.client.get("/admin/ml/detectionembedding/add/").status_code, 403)
        self.assertEqual(self.client.post(f"/admin/ml/detectionembedding/{embedding.pk}/delete/").status_code, 403)
        response = self.client.get(f"/admin/ml/detectionembedding/{embedding.pk}/change/")
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "0.5, 0.5")
        self.assertContains(response, "Vector length")
        self.assertEqual(self.client.post(f"/admin/ml/detectionembedding/{embedding.pk}/change/", {}).status_code, 403)


class TestConcurrentWriters(ClassifierPipelineMixin, TransactionTestCase):
    """Several workers saving results at once, as the async job path does in production.

    Two inserts that share rows but take them in different orders can each hold a row the other
    needs, and Postgres then aborts one with a deadlock. The writer inserts in one fixed order, so
    concurrent writers wait for each other instead, and the first vector for each row is kept.
    """

    ROWS = 600
    ROUNDS = 3

    def setUp(self) -> None:
        self._set_up_pipeline()
        image = self._image()
        boxes = [float(i) for i in range(self.ROWS)]
        self._save(*[self._rejected(image, box=box) for box in boxes])
        detections = {
            d.bbox[0]: d for d in Detection.objects.filter(source_image=image).select_related("source_image")
        }
        self.algorithms_known = {algorithm.key: algorithm for algorithm in self.pipeline.algorithms.all()}
        self.pairs_by_vector = {
            value: [
                (
                    detections[box],
                    DetectionResponse.parse_obj(
                        self._rejected(image, _embedding_payload([value] * 8, BINARY), box=box)
                    ),
                )
                for box in boxes
            ]
            for value in (0.25, 0.75)
        }

    def _race(self, orders: list[list[int]]) -> list[BaseException]:
        """Run one writer per order at the same moment, each in its own connection; return their errors."""
        barrier = threading.Barrier(len(orders))
        errors: list[BaseException] = []

        def write(value: float, order: list[int]) -> None:
            pairs = self.pairs_by_vector[value]
            try:
                barrier.wait()
                create_detection_embeddings([pairs[i] for i in order], self.algorithms_known)
            except BaseException as error:  # noqa: B036 - collected and asserted in the test thread
                errors.append(error)
            finally:
                connection.close()

        threads = [
            threading.Thread(target=write, args=(value, order))
            for value, order in zip([0.25, 0.75] * len(orders), orders)
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=60)
        return errors

    def test_concurrent_writers_of_the_same_rows_in_different_orders_neither_fail_nor_duplicate(self):
        forward = list(range(self.ROWS))
        for round_number in range(self.ROUNDS):
            DetectionEmbedding.objects.all().delete()
            shuffled = random.Random(round_number).sample(forward, len(forward))
            errors = self._race([forward, list(reversed(forward)), shuffled, forward[::-1]])
            self.assertEqual(errors, [], f"round {round_number}")
            rows = DetectionEmbedding.objects.values_list("detection_id", "vector")
            self.assertEqual(len(rows), self.ROWS)
            self.assertTrue(all(set(vector) <= {0.25, 0.75} for _, vector in rows))
