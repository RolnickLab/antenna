"""Domain tests for the "Add feature vectors" post-processing task.

The task sends detections that already exist, and only those that lack a vector, to a feature-only
processing service and stores the vectors that come back. The service is stubbed with a response in
the shape ADC's feature-only pipeline returns: each requested detection echoed unchanged, still
naming the detector, with an embedding attached and no classifications.
"""
import datetime
from unittest import mock

from cachalot.api import cachalot_disabled
from django.contrib import admin as django_admin
from django.db import connection
from django.test import Client, TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from ami.jobs.models import Job
from ami.main.models import Classification, Detection, Occurrence, SourceImage, SourceImageCollection
from ami.ml.exceptions import PipelineNotConfigured
from ami.ml.models import Algorithm, DetectionEmbedding, Pipeline, ProcessingService, ProjectPipelineConfig
from ami.ml.models.algorithm import AlgorithmTaskType
from ami.ml.models.pipeline import get_or_create_algorithm_and_category_map
from ami.ml.post_processing.feature_vectors import AddFeatureVectorsTask
from ami.tests.fixtures.main import no_processing_service_http, setup_test_project
from ami.tests.fixtures.ml import ALGORITHM_CHOICES
from ami.users.models import User

DETECTOR = ALGORITHM_CHOICES["random-detector"]
LENGTH = 8
VECTOR = [0.5] * LENGTH


class FakeFeaturePipelineService:
    """Stands in for the processing service's synchronous ``/process`` endpoint.

    Mirrors ``run_feature_pipeline``: the requested detections come back with their box and detector
    reference unchanged, an ``embeddings`` entry from the extractor, and no classifications.
    """

    def __init__(self, extractor_key: str):
        self.extractor_key = extractor_key
        self.requests: list[dict] = []
        self.extra_detections: list[dict] = []
        self.embedding_key_override: str | None = None
        self.status_ok = True

    def post(self, url: str, json: dict):
        self.requests.append(json)
        key = self.embedding_key_override or self.extractor_key
        detections = [
            {
                "source_image_id": requested["source_image"]["id"],
                "bbox": requested["bbox"],
                "algorithm": requested["algorithm"],
                "crop_image_url": requested["crop_image_url"],
                "timestamp": datetime.datetime.now().isoformat(),
                "classifications": [],
                "embeddings": [{"algorithm": {"name": "Extractor", "key": key}, "features": VECTOR}],
            }
            for requested in json["detections"]
        ] + self.extra_detections
        body = {
            "pipeline": json["pipeline"],
            "total_time": 0.1,
            "source_images": [{"id": image["id"], "url": image["url"]} for image in json["source_images"]],
            "detections": detections,
        }
        return mock.Mock(ok=self.status_ok, json=lambda: body, status_code=200 if self.status_ok else 500)

    @property
    def detections_sent(self) -> int:
        return sum(len(request["detections"]) for request in self.requests)


class FeatureVectorsFixture:
    """A project with a feature-only pipeline, its processing service stubbed, and captures with detections."""

    @classmethod
    def _set_up_data(cls) -> None:
        # Creating a service checks its status over the network right away; there is no network here.
        with no_processing_service_http():
            cls.project, cls.deployment = setup_test_project(reuse=False)
            cls.detector = get_or_create_algorithm_and_category_map(DETECTOR)
            cls.extractor = Algorithm.objects.create(
                name="Extractor", key="extractor", task_type=AlgorithmTaskType.EMBEDDING.value
            )
            cls.pipeline = Pipeline.objects.create(name="Feature pipeline")
            cls.pipeline.algorithms.set([cls.extractor])
            cls.service = ProcessingService.objects.create(
                name="Feature service", endpoint_url="http://features.test:2000", last_seen_live=True
            )
            ProcessingService.objects.filter(pk=cls.service.pk).update(last_seen_live=True)
            cls.service.projects.add(cls.project)
            cls.service.pipelines.add(cls.pipeline)
        cls.captures = 0

    def _set_up_stubs(self) -> None:
        """Per-test stand-ins for the processing service: a fake session and no status checks."""
        status_patcher = mock.patch.object(ProcessingService, "get_status")
        status_patcher.start()
        self.addCleanup(status_patcher.stop)  # type: ignore[attr-defined]
        self.fake = FakeFeaturePipelineService(self.extractor.key)
        patcher = mock.patch("ami.ml.models.pipeline.create_session", return_value=self.fake)
        patcher.start()
        self.addCleanup(patcher.stop)  # type: ignore[attr-defined]

    def _collection(self, captures: int, detections_per_capture: int = 2) -> SourceImageCollection:
        images = []
        for _ in range(captures):
            self.captures += 1
            image = SourceImage.objects.create(
                path=f"fv-{self.captures}-20240101{self.captures:06d}.jpg",
                deployment=self.deployment,
                project=self.project,
                public_base_url="http://images.test/",
            )
            for i in range(detections_per_capture):
                Detection.objects.create(
                    source_image=image,
                    bbox=[20.0 * i, 0.0, 20.0 * i + 10, 10.0],
                    detection_algorithm=self.detector,
                )
            images.append(image)
        collection = SourceImageCollection.objects.create(
            name=f"fv collection {self.captures}", project=self.project, method="manual"
        )
        collection.images.set(images)
        return collection

    def _config(self, collection: SourceImageCollection, **extra) -> dict:
        return {"source_image_collection_id": collection.pk, "pipeline_id": self.pipeline.pk, **extra}

    def _job(self, collection: SourceImageCollection, **extra) -> Job:
        return Job.objects.create(
            name="Add feature vectors",
            project=self.project,
            job_type_key="post_processing",
            params={"task": AddFeatureVectorsTask.key, "config": self._config(collection, **extra)},
        )

    def _run(self, collection: SourceImageCollection, **extra) -> Job:
        job = self._job(collection, **extra)
        job.run()
        job.refresh_from_db()
        return job

    def _metrics(self, job: Job) -> dict[str, int]:
        return {param.name: param.value for param in job.progress.stages[0].params}


class TestAddFeatureVectorsTask(FeatureVectorsFixture, TestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        cls._set_up_data()

    def setUp(self) -> None:
        self._set_up_stubs()

    def test_only_detections_missing_a_vector_are_sent(self):
        collection = self._collection(captures=1, detections_per_capture=3)
        stored, *missing = list(Detection.objects.filter(source_image__collections=collection).order_by("pk"))
        DetectionEmbedding.objects.create(detection=stored, algorithm=self.extractor, key="embedding", vector=VECTOR)

        self._run(collection)

        sent = [d["bbox"] for request in self.fake.requests for d in request["detections"]]
        self.assertCountEqual(
            sent, [{"x1": m.bbox[0], "y1": m.bbox[1], "x2": m.bbox[2], "y2": m.bbox[3]} for m in missing]
        )
        self.assertEqual(DetectionEmbedding.objects.filter(algorithm=self.extractor).count(), 3)

    def test_captures_with_nothing_missing_are_skipped(self):
        collection = self._collection(captures=2)
        done, todo = list(collection.images.order_by("pk"))
        for detection in done.detections.all():
            DetectionEmbedding.objects.create(
                detection=detection, algorithm=self.extractor, key="embedding", vector=VECTOR
            )

        job = self._run(collection)

        (request,) = self.fake.requests
        self.assertEqual([image["id"] for image in request["source_images"]], [str(todo.pk)])
        self.assertEqual(self._metrics(job)["Captures"], 1)

    def test_vectors_are_stored_on_the_detections_they_were_sent_for_and_reported(self):
        collection = self._collection(captures=3)

        job = self._run(collection)

        detections = Detection.objects.filter(source_image__collections=collection)
        self.assertEqual(
            set(DetectionEmbedding.objects.filter(algorithm=self.extractor).values_list("detection_id", flat=True)),
            set(detections.values_list("pk", flat=True)),
        )
        self.assertEqual(
            self._metrics(job),
            {
                "Captures": 3,
                "Detections sent": 6,
                "Vectors stored": 6,
                "Vectors unchanged": 0,
                "Boxes unmatched": 0,
            },
        )

    def test_no_detections_classifications_or_occurrences_are_created(self):
        collection = self._collection(captures=2)
        before = (Detection.objects.count(), Classification.objects.count(), Occurrence.objects.count())

        self._run(collection)

        self.assertEqual(
            (Detection.objects.count(), Classification.objects.count(), Occurrence.objects.count()), before
        )

    def test_a_returned_box_with_no_stored_detection_is_counted_and_not_created(self):
        collection = self._collection(captures=1)
        image = collection.images.get()
        self.fake.extra_detections = [
            {
                "source_image_id": str(image.pk),
                "bbox": {"x1": 500.0, "y1": 500.0, "x2": 510.0, "y2": 510.0},
                "algorithm": {"name": DETECTOR.name, "key": DETECTOR.key},
                "timestamp": datetime.datetime.now().isoformat(),
                "embeddings": [{"algorithm": {"name": "Extractor", "key": self.extractor.key}, "features": VECTOR}],
            }
        ]

        job = self._run(collection)

        self.assertEqual(self._metrics(job)["Boxes unmatched"], 1)
        self.assertEqual(Detection.objects.filter(source_image=image).count(), 2)
        self.assertEqual(DetectionEmbedding.objects.count(), 2)

    def test_an_embedding_from_an_algorithm_outside_the_pipeline_raises_and_stores_nothing(self):
        collection = self._collection(captures=1)
        self.fake.embedding_key_override = "not-in-pipeline"

        with self.assertRaises(PipelineNotConfigured):
            self._run(collection)

        self.assertEqual(DetectionEmbedding.objects.count(), 0)

    def test_a_second_run_sends_nothing(self):
        collection = self._collection(captures=2)
        self._run(collection)
        requests_after_first = len(self.fake.requests)

        self._run(collection)

        self.assertEqual(len(self.fake.requests), requests_after_first)
        self.assertEqual(DetectionEmbedding.objects.count(), 4)

    def test_a_pipeline_without_an_embedding_algorithm_is_refused_before_any_request(self):
        collection = self._collection(captures=1)
        self.pipeline.algorithms.set([self.detector])

        with self.assertRaisesMessage(ValueError, "produces feature vectors"):
            self._run(collection)

        self.assertEqual(self.fake.requests, [])

    def test_a_failed_request_raises_instead_of_reporting_success(self):
        collection = self._collection(captures=1)
        self.fake.status_ok = False
        with mock.patch("ami.ml.models.pipeline.extract_error_message_from_response", return_value="boom"):
            with self.assertRaisesMessage(Exception, "boom"):
                self._run(collection)
        self.assertEqual(DetectionEmbedding.objects.count(), 0)

    def test_requests_are_made_per_batch_of_captures(self):
        collection = self._collection(captures=5)
        self._run(collection, batch_size=2)
        self.assertEqual([len(r["source_images"]) for r in self.fake.requests], [2, 2, 1])

    def test_queries_do_not_grow_with_the_number_of_captures(self):
        """A batch of 2 captures and a batch of 8 take the same number of queries."""
        self._run(self._collection(captures=1))  # first run creates the task's algorithm row and similar one-offs
        small, large = self._collection(captures=2), self._collection(captures=8)
        # Cold counts: a query the cache served for the first run would otherwise be missing from the second.
        with cachalot_disabled():
            with CaptureQueriesContext(connection) as small_queries:
                self._run(small, batch_size=100)
            with CaptureQueriesContext(connection) as large_queries:
                self._run(large, batch_size=100)
        self.assertEqual(len(large_queries), len(small_queries))


class TestEmbeddingOnlyPipelineGuard(FeatureVectorsFixture, TestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        cls._set_up_data()

    def setUp(self) -> None:
        self._set_up_stubs()

    def test_pipeline_knows_when_it_only_produces_vectors(self):
        self.assertTrue(self.pipeline.is_embedding_only())
        self.pipeline.algorithms.add(self.detector)
        self.assertFalse(self.pipeline.is_embedding_only())
        self.assertFalse(Pipeline.objects.create(name="Empty").is_embedding_only())

    def test_a_regular_ml_job_with_an_embedding_only_pipeline_fails_early_pointing_to_the_task(self):
        collection = self._collection(captures=1)
        job = Job.objects.create(
            name="ML job",
            project=self.project,
            job_type_key="ml",
            pipeline=self.pipeline,
            source_image_collection=collection,
        )
        with self.assertRaisesMessage(PipelineNotConfigured, "Add feature vectors"):
            job.run()
        self.assertEqual(self.fake.requests, [])


class TestAddFeatureVectorsAdmin(FeatureVectorsFixture, TestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        cls._set_up_data()
        cls.superuser = User.objects.create_superuser(email="afv-admin@example.com", password="x")
        ProjectPipelineConfig.objects.create(project=cls.project, pipeline=cls.pipeline, enabled=True)
        cls.other_pipeline = Pipeline.objects.create(name="Classifier only pipeline")
        cls.other_pipeline.algorithms.set([cls.detector])

    def setUp(self) -> None:
        self._set_up_stubs()
        self.client = Client()
        self.client.force_login(self.superuser)

    def _post(self, collections: list[SourceImageCollection], data: dict):
        return self.client.post(
            reverse("admin:main_sourceimagecollection_changelist"),
            {
                "action": "run_add_feature_vectors",
                django_admin.helpers.ACTION_CHECKBOX_NAME: [str(c.pk) for c in collections],
                **data,
            },
        )

    def test_the_form_lists_only_pipelines_with_an_embedding_algorithm(self):
        response = self._post([self._collection(captures=1)], {})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Run Add feature vectors")
        self.assertContains(response, "Feature pipeline")
        self.assertNotContains(response, "Classifier only pipeline")

    def test_it_enqueues_one_job_per_capture_set_with_the_config_on_the_job(self):
        first, second = self._collection(captures=1), self._collection(captures=1)

        response = self._post(
            [first, second], {"confirm": "1", "pipeline_id": self.pipeline.pk, "key": "embedding", "batch_size": 5}
        )

        self.assertEqual(response.status_code, 302)
        jobs = Job.objects.filter(job_type_key="post_processing", params__task="add_feature_vectors")
        self.assertEqual(jobs.count(), 2)
        self.assertCountEqual(
            [job.params["config"]["source_image_collection_id"] for job in jobs], [first.pk, second.pk]
        )
        for job in jobs:
            self.assertEqual(job.params["config"]["pipeline_id"], self.pipeline.pk)
            self.assertEqual(job.params["config"]["batch_size"], 5)

    def test_an_out_of_range_batch_size_is_shown_on_the_form_and_creates_no_job(self):
        response = self._post(
            [self._collection(captures=1)],
            {"confirm": "1", "pipeline_id": self.pipeline.pk, "key": "embedding", "batch_size": 0},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Job.objects.filter(params__task="add_feature_vectors").count(), 0)
