"""How detection feature vectors are stored and read back.

These pin that a vector is stored once per detection and algorithm on the detection it
was sent with, never as a classification; that its project is copied from the detection's
capture; that writes are insert-mostly; and that readers return one algorithm at a time.
"""

import contextlib
import datetime

import numpy as np
import pydantic
from django.db import connection
from django.test import SimpleTestCase, TestCase
from django.test.utils import CaptureQueriesContext
from rest_framework import status
from rest_framework.test import APITestCase

from ami.jobs.models import Job
from ami.main.models import Classification, Deployment, Detection, Occurrence, SourceImage
from ami.ml.embeddings.reader import (
    algorithm_with_most_vectors,
    detections_missing_vectors,
    project_vectors,
    vector_counts_by_algorithm,
    vectors_for_detections,
)
from ami.ml.embeddings.writer import EmbeddingDimensionMismatch, create_detection_embeddings
from ami.ml.exceptions import PipelineNotConfigured
from ami.ml.models import Algorithm, DetectionEmbedding, Pipeline
from ami.ml.models.pipeline import get_or_create_algorithm_and_category_map, save_results
from ami.ml.schemas import DetectionResponse, PipelineResultsResponse
from ami.tests.fixtures.main import (
    create_captures,
    create_occurrences,
    create_taxa,
    no_processing_service_http,
    setup_test_project,
)
from ami.tests.fixtures.ml import ALGORITHM_CHOICES
from ami.users.models import User

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

    def test_the_field_is_optional_and_refuses_an_empty_vector(self):
        """Any length parses (extractors differ; each algorithm's length is checked on save), but not none,
        and a service that sends no embeddings still parses."""
        self.assertIsNone(DetectionResponse.parse_obj(self._detection()).embeddings)
        parsed = DetectionResponse.parse_obj(self._detection(embeddings=_embedding_payload([0.5] * 512)))
        self.assertEqual(len(parsed.embeddings or []), 1)
        with self.assertRaises(pydantic.ValidationError):
            DetectionResponse.parse_obj(self._detection(embeddings=_embedding_payload([])))


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
    detection, including those the moth/non-moth filter rejected. What these pin is that it
    is stored once per detection and algorithm, on the detection it was sent with, and that
    storing it never adds a classification or moves a determination.
    """

    @classmethod
    def setUpTestData(cls) -> None:
        cls._set_up_pipeline()

    def test_every_detection_stores_its_vector_including_a_rejected_crop(self):
        """Including the rejected crop, which has no species classification that could carry one."""
        image = self._image()
        self._save(
            self._moth(image, _embedding_payload(self.LOW)),
            self._rejected(image, _embedding_payload(self.HIGH), box=100.0),
        )
        self.assertEqual(self._stored(image), {(0.0, SPECIES.key): self.LOW, (100.0, SPECIES.key): self.HIGH})
        self.assertEqual(set(DetectionEmbedding.objects.values_list("project_id", flat=True)), {self.project.pk})

    def test_two_models_store_their_vectors_side_by_side_on_one_detection(self):
        """Each model keeps its own row and its own length on the same detection."""
        image = self._image()
        self._save(self._moth(image, _embedding_payload(self.LOW) + _embedding_payload([0.5] * 8, algorithm=BINARY)))
        self.assertEqual(self._stored(image), {(0.0, SPECIES.key): self.LOW, (0.0, BINARY.key): [0.5] * 8})

    def test_two_vectors_from_one_model_on_one_detection_keep_the_last_and_warn(self):
        image = self._image()
        with self.assertLogs(level="WARNING") as logs:
            self._save(self._moth(image, _embedding_payload(self.LOW) + _embedding_payload(self.HIGH)))
        self.assertEqual(self._stored(image), {(0.0, SPECIES.key): self.HIGH})
        self.assertIn("more than one vector", "\n".join(logs.output))

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
        first, second, third = (
            Job.objects.create(project=self.project, name=f"Embedding job {n}", pipeline=self.pipeline)
            for n in (1, 2, 3)
        )
        self._save(self._moth(image, _embedding_payload(self.LOW)), job_id=first.pk)
        self._save(self._moth(image, _embedding_payload(self.HIGH)), job_id=second.pk)

        detection = Detection.objects.get(source_image=image)
        embedding = DetectionEmbedding.objects.get(detection=detection)
        self.assertEqual(embedding.job_id, second.pk, "A replaced vector records the job that replaced it")

        self._save(self._moth(image, _embedding_payload(self.HIGH)), job_id=third.pk)
        embedding.refresh_from_db()
        self.assertEqual(embedding.job_id, second.pk, "An unchanged vector keeps the job that stored it")

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

    def test_an_algorithm_and_key_keep_the_length_of_their_first_vector(self):
        """Vectors of another length are refused, because they could never be compared."""
        image, other = self._image(), self._image()
        self._save(self._moth(image, _embedding_payload([0.5] * 512)))

        with self.assertRaises(EmbeddingDimensionMismatch) as raised:
            self._save(self._moth(other, _embedding_payload(self.LOW)))
        self.assertIn(self.species.key, str(raised.exception))
        self.assertIn("512", str(raised.exception))
        self.assertIn(str(LENGTH), str(raised.exception))
        self.assertFalse(DetectionEmbedding.objects.filter(detection__source_image=other).exists())

    def test_a_batch_with_no_stored_vector_must_agree_on_one_length(self):
        image = self._image()
        with self.assertRaises(EmbeddingDimensionMismatch):
            self._save(
                self._rejected(image, _embedding_payload([0.5] * 8), box=0.0),
                self._rejected(image, _embedding_payload([0.5] * 4), box=100.0),
            )
        self.assertFalse(DetectionEmbedding.objects.exists())

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

        # Measure after a first write, on other detections so no read is served from the query cache.
        create_detection_embeddings(detections[:1], parsed[:1], algorithms_known)
        DetectionEmbedding.objects.all().delete()
        with CaptureQueriesContext(connection) as one:
            create_detection_embeddings(detections[1:2], parsed[1:2], algorithms_known)
        DetectionEmbedding.objects.all().delete()
        with CaptureQueriesContext(connection) as five:
            stored = create_detection_embeddings(detections, parsed, algorithms_known)
        self.assertEqual(len(five), len(one))
        self.assertEqual(len(stored), 5)

        # A rerun with identical vectors reads the length and the stored rows and writes nothing.
        with self.assertNumQueries(2):
            create_detection_embeddings(detections, parsed, algorithms_known)

    def test_a_vector_matches_its_box_exactly_after_a_json_round_trip(self):
        image = self._image()
        self._save(self._rejected(image, box=0.1234567))
        sent = DetectionResponse.parse_obj(self._rejected(image, _embedding_payload(self.LOW), box=0.1234567))
        round_tripped = DetectionResponse.parse_raw(sent.json())
        detections = list(Detection.objects.filter(source_image=image))
        algorithms_known = {algorithm.key: algorithm for algorithm in self.pipeline.algorithms.all()}

        stored = create_detection_embeddings(detections, [round_tripped], algorithms_known)
        self.assertEqual([embedding.detection_id for embedding in stored], [detections[0].pk])

    def test_two_nearby_boxes_each_get_their_own_vector(self):
        image = self._image()
        near, nearer = 10.0001, 10.0002
        self._save(self._rejected(image, box=near), self._rejected(image, box=nearer))
        self._save(
            self._rejected(image, _embedding_payload(self.LOW), box=near),
            self._rejected(image, _embedding_payload(self.HIGH), box=nearer),
        )
        self.assertEqual(self._stored(image), {(near, SPECIES.key): self.LOW, (nearer, SPECIES.key): self.HIGH})

    def test_a_box_stored_twice_is_skipped_and_logged_not_guessed(self):
        image = self._image()
        self._save(self._rejected(image, box=5.0))
        original = Detection.objects.get(source_image=image)
        Detection.objects.create(
            source_image=image, bbox=original.bbox, detection_algorithm=original.detection_algorithm
        )
        sent = DetectionResponse.parse_obj(self._rejected(image, _embedding_payload(self.LOW), box=5.0))
        algorithms_known = {algorithm.key: algorithm for algorithm in self.pipeline.algorithms.all()}

        with self.assertLogs("ami.ml.embeddings.writer", level="WARNING") as logs:
            stored = create_detection_embeddings(
                list(Detection.objects.filter(source_image=image)), [sent], algorithms_known
            )
        self.assertEqual(stored, [])
        self.assertFalse(DetectionEmbedding.objects.exists())
        self.assertIn(f"capture {image.pk}", "\n".join(logs.output))

    def test_an_existing_box_returned_twice_is_one_detection_and_keeps_its_vector(self):
        """Detection creation returns the stored detection once per response, so a repeated box
        must not look like two detections sharing it."""
        image = self._image()
        self._save(self._rejected(image, box=5.0))
        self._save(
            self._rejected(image, _embedding_payload(self.LOW), box=5.0),
            self._rejected(image, _embedding_payload(self.LOW), box=5.0),
        )
        self.assertEqual(self._stored(image), {(5.0, SPECIES.key): self.LOW})

    def test_only_the_first_write_of_an_algorithm_and_key_takes_the_advisory_lock(self):
        image, other = self._image(), self._image()
        self._save(self._rejected(image), self._rejected(other))

        def locks(queries) -> int:
            return sum("pg_advisory_xact_lock" in query["sql"] for query in queries)

        with CaptureQueriesContext(connection) as first:
            self._save(self._rejected(image, _embedding_payload(self.LOW)))
        with CaptureQueriesContext(connection) as later:
            self._save(self._rejected(other, _embedding_payload(self.LOW)))
        self.assertEqual(locks(first.captured_queries), 1)
        self.assertEqual(locks(later.captured_queries), 0)


class TestEmbeddingProject(TestCase):
    """An embedding's project is its capture's, falling back to the capture's station's."""

    @classmethod
    def setUpTestData(cls) -> None:
        with no_processing_service_http():
            cls.project, cls.deployment = setup_test_project(reuse=False)
        cls.image = SourceImage.objects.create(path="project-fill.jpg", deployment=cls.deployment, project=cls.project)
        cls.detection = Detection.objects.create(source_image=cls.image, bbox=[0.0, 0.0, 10.0, 10.0])
        cls.algorithm = Algorithm.objects.create(name="Backbone", key="backbone", task_type="embedding")

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


@contextlib.contextmanager
def cache_off():
    """Run a block with cachalot off, restoring it even when the block raises, so query counts are real."""
    from cachalot.api import cachalot_disabled

    disabled = cachalot_disabled()
    disabled.__enter__()
    try:
        yield
    finally:
        disabled.__exit__(None, None, None)


class TestQueryHelpers(TestCase):
    """The functions in ``ami.ml.embeddings.reader``: each reads one algorithm in a fixed number of queries.

    The fixture mixes two models of different lengths, so a helper that merged models would return
    the wrong lengths or counts.
    """

    @classmethod
    def setUpTestData(cls) -> None:
        with no_processing_service_http():
            cls.project, cls.deployment = setup_test_project(reuse=False)
        cls.image = SourceImage.objects.create(path="helpers.jpg", deployment=cls.deployment, project=cls.project)
        cls.eight = Algorithm.objects.create(name="Eight", key="eight", task_type="embedding")
        cls.four = Algorithm.objects.create(name="Four", key="four", task_type="embedding")
        cls.detections: list[Detection] = []

    def _detections(self, count: int) -> list[Detection]:
        made = [
            Detection.objects.create(
                source_image=self.image, bbox=[float(len(self.detections) + i), 0.0, 500.0 + i, 10.0]
            )
            for i in range(count)
        ]
        self.detections += made
        return made

    def _store(self, detections, algorithm, length):
        DetectionEmbedding.objects.store(
            [
                DetectionEmbedding(detection=d, algorithm=algorithm, vector=[float(i % 7) / 4] * length)
                for i, d in enumerate(detections)
            ]
        )

    def _fill(self, count: int):
        """``count`` detections with an 8-d vector from one model, and every other one also with a
        4-d vector from another."""
        detections = self._detections(count)
        self._store(detections, self.eight, 8)
        self._store(detections[::2], self.four, 4)
        return detections

    def test_vectors_for_detections_returns_one_models_vectors_as_float32(self):
        detections = self._fill(3)
        ids = [d.pk for d in detections]
        eight = vectors_for_detections(ids, self.eight.pk)
        self.assertEqual({v.shape for v in eight.values()}, {(8,)})
        self.assertEqual({v.dtype for v in eight.values()}, {np.dtype(np.float32)})
        self.assertEqual(float(eight[ids[1]][0]), 0.25)
        self.assertEqual(sorted(vectors_for_detections(ids, self.four.pk)), [ids[0], ids[2]])

    def test_vectors_for_detections_takes_one_query_at_any_size(self):
        counts = []
        for size in (3, 12):
            ids = [d.pk for d in self._fill(size)]
            with cache_off(), CaptureQueriesContext(connection) as queries:
                vectors = vectors_for_detections(ids, self.eight.pk)
            self.assertEqual(len(vectors), size)
            counts.append(len(queries))
        self.assertEqual(counts, [1, 1])

    def test_project_vectors_yields_every_row_once_in_id_order_in_bounded_chunks(self):
        detections = self._fill(7)
        chunks = list(project_vectors(self.project.pk, self.eight.pk, chunk_size=3))
        self.assertEqual([len(ids) for ids, _ in chunks], [3, 3, 1])
        all_ids = [i for ids, _ in chunks for i in ids]
        self.assertEqual(all_ids, sorted(d.pk for d in detections))
        for ids, array in chunks:
            self.assertEqual(array.shape, (len(ids), 8))
            self.assertEqual(array.dtype, np.dtype(np.float32))
        # A chunk size that divides the rows exactly ends without an empty chunk.
        self.assertEqual([len(i) for i, _ in project_vectors(self.project.pk, self.eight.pk, chunk_size=7)], [7])
        unused = Algorithm.objects.create(name="Unused", key="unused", task_type="embedding")
        self.assertEqual(list(project_vectors(self.project.pk, unused.pk)), [])

    def test_project_vectors_keeps_models_apart_and_honours_the_id_scope(self):
        detections = self._fill(6)
        ((ids, array),) = project_vectors(self.project.pk, self.four.pk)
        self.assertEqual(ids, [d.pk for d in detections[::2]])
        self.assertEqual(array.shape, (3, 4))
        wanted = [detections[0].pk, detections[1].pk, detections[2].pk]
        ((ids, _),) = project_vectors(self.project.pk, self.four.pk, detection_ids=wanted)
        self.assertEqual(ids, [detections[0].pk, detections[2].pk])

    def test_counts_are_per_algorithm(self):
        self._fill(5)
        self.assertEqual(vector_counts_by_algorithm(self.project.pk), {self.eight.pk: 5, self.four.pk: 3})
        self.assertEqual(algorithm_with_most_vectors(self.project), self.eight.pk)

    def test_the_default_algorithm_breaks_ties_by_lowest_id(self):
        detections = self._detections(2)
        self._store(detections, self.four, 4)
        self._store(detections, self.eight, 8)
        self.assertEqual(algorithm_with_most_vectors(self.project), min(self.four.pk, self.eight.pk))

    def test_detections_missing_vectors_keeps_the_callers_scope(self):
        detections = self._fill(4)
        scope = Detection.objects.filter(source_image=self.image)
        missing = detections_missing_vectors(scope, self.four.pk)
        self.assertEqual({d.pk for d in missing}, {detections[1].pk, detections[3].pk})
        self.assertEqual(list(detections_missing_vectors(scope, self.eight.pk)), [])
        self.assertEqual(
            {d.pk for d in detections_missing_vectors(scope.filter(pk__lte=detections[1].pk), self.four.pk)},
            {detections[1].pk},
        )

    def test_detections_missing_vectors_is_never_served_from_the_query_cache(self):
        """The vector table is uncachable, which only holds if django-cachalot sees it in the query.

        It does not see tables inside a negated ``Exists`` in ``filter()``; written that way, a
        cached "missing" result would outlive new vectors and the next run would send the same
        detections again.
        """
        from cachalot.utils import UncachableQuery, _get_tables

        query = detections_missing_vectors(Detection.objects.all(), self.four.pk).query
        with self.assertRaises(UncachableQuery):
            _get_tables(connection.alias, query)


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


class TestEmbeddingsInOccurrenceApi(APITestCase):
    """What the occurrence endpoints say about stored vectors: the algorithms on the detail view, and the
    algorithm filter finding an occurrence by an embedding-only model."""

    @classmethod
    def setUpTestData(cls) -> None:
        with no_processing_service_http():
            cls.project, cls.deployment = setup_test_project(reuse=False)
        cls.project.default_filters_score_threshold = 0.0
        cls.project.save()
        create_taxa(project=cls.project)
        create_captures(deployment=cls.deployment, num_nights=1, images_per_night=3)
        create_occurrences(deployment=cls.deployment, num=3, determination_score=0.9)
        cls.both, cls.one, cls.none = list(Occurrence.objects.filter(project=cls.project).order_by("pk"))
        cls.backbone = Algorithm.objects.create(name="Backbone", key="backbone", task_type="embedding")
        cls.other = Algorithm.objects.create(name="Other backbone", key="other-backbone", task_type="embedding")
        both_detection, one_detection = (occurrence.detections.get() for occurrence in (cls.both, cls.one))
        DetectionEmbedding.objects.store(
            [
                DetectionEmbedding(detection=both_detection, algorithm=cls.backbone, vector=[1.0, 0.0]),
                DetectionEmbedding(detection=both_detection, algorithm=cls.other, vector=[1.0, 0.0]),
                DetectionEmbedding(detection=one_detection, algorithm=cls.other, vector=[0.0, 1.0]),
            ]
        )

    def _detail(self, occurrence: Occurrence) -> dict:
        response = self.client.get(f"/api/v2/occurrences/{occurrence.pk}/?project_id={self.project.pk}")
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        return response.json()

    def _list_ids(self, query: str) -> set[int]:
        response = self.client.get(f"/api/v2/occurrences/?project_id={self.project.pk}&{query}")
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        return {int(row["id"]) for row in response.json()["results"]}

    def test_the_detail_lists_each_algorithm_that_has_a_vector_and_nothing_without_vectors(self):
        self.assertEqual(self._detail(self.none)["embedding_algorithms"], [])
        self.assertEqual(
            self._detail(self.both)["embedding_algorithms"],
            [{"id": self.backbone.pk, "name": "Backbone"}, {"id": self.other.pk, "name": "Other backbone"}],
        )
        self.assertEqual(
            self._detail(self.one)["embedding_algorithms"], [{"id": self.other.pk, "name": "Other backbone"}]
        )

    def test_the_field_costs_one_query_whatever_the_number_of_algorithms(self):
        def vector_queries(occurrence: Occurrence) -> int:
            with cache_off(), CaptureQueriesContext(connection) as queries:
                self._detail(occurrence)
            return sum("ml_detectionembedding" in query["sql"] for query in queries.captured_queries)

        self.assertEqual(vector_queries(self.none), 1)
        self.assertEqual(vector_queries(self.both), 1)

    def test_the_list_view_does_not_carry_the_field(self):
        response = self.client.get(f"/api/v2/occurrences/?project_id={self.project.pk}")
        self.assertNotIn("embedding_algorithms", response.json()["results"][0])

    def test_the_algorithm_filter_finds_occurrences_by_their_vectors_and_excludes_them(self):
        self.assertEqual(self._list_ids(f"algorithm={self.backbone.pk}"), {self.both.pk})
        self.assertEqual(self._list_ids(f"algorithm={self.other.pk}"), {self.both.pk, self.one.pk})
        self.assertEqual(self._list_ids(f"not_algorithm={self.other.pk}"), {self.none.pk})

    def test_the_filter_sees_a_vector_stored_after_a_cached_answer(self):
        """The query cache must know the filter reads the vector table, including under exclude()."""
        self.assertEqual(self._list_ids(f"not_algorithm={self.backbone.pk}"), {self.one.pk, self.none.pk})
        DetectionEmbedding.objects.store(
            [DetectionEmbedding(detection=self.none.detections.get(), algorithm=self.backbone, vector=[1.0, 1.0])]
        )
        self.assertEqual(self._list_ids(f"not_algorithm={self.backbone.pk}"), {self.one.pk})


class TestEmbeddingAdmin(TestCase):
    """The admin lists vectors without loading them and cannot change them."""

    @classmethod
    def setUpTestData(cls) -> None:
        with no_processing_service_http():
            cls.project, cls.deployment = setup_test_project(reuse=False)
        image = SourceImage.objects.create(path="admin.jpg", deployment=cls.deployment, project=cls.project)
        cls.algorithm = Algorithm.objects.create(name="Admin backbone", key="admin-backbone", task_type="embedding")
        cls.detections = [
            Detection.objects.create(source_image=image, bbox=[float(i), 0.0, float(i) + 10.0, 10.0]) for i in range(6)
        ]
        cls.superuser = User.objects.create_superuser(email="vector-admin@insectai.org", password="secret")

    def _store(self, count: int) -> None:
        DetectionEmbedding.objects.all().delete()
        DetectionEmbedding.objects.store(
            [
                DetectionEmbedding(detection=detection, algorithm=self.algorithm, vector=[0.5] * 4)
                for detection in self.detections[:count]
            ]
        )

    def _changelist(self):
        self.client.force_login(self.superuser)
        with cache_off(), CaptureQueriesContext(connection) as queries:
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
            # The vector's length is computed in SQL; the column itself is never read.
            sql = query["sql"].replace('vector_dims("ml_detectionembedding"."vector")', "")
            self.assertNotIn('"ml_detectionembedding"."vector"', sql)

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
