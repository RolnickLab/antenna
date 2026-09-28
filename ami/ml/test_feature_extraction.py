"""Feature-only pipelines: vectors for detections Antenna already has, and nothing else.

A feature extractor (e.g. a BioCLIP backbone) is run on existing detections so tracking
can compare every detection by appearance. These tests pin that such a run writes only
``DetectionEmbedding`` rows, skips detections that already have a vector, keeps one vector
length per algorithm, and that readers never compare vectors of different lengths.
"""

import datetime
from unittest import mock

import pydantic
from django.test import TestCase
from rest_framework.test import APITestCase

from ami.jobs.models import Job, JobDispatchMode, MLJob
from ami.main.models import (
    Classification,
    Deployment,
    Detection,
    DetectionEmbedding,
    Event,
    Occurrence,
    Project,
    SourceImage,
    SourceImageCollection,
    group_images_into_events,
)
from ami.main.models_future.embeddings import (
    default_feature_algorithm_id,
    feature_extractors_with_vectors,
    vectors_for_detections,
)
from ami.ml.models import Algorithm, Pipeline, ProcessingService
from ami.ml.models.pipeline import (
    COLLECT_PROGRESS_MAX_FRACTION,
    COLLECT_PROGRESS_SAVE_INTERVAL_SECONDS,
    EmbeddingDimensionMismatch,
    collect_detections_for_features,
    collect_images,
    filter_processed_images,
    process_images,
    save_results,
)
from ami.ml.models.project_pipeline_config import ProjectPipelineConfig
from ami.ml.orchestration.jobs import queue_images_to_nats
from ami.ml.post_processing.tracking_task import TrackingConfig, cosine_similarity, resolve_feature_algorithm
from ami.ml.schemas import EmbeddingResponse, PipelineResultsResponse, SourceImageRequest
from ami.users.models import User

BIOCLIP_DIMENSIONS = 1024


def _box(offset: float) -> list[float]:
    return [offset, offset, offset + 10.5, offset + 12.25]


class FeatureOnlyFixture:
    """A project with detected, classified and determined captures, plus a feature-only pipeline."""

    def _set_up_project(self, images: int = 3, boxes_per_image: int = 2) -> None:
        self.project = Project.objects.create(name="Feature extraction")
        self.deployment = Deployment.objects.create(name="Station", project=self.project)
        self.detector = Algorithm.objects.create(name="Detector", key="test-detector", task_type="localization")
        self.classifier = Algorithm.objects.create(
            name="Classifier", key="test-classifier", task_type="classification"
        )
        self.extractor = Algorithm.objects.create(name="Backbone", key="test-backbone", task_type="embedding")
        self.pipeline = Pipeline.objects.create(name="Features only", slug="features-only")
        self.pipeline.algorithms.set([self.extractor])

        start = datetime.datetime(2024, 6, 1, 22, 0)
        self.images = [
            SourceImage.objects.create(
                deployment=self.deployment,
                project=self.project,
                path=f"feat/{i}.jpg",
                timestamp=start + datetime.timedelta(minutes=i),
            )
            for i in range(images)
        ]
        group_images_into_events(self.deployment)
        self.images = list(SourceImage.objects.filter(pk__in=[i.pk for i in self.images]).order_by("timestamp"))
        self.collection = SourceImageCollection.objects.create(project=self.project, name="Scope")
        self.collection.images.set(self.images)
        for image in self.images:
            for n in range(boxes_per_image):
                occurrence = Occurrence.objects.create(
                    project=self.project, deployment=self.deployment, event=image.event
                )
                detection = Detection.objects.create(
                    source_image=image,
                    bbox=_box(20.0 * n),
                    detection_algorithm=self.detector,
                    occurrence=occurrence,
                    timestamp=image.timestamp,
                )
                Classification.objects.create(
                    detection=detection, algorithm=self.classifier, score=0.9, timestamp=image.timestamp
                )
        # A null marker must never be sent or embedded.
        Detection.objects.create(source_image=self.images[0], bbox=None, detection_algorithm=self.detector)

    def _embed(self, detections, algorithm: Algorithm, length: int = BIOCLIP_DIMENSIONS) -> None:
        DetectionEmbedding.objects.bulk_create(
            [DetectionEmbedding(detection=d, algorithm=algorithm, vector=[0.5] * length) for d in detections]
        )

    def _response(self, boxes: list[tuple[SourceImage, list[float]]], length: int = BIOCLIP_DIMENSIONS, **extra):
        """What a feature-only pipeline sends back: the boxes it was given, each with a vector."""
        return PipelineResultsResponse(
            pipeline=self.pipeline.slug,
            total_time=0.1,
            source_images=[{"id": str(image.pk), "url": "x"} for image in {image for image, _ in boxes}],
            detections=[
                {
                    "source_image_id": str(image.pk),
                    "bbox": dict(zip(["x1", "y1", "x2", "y2"], box)),
                    "algorithm": {"name": self.detector.name, "key": self.detector.key},
                    "timestamp": datetime.datetime.now().isoformat(),
                    "embeddings": [
                        {
                            "algorithm": {"name": self.extractor.name, "key": self.extractor.key},
                            "vector": [0.1] * length,
                        }
                    ],
                    **extra,
                }
                for image, box in boxes
            ],
        )

    def _counts(self) -> tuple:
        return (
            Detection.objects.count(),
            Classification.objects.count(),
            Occurrence.objects.count(),
            sorted(Occurrence.objects.values_list("pk", "determination_id", "determination_score")),
        )


class TestEmbeddingSchema(TestCase):
    def test_a_vector_of_any_length_is_accepted_under_either_key(self):
        algorithm = {"name": "Backbone", "key": "test-backbone"}
        for key in ("features", "vector"):
            parsed = EmbeddingResponse.parse_obj({"algorithm": algorithm, key: [0.1] * BIOCLIP_DIMENSIONS})
            self.assertEqual(len(parsed.features), BIOCLIP_DIMENSIONS)
        with self.assertRaises(pydantic.ValidationError):
            EmbeddingResponse.parse_obj({"algorithm": algorithm, "vector": []})


class TestFeatureOnlySave(FeatureOnlyFixture, TestCase):
    def setUp(self) -> None:
        self._set_up_project()

    def test_an_embeddings_only_response_writes_only_vectors(self):
        """No detection, classification or occurrence is created and no determination moves, even
        for a box Antenna does not have or classifications the service sent anyway."""
        before = self._counts()
        known = [(image, _box(0.0)) for image in self.images]
        unknown = [(self.images[0], _box(500.0))]
        stray = {
            "classifications": [
                {
                    "classification": "Moth",
                    "scores": [0.99],
                    "algorithm": {"name": self.extractor.name, "key": self.extractor.key},
                    "timestamp": datetime.datetime.now().isoformat(),
                }
            ]
        }
        save_results(self._response(known + unknown, **stray))

        self.assertEqual(self._counts(), before)
        stored = DetectionEmbedding.objects.filter(algorithm=self.extractor)
        self.assertEqual(
            sorted(stored.values_list("detection__source_image_id", flat=True)), sorted(i.pk for i in self.images)
        )
        self.extractor.refresh_from_db()
        self.assertEqual(self.extractor.embedding_dimensions, BIOCLIP_DIMENSIONS)

    def test_a_vector_of_another_length_is_refused_and_nothing_is_stored(self):
        save_results(self._response([(self.images[0], _box(0.0))]))
        with self.assertRaises(EmbeddingDimensionMismatch):
            save_results(self._response([(self.images[1], _box(0.0))], length=512))
        self.assertEqual(DetectionEmbedding.objects.count(), 1)


class TestExtractFeaturesScope(FeatureOnlyFixture, TestCase):
    """What an extract-features run sends: only real detections still missing a vector."""

    def setUp(self) -> None:
        self._set_up_project()
        # The first image is done; one box on the second is done.
        self._embed(self.images[0].detections.valid(), self.extractor)
        self._embed(self.images[1].detections.valid().filter(bbox=_box(0.0)), self.extractor)

    def test_images_whose_detections_all_have_vectors_are_skipped(self):
        collected = collect_images(collection=self.collection, pipeline=self.pipeline)
        self.assertEqual([image.pk for image in collected], [self.images[1].pk, self.images[2].pk])

    def test_a_vector_from_another_algorithm_does_not_count(self):
        other = Algorithm.objects.create(name="Other", key="other-backbone", task_type="embedding")
        self._embed(self.images[2].detections.valid(), other)
        collected = collect_images(collection=self.collection, pipeline=self.pipeline)
        self.assertIn(self.images[2].pk, [image.pk for image in collected])

    def test_the_request_carries_only_the_missing_boxes_in_one_query(self):
        requests = [SourceImageRequest(id=str(image.pk), url="x") for image in self.images]
        with self.assertNumQueries(1):
            detections = collect_detections_for_features(requests, [self.extractor.pk])
        self.assertEqual(
            sorted((int(d.source_image.id), d.bbox.x1) for d in detections),
            [(self.images[1].pk, 20.0), (self.images[2].pk, 0.0), (self.images[2].pk, 20.0)],
        )
        self.assertEqual({d.algorithm.key for d in detections}, {self.detector.key})

    def test_process_images_sends_existing_boxes_and_skips_done_images(self):
        sent = {}

        def post(url, json):
            sent.update(json)
            return mock.Mock(
                ok=True,
                json=lambda: {"pipeline": json["pipeline"], "total_time": 0, "source_images": [], "detections": []},
            )

        with mock.patch.object(SourceImage, "public_url", return_value="http://example.org/i.jpg"), mock.patch(
            "ami.ml.models.pipeline.create_session", return_value=mock.Mock(post=post)
        ):
            process_images(self.pipeline, "http://example.org/process", self.images, project_id=self.project.pk)

        self.assertEqual(sorted(int(i["id"]) for i in sent["source_images"]), [self.images[1].pk, self.images[2].pk])
        self.assertEqual(len(sent["detections"]), 3)


class TestExtractFeaturesQueue(FeatureOnlyFixture, TestCase):
    """The async path: each queued task carries its missing boxes, and no task is queued empty."""

    def setUp(self) -> None:
        self._set_up_project()
        self._embed(self.images[0].detections.valid(), self.extractor)
        self._embed(self.images[1].detections.valid().filter(bbox=_box(0.0)), self.extractor)
        # A box whose detector is unknown cannot be sent, so it must not make its image count as pending.
        Detection.objects.create(source_image=self.images[0], bbox=_box(40.0), detection_algorithm=None)
        self.job = Job.objects.create(
            name="Extract features",
            job_type_key=MLJob.key,
            project=self.project,
            pipeline=self.pipeline,
            source_image_collection=self.collection,
            dispatch_mode=JobDispatchMode.ASYNC_API,
        )

    @mock.patch("ami.ml.orchestration.jobs.AsyncJobStateManager")
    @mock.patch("ami.ml.orchestration.jobs.TaskQueueManager")
    def test_each_task_carries_its_missing_boxes_and_images_with_none_are_not_queued(self, manager_cls, state_cls):
        manager = manager_cls.return_value
        manager.__aenter__ = mock.AsyncMock(return_value=manager)
        manager.__aexit__ = mock.AsyncMock(return_value=False)
        manager.ensure_job_resources = mock.AsyncMock()
        manager.publish_task = mock.AsyncMock(return_value=True)

        with mock.patch.object(SourceImage, "url", return_value="http://example.org/i.jpg"):
            self.assertTrue(queue_images_to_nats(self.job, self.images))

        published = {
            int(call.kwargs["data"].image_id): sorted(d.bbox.x1 for d in call.kwargs["data"].detections)
            for call in manager.publish_task.await_args_list
        }
        self.assertEqual(published, {self.images[1].pk: [20.0], self.images[2].pk: [0.0, 20.0]})
        state_cls.return_value.initialize_job.assert_called_once_with([str(self.images[1].pk), str(self.images[2].pk)])

    def test_images_whose_only_pending_box_has_no_detector_are_skipped(self):
        collected = collect_images(collection=self.collection, pipeline=self.pipeline)
        self.assertEqual([image.pk for image in collected], [self.images[1].pk, self.images[2].pk])

    def test_the_collect_stage_reports_progress_while_filtering(self):
        clock = {"t": 0.0}

        def fake_monotonic() -> float:
            clock["t"] += COLLECT_PROGRESS_SAVE_INTERVAL_SECONDS
            return clock["t"]

        with mock.patch("ami.ml.models.pipeline.time.monotonic", side_effect=fake_monotonic), mock.patch.object(
            Job, "save", autospec=True
        ) as save:
            list(filter_processed_images(self.images, self.pipeline, batch_size=1, job=self.job, total=3))

        self.assertEqual(save.call_count, 3)
        self.assertEqual(save.call_args.kwargs["update_fields"], ["progress", "updated_at"])
        self.assertEqual(self.job.progress.get_stage("collect").progress, COLLECT_PROGRESS_MAX_FRACTION)


class TestReadersNeverMixLengths(FeatureOnlyFixture, TestCase):
    def setUp(self) -> None:
        self._set_up_project(images=2, boxes_per_image=2)

    def test_one_algorithm_with_two_lengths_returns_one_length(self):
        detections = list(Detection.objects.valid().order_by("pk"))
        self._embed(detections[:3], self.extractor, length=BIOCLIP_DIMENSIONS)
        Classification.objects.filter(detection=detections[3]).update(
            algorithm=self.extractor, features_2048=[0.5] * 2048
        )
        vectors = vectors_for_detections([d.pk for d in detections], self.extractor.pk)
        self.assertEqual({len(v) for v in vectors.values()}, {BIOCLIP_DIMENSIONS})
        self.assertEqual(len(vectors), 3)

    def test_cosine_similarity_refuses_vectors_of_different_lengths(self):
        with self.assertRaises(ValueError):
            cosine_similarity([1.0] * 1024, [1.0] * 2048)


class TestDefaultFeatureExtractor(FeatureOnlyFixture, TestCase):
    """With vectors from several extractors and none chosen, tracking compares the one covering most boxes."""

    def setUp(self) -> None:
        self._set_up_project(images=2, boxes_per_image=2)
        self.event = Event.objects.get(pk=self.images[0].event_id)
        self.other = Algorithm.objects.create(name="Other backbone", key="other-backbone", task_type="embedding")
        self.detections = list(Detection.objects.valid().filter(source_image__event=self.event).order_by("pk"))
        self._embed(self.detections, self.other, length=2048)
        self._embed(self.detections[:1], self.extractor)  # stored last, on one box only

    def test_the_extractor_covering_most_detections_wins_over_a_more_recent_one(self):
        algorithm, should_track, note = resolve_feature_algorithm(
            self.event, TrackingConfig(event_ids=[self.event.pk], require_features=True)
        )
        self.assertEqual((algorithm, should_track), (self.other, True))
        self.assertIn("2 feature extractors", note)

    def test_an_extractor_the_project_runs_wins_only_once_it_covers_nearly_as_many(self):
        service = ProcessingService.objects.create(name="Service", endpoint_url=None)
        service.projects.add(self.project)
        service.pipelines.add(self.pipeline)
        ProjectPipelineConfig.objects.create(project=self.project, pipeline=self.pipeline, enabled=True)
        algorithm_ids = [self.other.pk, self.extractor.pk]

        def default() -> int | None:
            return default_feature_algorithm_id(self.project.pk, algorithm_ids, source_image__event=self.event)

        self.assertEqual(default(), self.other.pk)  # 1 of 4 boxes: a run still in progress
        self._embed(self.detections[1:], self.extractor)
        self.assertEqual(default(), self.extractor.pk)

    def test_a_chosen_extractor_is_kept(self):
        config = TrackingConfig(
            event_ids=[self.event.pk], require_features=True, feature_extraction_algorithm_id=self.extractor.pk
        )
        self.assertEqual(resolve_feature_algorithm(self.event, config)[0], self.extractor)

    def test_listing_a_sessions_extractors_takes_a_fixed_number_of_queries(self):
        with self.assertNumQueries(5):
            rows = feature_extractors_with_vectors(self.project.pk, source_image__event=self.event)
        self.assertEqual(
            [(row["algorithm"].pk, row["embeddings_count"], row["is_default"]) for row in rows],
            [(self.other.pk, 4, True), (self.extractor.pk, 1, False)],  # newest algorithm first
        )


class TestSessionFeatureExtractorsEndpoint(FeatureOnlyFixture, APITestCase):
    """Who can list a session's feature extractors: whoever can open the session."""

    def setUp(self) -> None:
        self._set_up_project(images=2, boxes_per_image=2)
        self._embed(Detection.objects.valid(), self.extractor)
        self.owner = User.objects.create_user(email="feat-owner@insectai.org", password="x")
        self.member = User.objects.create_user(email="feat-member@insectai.org", password="x")
        self.outsider = User.objects.create_user(email="feat-outsider@insectai.org", password="x")
        self.superuser = User.objects.create_superuser(email="feat-admin@insectai.org", password="x")
        self.project.owner = self.owner
        self.project.draft = True
        self.project.save()
        self.project.members.add(self.member)
        self.url = f"/api/v2/events/{self.images[0].event_id}/feature-extractors/?project_id={self.project.pk}"

    def _status(self, user) -> int:
        self.client.force_authenticate(user)
        return self.client.get(self.url).status_code

    def test_permission_matrix_on_a_draft_project(self):
        self.assertEqual(self._status(self.member), 200)
        self.assertEqual(self._status(self.superuser), 200)
        self.assertIn(self._status(self.outsider), (403, 404))
        self.assertIn(self._status(None), (401, 403, 404))

    def test_the_response_names_each_extractor_and_the_default(self):
        self.client.force_authenticate(self.member)
        body = self.client.get(self.url).json()
        self.assertEqual(
            body,
            [
                {
                    "id": self.extractor.pk,
                    "name": self.extractor.name,
                    "key": self.extractor.key,
                    "task_type": "embedding",
                    "embedding_dimensions": None,
                    "embeddings_count": 4,
                    "classification_vectors_count": 0,
                    "is_default": True,
                }
            ],
        )
