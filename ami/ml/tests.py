import concurrent.futures
import datetime
import io
import json
import pathlib
import unittest
import unittest.mock
import uuid

import numpy as np
from django.core.files.storage import default_storage
from django.test import TestCase
from rest_framework.test import APIRequestFactory, APITestCase

from ami.base.serializers import reverse_with_params
from ami.main.models import (
    Classification,
    Deployment,
    Detection,
    Event,
    Identification,
    Occurrence,
    OccurrenceSet,
    Project,
    SourceImage,
    SourceImageCollection,
    TaxaList,
    Taxon,
    TaxonRank,
    group_images_into_events,
)
from ami.ml import training_data
from ami.ml.models import (
    Algorithm,
    AlgorithmCategoryMap,
    AlgorithmEvaluation,
    DetectionEmbedding,
    Pipeline,
    ProcessingService,
    TaxonEvaluation,
)
from ami.ml.models.embedding import EMBEDDING_DIMENSIONS
from ami.ml.models.pipeline import collect_images, get_or_create_algorithm_and_category_map, save_results
from ami.ml.post_processing.small_size_filter import SmallSizeFilterTask
from ami.ml.schemas import (
    AlgorithmConfigResponse,
    AlgorithmReference,
    BoundingBox,
    ClassificationResponse,
    DetectionResponse,
    PipelineResultsResponse,
    SourceImageResponse,
)
from ami.tests.fixtures.main import (
    create_captures_from_files,
    create_processing_service,
    create_taxa,
    setup_test_project,
)
from ami.tests.fixtures.ml import ALGORITHM_CHOICES
from ami.users.models import User


class TestProcessingServiceAPI(APITestCase):
    """
    Test the Processing Services API endpoints.
    """

    def setUp(self):
        self.project = Project.objects.create(name="Processing Service Test Project")

        self.user = User.objects.create_user(  # type: ignore
            email="testuser@insectai.org",
            is_staff=True,
        )
        self.factory = APIRequestFactory()

    def _create_processing_service(self, name: str, endpoint_url: str):
        processing_services_create_url = reverse_with_params(
            "api:processingservice-list", params={"project_id": self.project.pk}
        )
        self.client.force_authenticate(user=self.user)
        processing_service_data = {
            "name": name,
            "endpoint_url": endpoint_url,
        }
        resp = self.client.post(processing_services_create_url, processing_service_data)
        self.client.force_authenticate(user=None)
        self.assertEqual(resp.status_code, 201)
        return resp.json()["instance"]

    def _delete_processing_service(self, processing_service_id: int):
        processing_services_delete_url = reverse_with_params(
            "api:processing-service-detail", kwargs={"pk": processing_service_id}
        )
        self.client.force_authenticate(user=self.user)
        resp = self.client.delete(processing_services_delete_url)
        self.client.force_authenticate(user=None)
        self.assertEqual(resp.status_code, 204)
        return resp

    def _register_pipelines(self, processing_service_id):
        processing_services_register_pipelines_url = reverse_with_params(
            "api:processingservice-register-pipelines", args=[processing_service_id]
        )
        self.client.force_authenticate(user=self.user)
        resp = self.client.post(processing_services_register_pipelines_url)
        data = resp.json()
        self.assertEqual(data["success"], True)
        return data

    def test_create_processing_service(self):
        self._create_processing_service(
            name="Processing Service Test",
            endpoint_url="http://processing_service:2000",
        )

    def test_project_was_added(self):
        response = self._create_processing_service(
            name="Processing Service Test",
            endpoint_url="http://processing_service:2000",
        )
        processing_service_id = response["id"]
        processing_service = ProcessingService.objects.get(pk=processing_service_id)
        self.assertIn(self.project, processing_service.projects.all())

    def test_processing_service_pipeline_registration(self):
        # register a processing service
        response = self._create_processing_service(
            name="Processing Service Test",
            endpoint_url="http://processing_service:2000",
        )
        processing_service_id = response["id"]

        # sync the processing service to create/add the associate pipelines
        response = self._register_pipelines(processing_service_id)
        processing_service = ProcessingService.objects.get(pk=processing_service_id)
        pipelines_queryset = processing_service.pipelines.all()

        self.assertEqual(pipelines_queryset.count(), len(response["pipelines"]))

    def test_create_processing_service_without_endpoint_url(self):
        """Test creating a ProcessingService without endpoint_url (pull mode)"""
        processing_services_create_url = reverse_with_params(
            "api:processingservice-list", params={"project_id": self.project.pk}
        )
        self.client.force_authenticate(user=self.user)
        processing_service_data = {
            "name": "Pull Mode Service",
            "description": "Service without endpoint",
        }
        resp = self.client.post(processing_services_create_url, processing_service_data)
        self.client.force_authenticate(user=None)

        self.assertEqual(resp.status_code, 201)
        data = resp.json()

        # Check that endpoint_url is null
        self.assertIsNone(data["instance"]["endpoint_url"])

        # Check that status indicates service is not yet live (no heartbeat received)
        self.assertFalse(data["status"]["request_successful"])
        self.assertFalse(data["status"]["server_live"])
        self.assertIsNone(data["status"]["endpoint_url"])

    def test_get_status_with_null_endpoint_url(self):
        """Test get_status method when endpoint_url is None"""
        service = ProcessingService.objects.create(name="Pull Mode Service", endpoint_url=None)
        service.projects.add(self.project)

        status = service.get_status()

        self.assertFalse(status.request_successful)
        self.assertFalse(status.server_live)  # No heartbeat received yet = not live
        self.assertIsNone(status.endpoint_url)
        self.assertEqual(status.pipelines_online, [])

    def test_get_pipeline_configs_with_null_endpoint_url(self):
        """Test get_pipeline_configs method when endpoint_url is None"""
        service = ProcessingService.objects.create(name="Pull Mode Service", endpoint_url=None)

        configs = service.get_pipeline_configs()

        self.assertEqual(configs, [])


class TestProcessingServiceLastSeen(TestCase):
    """Test the last_seen, last_seen_live, and last_seen_latency fields."""

    def setUp(self):
        self.project = Project.objects.create(name="Last Seen Test Project")

    def test_mark_seen_sets_fields(self):
        """Test that mark_seen() sets last_seen and last_seen_live."""
        service = ProcessingService.objects.create(name="Async Worker", endpoint_url=None)
        service.projects.add(self.project)

        self.assertIsNone(service.last_seen)
        self.assertIsNone(service.last_seen_live)

        service.mark_seen(live=True)
        service.refresh_from_db()

        self.assertIsNotNone(service.last_seen)
        self.assertTrue(service.last_seen_live)

    def test_mark_seen_offline(self):
        """Test that mark_seen(live=False) sets last_seen_live to False."""
        service = ProcessingService.objects.create(name="Async Worker Offline", endpoint_url=None)

        service.mark_seen(live=False)
        service.refresh_from_db()

        self.assertIsNotNone(service.last_seen)
        self.assertFalse(service.last_seen_live)

    def test_get_status_updates_last_seen_for_sync_service(self):
        """Test that get_status() updates last_seen fields for sync services (even if endpoint is unreachable)."""
        service = ProcessingService.objects.create(name="Sync Service", endpoint_url="http://nonexistent-host:9999")
        service.projects.add(self.project)

        # get_status should update the fields even for unreachable endpoints
        service.get_status(timeout=1)
        service.refresh_from_db()

        self.assertIsNotNone(service.last_seen)
        self.assertFalse(service.last_seen_live)  # unreachable = not live
        self.assertIsNotNone(service.last_seen_latency)

    def test_model_has_last_seen_fields(self):
        """Test that ProcessingService model has last_seen fields and not last_checked."""
        service = ProcessingService.objects.create(name="Field Test Service", endpoint_url=None)
        service.mark_seen(live=True)
        service.refresh_from_db()

        # Verify new fields exist
        self.assertTrue(hasattr(service, "last_seen"))
        self.assertTrue(hasattr(service, "last_seen_live"))
        self.assertTrue(hasattr(service, "last_seen_latency"))

        # Verify old fields don't exist
        self.assertFalse(hasattr(service, "last_checked"))
        self.assertFalse(hasattr(service, "last_checked_live"))
        self.assertFalse(hasattr(service, "last_checked_latency"))


class TestProjectPipelineRegistrationUpdatesLastSeen(APITestCase):
    """Test that async pipeline registration updates last_seen on the processing service."""

    def setUp(self):
        from ami.users.roles import ProjectManager, create_roles_for_project

        self.user = User.objects.create_user(email="lastseen@example.com")  # type: ignore
        self.project = Project.objects.create(name="Last Seen Project", owner=self.user, create_defaults=False)
        create_roles_for_project(self.project)
        ProjectManager.assign_user(self.user, self.project)

    def test_pipeline_registration_marks_service_as_seen(self):
        """Test that POSTing to the pipeline registration endpoint marks the service as last_seen_live."""
        url = f"/api/v2/projects/{self.project.pk}/pipelines/"
        payload = {
            "processing_service_name": "AsyncTestWorker",
            "pipelines": [],
        }

        self.client.force_authenticate(user=self.user)
        response = self.client.post(url, payload, format="json")
        self.assertEqual(response.status_code, 201)

        service = ProcessingService.objects.get(name="AsyncTestWorker")
        self.assertIsNotNone(service.last_seen)
        self.assertTrue(service.last_seen_live)

    def test_repeated_registration_updates_last_seen(self):
        """Test that re-registering updates the last_seen timestamp."""
        url = f"/api/v2/projects/{self.project.pk}/pipelines/"
        payload = {
            "processing_service_name": "AsyncTestWorkerRepeat",
            "pipelines": [],
        }

        self.client.force_authenticate(user=self.user)

        # First registration
        self.client.post(url, payload, format="json")
        service = ProcessingService.objects.get(name="AsyncTestWorkerRepeat")
        first_seen = service.last_seen

        # Second registration
        self.client.post(url, payload, format="json")
        service.refresh_from_db()
        second_seen = service.last_seen

        self.assertIsNotNone(first_seen)
        self.assertIsNotNone(second_seen)
        self.assertGreaterEqual(second_seen, first_seen)


class TestPipelineWithProcessingService(TestCase):
    def test_run_pipeline_with_errors_from_processing_service(self):
        """
        Run a real pipeline and verify that if an error occurs for one image, the error is logged to JobLog.
        """
        from ami.jobs.models import Job, JobLog

        # Setup test project, images, and job
        project, deployment = setup_test_project()
        captures = create_captures_from_files(deployment, skip_existing=False)
        test_images = [image for image, frame in captures]
        processing_service_instance = create_processing_service(project)
        pipeline = processing_service_instance.pipelines.all().get(slug="constant")
        job = Job.objects.create(project=project, name="Test Job Real Pipeline Error Handling", pipeline=pipeline)

        # Simulate an error by passing an invalid image (e.g., missing file or corrupt)
        # Here, we manually set the path of one image to a non-existent file
        error_image = test_images[0]
        error_image.path = "/tmp/nonexistent_image.jpg"
        error_image.save()
        images = [error_image] + test_images[1:2]  # Only two images for brevity

        # Run the pipeline and catch any error
        try:
            pipeline.process_images(images, job_id=job.pk, project_id=project.pk)
        except Exception:
            pass  # Expected if the backend raises

        job.refresh_from_db()
        stderr_logs = list(
            JobLog.objects.filter(job=job, level__in=["ERROR", "CRITICAL"]).values_list("message", flat=True)
        )
        # Check that an error message mentioning the failed image is present
        assert any(
            "Failed to process" in log for log in stderr_logs
        ), f"Expected error message in job logs, got: {stderr_logs}"

    def setUp(self):
        self.project, self.deployment = setup_test_project()
        self.captures = create_captures_from_files(self.deployment, skip_existing=False)
        self.test_images = [image for image, frame in self.captures]
        self.processing_service_instance = create_processing_service(self.project)
        self.processing_service = self.processing_service_instance
        assert self.processing_service_instance.pipelines.exists()
        self.pipeline = self.processing_service_instance.pipelines.all().get(slug="constant")

    def test_run_pipeline(self):
        # Send images to Processing Service to process and return detections
        assert self.pipeline
        pipeline_response = self.pipeline.process_images(self.test_images, job_id=None, project_id=self.project.pk)
        assert pipeline_response.detections

    def test_created_category_maps(self):
        # Send images to ML backend to process and return detections
        assert self.pipeline
        pipeline_response = self.pipeline.process_images(self.test_images, project_id=self.project.pk)
        save_results(pipeline_response, return_created=True)

        source_images = SourceImage.objects.filter(pk__in=[image.id for image in pipeline_response.source_images])
        detections = Detection.objects.filter(source_image__in=source_images).select_related(
            "detection_algorithm",
            "detection_algorithm__category_map",
        )
        assert detections.count() > 0
        for detection in detections:
            # No detection algorithm should have category map at this time (but this may change!)
            assert detection.detection_algorithm
            assert detection.detection_algorithm.category_map is None

            # Ensure that all classification algorithms have a category map
            classification_taxa = set()
            for classification in detection.classifications.all().select_related(
                "algorithm",
                "algorithm__category_map",
            ):
                assert classification.algorithm is not None
                assert classification.category_map is not None
                assert classification.algorithm.category_map == classification.category_map

                _, top_score = list(classification.predictions(sort=True))[0]
                assert top_score == classification.score

                top_taxon, top_taxon_score = list(classification.predictions_with_taxa(sort=True))[0]
                assert top_taxon == classification.taxon
                assert top_taxon_score == classification.score

                classification_taxa.add(top_taxon)

            # Check the occurrence determination taxon
            assert detection.occurrence
            assert detection.occurrence.determination in classification_taxa

    def test_missing_category_map(self):
        # Test that an exception is raised if a classification algorithm is missing a category map
        from ami.ml.exceptions import PipelineNotConfigured

        # Get the response from the /info endpoint
        pipeline_configs = self.processing_service.get_pipeline_configs()

        # Assert that there is a least one classification algorithm with a category map
        self.assertTrue(
            any(
                algo.task_type in Algorithm.classification_task_types and algo.category_map is not None
                for pipeline in pipeline_configs
                for algo in pipeline.algorithms
            ),
            "Expected pipeline to have at least one classification algorithm with a category map",
        )

        # Remove the category map from one of the classification algorithms
        for pipeline_config in pipeline_configs:
            for algorithm in pipeline_config.algorithms:
                if algorithm.task_type in Algorithm.classification_task_types and algorithm.category_map is not None:
                    algorithm.category_map = None
                    # Change the key to ensure it's treated as a new algorithm
                    algorithm.key = "missing-category-map-classifier"
                    algorithm.name = "Classifier with Missing Category Map"
                    break

        with self.assertRaises(
            PipelineNotConfigured,
            msg="Expected an exception to be raised if a classification algorithm is missing a category map",
        ):
            self.processing_service.create_pipelines(pipeline_configs=pipeline_configs)

    def test_alignment_of_predictions_and_category_map(self):
        # Ensure that the scores and labels are aligned
        pipeline = self.processing_service_instance.pipelines.all().get(slug="random-detection-random-species")
        pipeline_response = pipeline.process_images(self.test_images, project_id=self.project.pk)
        results = save_results(pipeline_response, return_created=True)
        assert results is not None, "Expected results to be returned in a PipelineSaveResults object"
        assert results.classifications, "Expected classifications to be returned in the results"
        for classification in results.classifications:
            assert classification.scores
            taxa_with_scores = list(classification.predictions_with_taxa(sort=True))
            assert taxa_with_scores
            assert classification.score == taxa_with_scores[0][1]
            assert classification.taxon == taxa_with_scores[0][0]

    def test_top_n_alignment(self):
        # Ensure that the top_n parameter works
        pipeline = self.processing_service_instance.pipelines.all().get(slug="random-detection-random-species")
        pipeline_response = pipeline.process_images(self.test_images, project_id=self.project.pk)
        results = save_results(pipeline_response, return_created=True)
        assert results is not None, "Expecected results to be returned in a PipelineSaveResults object"
        assert results.classifications, "Expected classifications to be returned in the results"
        for classification in results.classifications:
            top_n = classification.top_n(n=3)
            assert classification.score == top_n[0]["score"]
            assert classification.taxon == top_n[0]["taxon"]

    def test_pipeline_reprocessing(self):
        """
        Test that reprocessing the same images with differet pipelines does not create duplicate
        detections. The 2 pipelines used are a random detection + random species classifier, and a
        constant species classifier.
        """
        if not self.project.feature_flags.reprocess_existing_detections:
            self.project.feature_flags.reprocess_existing_detections = True
            self.project.save()

        # Process the images once
        pipeline_one = self.processing_service_instance.pipelines.all().get(slug="random-detection-random-species")
        num_classifiers_pipeline_one = pipeline_one.algorithms.filter(task_type="classification").count()
        pipeline_response = pipeline_one.process_images(self.test_images, project_id=self.project.pk)
        results = save_results(pipeline_response, return_created=True)
        assert results is not None, "Expected results to be returned in a PipelineSaveResults object"
        assert results.detections, "Expected detections to be returned in the results"
        num_initial_detections = len(results.detections)

        # This particular pipeline produces 2 classifications per detection
        for det in results.detections:
            num_classifications = det.classifications.count()
            self.assertEqual(
                num_classifications,
                num_classifiers_pipeline_one,
                f"Expected {num_classifiers_pipeline_one} classifications per detection "
                "(random species and random binary classifier).",
            )

        source_images = SourceImage.objects.filter(pk__in=[image.id for image in pipeline_response.source_images])
        detections = Detection.objects.filter(source_image__in=source_images).select_related(
            "detection_algorithm",
            "detection_algorithm__category_map",
        )
        initial_detection_ids = sorted([det.pk for det in detections])
        assert detections.count() > 0

        # Reprocess the same images using a different pipeline
        pipeline_two = self.processing_service_instance.pipelines.all().get(slug="constant")
        num_classifiers_pipeline_two = pipeline_two.algorithms.filter(task_type="classification").count()
        pipeline_response = pipeline_two.process_images(self.test_images, project_id=self.project.pk)
        reprocessed_results = save_results(pipeline_response, return_created=True)
        assert reprocessed_results is not None, "Expected results to be returned in a PipelineSaveResults object"
        assert reprocessed_results.detections, "Expected detections to be returned in the results"
        num_reprocessed_detections = len(reprocessed_results.detections)
        self.assertEqual(
            num_reprocessed_detections,
            num_initial_detections,
            "Expected the same number of detections after reprocessing with a different pipeline.",
        )

        source_images = SourceImage.objects.filter(pk__in=[image.id for image in pipeline_response.source_images])
        detections = Detection.objects.filter(source_image__in=source_images).select_related(
            "detection_algorithm",
            "detection_algorithm__category_map",
        )

        # Check detections were re-processed, and not re-created
        reprocessed_detection_ids = sorted([det.pk for det in detections])
        assert initial_detection_ids == reprocessed_detection_ids, (
            "Expected the same detections to be returned after reprocessing with a different pipeline, "
            f"but found {initial_detection_ids} != {reprocessed_detection_ids}"
        )

        # The constant pipeline produces 1 classification per detection (added to the existing classifications)
        for detection in detections:
            self.assertEqual(
                detection.classifications.count(),
                num_classifiers_pipeline_one + num_classifiers_pipeline_two,
                f"Expected {num_classifiers_pipeline_one + num_classifiers_pipeline_two} "
                "classifications per detection (2 random classifiers + constant classifier).",
            )


class TestPipeline(TestCase):
    def setUp(self):
        self.project = Project.objects.create(name="Test Project")
        # Create test images and collection
        self.test_images = [
            SourceImage.objects.create(path="test1-20240101000000.jpg"),
            SourceImage.objects.create(path="test2-20240101001000.jpg"),
        ]
        self.image_collection = SourceImageCollection.objects.create(
            name="Test Collection",
            project=self.project,
        )
        self.image_collection.images.set(self.test_images)

        # Create test pipeline and algorithms
        self.pipeline = Pipeline.objects.create(
            name="Test Pipeline (Random)",
        )
        self.pipeline_two = Pipeline.objects.create(
            name="Test Pipeline (Constant)",
        )

        self.algorithms = {
            key: get_or_create_algorithm_and_category_map(val) for key, val in ALGORITHM_CHOICES.items()
        }
        self.pipeline.algorithms.set(
            [
                self.algorithms["random-detector"],
                self.algorithms["random-binary-classifier"],
                self.algorithms["random-species-classifier"],
            ]
        )
        self.pipeline_two.algorithms.set(
            [
                self.algorithms["random-detector"],
                self.algorithms["random-binary-classifier"],
                self.algorithms["constant-species-classifier"],
            ]
        )

    def test_create_pipeline(self):
        assert self.pipeline.slug.startswith("test-pipeline")
        self.assertEqual(self.pipeline.algorithms.count(), 3)
        self.assertEqual(self.pipeline_two.algorithms.count(), 3)

        for algorithm in self.pipeline.algorithms.all():
            assert isinstance(algorithm, Algorithm)
            self.assertIn(algorithm.key, [algo.key for algo in ALGORITHM_CHOICES.values()])

    def test_collect_images(self):
        images = list(collect_images(collection=self.image_collection, pipeline=self.pipeline))
        assert len(images) == 2

    def test_collect_images_prefetches_deployment_and_data_source(self):
        """
        collect_images() must hand back SourceImage rows with deployment and
        deployment.data_source already joined, so the downstream queue_images_to_nats
        loop doesn't trigger N+1 FK lookups inside image.url() (see issue #1321).
        """
        from ami.main.models import S3StorageSource

        data_source = S3StorageSource.objects.create(
            name="ds-prefetch-test",
            bucket="prefetch-bucket",
            access_key="x",
            secret_key="y",  # noqa: S106 - fixture value, never used as a real credential
            public_base_url="https://example.invalid/",
            project=self.project,
        )
        deployment = Deployment.objects.create(
            name="prefetch-deployment", project=self.project, data_source=data_source
        )
        images = [
            SourceImage.objects.create(path=f"prefetch-{i}.jpg", deployment=deployment, project=self.project)
            for i in range(3)
        ]
        collection = SourceImageCollection.objects.create(project=self.project, name="prefetch-collection")
        collection.images.set(images)

        collected = list(collect_images(collection=collection, pipeline=self.pipeline))
        self.assertEqual(len(collected), 3)

        # Accessing deployment.data_source on the returned images should
        # require zero extra queries because select_related joined both.
        with self.assertNumQueries(0):
            for image in collected:
                self.assertEqual(image.deployment_id, deployment.pk)
                self.assertEqual(image.deployment.data_source_id, data_source.pk)
                self.assertEqual(image.deployment.data_source.public_base_url, "https://example.invalid/")

    def fake_pipeline_results(
        self,
        source_images: list[SourceImage],
        pipeline: Pipeline,
        alt_species_classifier: AlgorithmConfigResponse | None = None,
    ):
        # @TODO use the pipeline passed in to get the algorithms
        source_image_results = [SourceImageResponse(id=image.pk, url=image.path) for image in source_images]
        detector = ALGORITHM_CHOICES["random-detector"]
        binary_classifier = ALGORITHM_CHOICES["random-binary-classifier"]
        assert binary_classifier.category_map

        if alt_species_classifier is None:
            species_classifier = ALGORITHM_CHOICES["random-species-classifier"]
        else:
            species_classifier = alt_species_classifier
        assert species_classifier.category_map

        detection_results = [
            DetectionResponse(
                source_image_id=image.pk,
                bbox=BoundingBox(x1=0.0, y1=0.0, x2=1.0, y2=1.0),
                inference_time=0.4,
                algorithm=AlgorithmReference(
                    name=detector.name,
                    key=detector.key,
                ),
                timestamp=datetime.datetime.now(),
                classifications=[
                    ClassificationResponse(
                        classification=binary_classifier.category_map.labels[0],
                        labels=binary_classifier.category_map.labels,
                        scores=[0.9213],
                        algorithm=AlgorithmReference(
                            name=binary_classifier.name,
                            key=binary_classifier.key,
                        ),
                        timestamp=datetime.datetime.now(),
                        terminal=False,
                    ),
                    ClassificationResponse(
                        classification=species_classifier.category_map.labels[0],
                        labels=species_classifier.category_map.labels,
                        scores=[0.64333],
                        algorithm=AlgorithmReference(
                            name=species_classifier.name,
                            key=species_classifier.key,
                        ),
                        timestamp=datetime.datetime.now(),
                        terminal=True,
                    ),
                ],
            )
            for image in self.test_images
        ]
        fake_results = PipelineResultsResponse(
            pipeline=pipeline.slug,
            algorithms={
                detector.key: detector,
                binary_classifier.key: binary_classifier,
                species_classifier.key: species_classifier,
            },
            total_time=0.01,
            source_images=source_image_results,
            detections=detection_results,
        )
        return fake_results

    def test_save_results(self):
        results = self.fake_pipeline_results(self.test_images, self.pipeline)
        save_results(results)

        for image in self.test_images:
            image.save()
            self.assertEqual(image.detections_count, 1)

        # @TODO test the cached counts for detections, etc are updated on Events, Deployments, etc.

    def test_skip_existing_when_all_matching(self):
        """
        When processing images, skip images that have already been processed by the same set of algorithms.
        (must be the same detection algorithm and all classification algorithms)
        """

        images = list(collect_images(collection=self.image_collection, pipeline=self.pipeline))
        total_images = len(images)
        self.assertEqual(total_images, self.image_collection.images.count())

        created = save_results(self.fake_pipeline_results(images, self.pipeline), return_created=True)
        assert created, "Expected created objects to be returned in a PipelineSaveResults object"

        # Collect all detection algorithms used on the detections
        detections = created.detections
        detection_algos_used = {
            detection.detection_algorithm.name for detection in detections if detection.detection_algorithm
        }
        # detection_algos_used = set(Detection.objects.all().values_list("detection_algorithm__name", flat=True))

        # Assert it was only one algorithm, and it was the one we used
        self.assertEqual(
            detection_algos_used, {self.algorithms["random-detector"].name}, "Wrong detection algorithm used."
        )

        # Collect all classification algorithms used on the classifications
        classifications = created.classifications
        classification_algos_used = {
            classification.algorithm.name for classification in classifications if classification.algorithm
        }
        # classification_algos_used = set(Classification.objects.all().values_list("algorithm__name", flat=True))
        # Assert it was only one algorithm, and it was the one we used
        self.assertEqual(
            classification_algos_used,
            {self.algorithms["random-species-classifier"].name, self.algorithms["random-binary-classifier"].name},
            "Wrong classification algorithms used.",
        )

        images_again = list(collect_images(collection=self.image_collection, pipeline=self.pipeline))
        remaining_images_to_process = len(images_again)
        self.assertEqual(remaining_images_to_process, 0)

    def test_skip_existing_with_new_detector(self):
        images = list(collect_images(collection=self.image_collection, pipeline=self.pipeline))
        total_images = len(images)
        self.assertEqual(total_images, self.image_collection.images.count())
        pipeline_response = self.fake_pipeline_results(images, self.pipeline)
        save_results(pipeline_response)
        # Find the fist algo used where task_type is classification
        classifiers = [algo for algo in pipeline_response.algorithms.values() if algo.task_type == "classification"]
        last_classifier = Algorithm.objects.get(key=classifiers[-1].key)
        self.pipeline.algorithms.set(
            [
                Algorithm.objects.create(name="NEW Object Detector 2.0"),
                last_classifier,
            ]
        )
        images_again = list(collect_images(collection=self.image_collection, pipeline=self.pipeline))
        remaining_images_to_process = len(images_again)
        self.assertEqual(remaining_images_to_process, total_images)

    @unittest.skip("Not implemented yet")
    def test_skip_existing_with_new_classifier(self):
        """
        @TODO add support for skipping the detection model if only the classifier has changed.
        """
        images = list(collect_images(collection=self.image_collection, pipeline=self.pipeline))
        total_images = len(images)
        self.assertEqual(total_images, self.image_collection.images.count())
        pipeline_response = self.fake_pipeline_results(images, self.pipeline)
        # Find the fist algo used where task_type is detection
        first_detector_in_response = next(
            algo for algo in pipeline_response.algorithms.values() if algo.task_type == "detection"
        )
        first_detector = Algorithm.objects.get(key=first_detector_in_response.key)
        save_results(pipeline_response)
        self.pipeline.algorithms.set(
            [
                first_detector,
                Algorithm.objects.create(name="NEW Classifier 2.0"),
            ]
        )
        images_again = list(collect_images(collection=self.image_collection, pipeline=self.pipeline))
        remaining_images_to_process = len(images_again)
        self.assertEqual(remaining_images_to_process, total_images)

    @unittest.skip("Not implemented yet")
    def test_skip_existing_per_batch_during_processing(self):
        # Send the same batch to two simultaneous processing pipelines
        # @TODO this needs to test the `process_images()` function with a real pipeline
        # @TODO enable test when a pipeline is added to the CI environment in PR #576
        pass

    def test_unknown_algorithm_returned_by_processing_service(self):
        """
        Test that unknown algorithms returned by the processing service are handled correctly.

        Previously we allowed unknown algorithms to be returned by the pipeline,
        now all algorithms must be registered first from the processing service's /info
        endpoint.
        """
        fake_results = self.fake_pipeline_results(self.test_images, self.pipeline)

        new_detector = AlgorithmConfigResponse(
            name="Unknown Detector 5.1b-mobile", key="unknown-detector", task_type="detection"
        )
        new_classifier = AlgorithmConfigResponse(
            name="Unknown Classifier 3.0b-mega", key="unknown-classifier", task_type="classification"
        )

        fake_results.algorithms[new_detector.key] = new_detector
        fake_results.algorithms[new_classifier.key] = new_classifier

        for detection in fake_results.detections:
            detection.algorithm = AlgorithmReference(name=new_detector.name, key=new_detector.key)

            for classification in detection.classifications:
                classification.algorithm = AlgorithmReference(name=new_classifier.name, key=new_classifier.key)

        current_total_algorithm_count = Algorithm.objects.count()

        # Ensure an exception is raised that a new algorithm was not
        # pre-registered from the /info endpoint
        from ami.ml.exceptions import PipelineNotConfigured

        with self.assertRaises(PipelineNotConfigured):
            save_results(fake_results)

        # Ensure no new algorithms were added to the database
        new_algorithm_count = Algorithm.objects.count()
        self.assertEqual(new_algorithm_count, current_total_algorithm_count)

        # Ensure new algorithms were also added to the pipeline

    def test_yes_reprocess_if_new_terminal_algorithm_same_intermediate(self):
        """
        Test two pipelines with the same detector and same moth/non-moth classifier, but a new species classifier.

        The first pipeline should process the images and save the results.
        The second pipeline should reprocess the images.
        """

        images = list(collect_images(collection=self.image_collection, pipeline=self.pipeline))
        assert len(images), "No images to process"

        detector = Algorithm.objects.get(key="random-detector")
        binary_classifier = Algorithm.objects.get(key="random-binary-classifier")
        old_species_classifier = Algorithm.objects.get(key="random-species-classifier")

        Detection.objects.all().delete()
        results = save_results(self.fake_pipeline_results(images, self.pipeline), return_created=True)
        assert results is not None, "Expecected results to be returned in a PipelineSaveResults object"

        for raw_detection in results.detections:
            self.assertEqual(raw_detection.detection_algorithm, detector)

        # Ensure all results have the binary classifier and the old species classifier
        for saved_detection in Detection.objects.all():
            self.assertEqual(saved_detection.detection_algorithm, detector)
            # Assert that the binary classifier was used
            self.assertTrue(
                saved_detection.classifications.filter(algorithm=binary_classifier).exists(),
                "Binary classifier not used in first run",
            )
            # Assert that the old species classifier was used
            self.assertTrue(
                saved_detection.classifications.filter(algorithm=old_species_classifier).exists(),
                "Old species classifier not used in first run",
            )

        # Get another species classifier
        new_species_classifier_key = "constant-species-classifier"
        new_species_classifier = Algorithm.objects.get(key=new_species_classifier_key)
        # new_species_classifier_response = ALGORITHM_CHOICES[new_species_classifier_key]

        # Create a new pipeline with the same detector and the new species classifier
        new_pipeline = Pipeline.objects.create(
            name="New Pipeline",
        )

        new_pipeline.algorithms.set(
            [
                detector,
                binary_classifier,
                new_species_classifier,
            ]
        )

        # Process the images with the new pipeline
        images_again = list(collect_images(collection=self.image_collection, pipeline=new_pipeline))
        remaining_images_to_process = len(images_again)
        self.assertEqual(remaining_images_to_process, len(images), "Images not re-processed with new pipeline")

    def test_project_pipeline_config(self):
        """
        Test the default_config for a pipeline, as well as the project pipeline config.
        Ensure the project pipeline parameters override the pipeline defaults.
        """
        from ami.ml.models import ProjectPipelineConfig
        from ami.ml.schemas import PipelineRequestConfigParameters

        # Add config to the pipeline & project
        self.pipeline.default_config = PipelineRequestConfigParameters({"test_param": "test_value"})
        self.pipeline.save()
        self.project_pipeline_config = ProjectPipelineConfig.objects.create(
            project=self.project,
            pipeline=self.pipeline,
            config={"test_param": "project_value"},
        )
        self.project_pipeline_config.save()

        # Check the final config
        default_config = self.pipeline.get_config()
        self.assertEqual(default_config["test_param"], "test_value")
        final_config = self.pipeline.get_config(self.project.pk)
        self.assertEqual(final_config["test_param"], "project_value")

    def test_image_with_null_detection(self):
        """
        Test saving results for a pipeline that returns null detections for some images.
        """
        image = self.test_images[0]
        results = self.fake_pipeline_results([image], self.pipeline)

        # Manually change the results for a single image to a list of empty detections
        results.detections = []

        save_results(results)

        image.save()
        self.assertEqual(image.get_detections_count(), 0)  # detections_count should exclude null detections
        total_num_detections = image.detections.distinct().count()
        self.assertEqual(total_num_detections, 1)

        was_processed = image.get_was_processed()
        self.assertEqual(was_processed, True)

        # Also test filtering by algorithm
        was_processed = image.get_was_processed(algorithm_key="random-detector")
        self.assertEqual(was_processed, True)

    def test_filter_processed_images_skips_null_only_image(self):
        """
        An image with only null detections (processed, nothing found) should be
        skipped by filter_processed_images — it doesn't need reprocessing.
        """
        from ami.ml.models.pipeline import filter_processed_images

        image = self.test_images[0]
        detector = self.algorithms["random-detector"]

        # Simulate a previous run that found nothing: create a null detection
        Detection.objects.create(
            source_image=image,
            detection_algorithm=detector,
            bbox=None,
        )

        result = list(filter_processed_images([image], self.pipeline))
        self.assertEqual(result, [], "Image with only null detections should be skipped")

    def test_filter_processed_images_yields_image_with_null_and_real_unclassified(self):
        """
        An image with BOTH a null detection AND a real detection lacking classifications
        should NOT be skipped — the real detection still needs to be classified.
        """
        from ami.ml.models.pipeline import filter_processed_images

        image = self.test_images[0]
        detector = self.algorithms["random-detector"]

        # Null detection from a prior empty run
        Detection.objects.create(
            source_image=image,
            detection_algorithm=detector,
            bbox=None,
        )
        # Real detection with no classification yet
        Detection.objects.create(
            source_image=image,
            detection_algorithm=detector,
            bbox=[0.1, 0.2, 0.3, 0.4],
        )

        result = list(filter_processed_images([image], self.pipeline))
        self.assertEqual(result, [image], "Image with real unclassified detections should be yielded")

    def test_filter_processed_images_skips_null_and_fully_classified(self):
        """
        An image with a null detection AND a real detection that is fully classified
        by all pipeline algorithms should be skipped — it's fully processed.
        """
        from ami.ml.models.pipeline import filter_processed_images

        image = self.test_images[0]
        detector = self.algorithms["random-detector"]
        binary_classifier = self.algorithms["random-binary-classifier"]
        species_classifier = self.algorithms["random-species-classifier"]

        # Null detection from a prior empty run
        Detection.objects.create(
            source_image=image,
            detection_algorithm=detector,
            bbox=None,
        )
        # Real detection with classifications from all pipeline algorithms
        real_det = Detection.objects.create(
            source_image=image,
            detection_algorithm=detector,
            bbox=[0.1, 0.2, 0.3, 0.4],
        )
        taxon = Taxon.objects.create(name="Test Species Filtered")
        Classification.objects.create(
            detection=real_det,
            taxon=taxon,
            algorithm=binary_classifier,
            score=0.9,
            timestamp=datetime.datetime.now(),
        )
        Classification.objects.create(
            detection=real_det,
            taxon=taxon,
            algorithm=species_classifier,
            score=0.8,
            timestamp=datetime.datetime.now(),
        )

        result = list(filter_processed_images([image], self.pipeline))
        self.assertEqual(result, [], "Fully classified image with null detection should be skipped")

    def test_filter_processed_images_empty_input(self):
        """An empty iterable should yield nothing and run no per-image queries."""
        from ami.ml.models.pipeline import filter_processed_images

        with self.assertNumQueries(1):  # one query: pipeline.algorithms.all()
            result = list(filter_processed_images([], self.pipeline))
        self.assertEqual(result, [])

    def test_filter_processed_images_yields_all_when_pipeline_has_no_classifiers(self):
        """
        When a pipeline has no classifier algorithms registered, filter_processed_images
        must yield every image (matching the "Will reprocess all images" warning).
        Without the short-circuit, the empty `pipeline_classifier_ids` set makes
        `set().issubset(observed) == True` and every image with existing detections
        is silently skipped — directly contradicting the warning.
        """
        from ami.ml.models.pipeline import filter_processed_images

        detector_only_pipeline = Pipeline.objects.create(name="Detector Only Pipeline")
        detector_only_pipeline.algorithms.set([self.algorithms["random-detector"]])

        # Image with a real, fully-processed-looking detection from the detector.
        # Pre-short-circuit this would be skipped because the empty pipeline classifier
        # set is vacuously a subset of any observed-classifier set.
        image_with_detection = SourceImage.objects.create(path="no-classifier-with-det.jpg")
        Detection.objects.create(
            source_image=image_with_detection,
            detection_algorithm=self.algorithms["random-detector"],
            bbox=[0.1, 0.2, 0.3, 0.4],
        )
        image_unprocessed = SourceImage.objects.create(path="no-classifier-unprocessed.jpg")

        result = list(filter_processed_images([image_with_detection, image_unprocessed], detector_only_pipeline))
        self.assertEqual(result, [image_with_detection, image_unprocessed])

    def test_filter_processed_images_mixed_batch(self):
        """
        A mixed batch of images covering all five branches should yield only
        the ones that need processing, in input order.
        """
        from ami.ml.models.pipeline import filter_processed_images

        detector = self.algorithms["random-detector"]
        binary = self.algorithms["random-binary-classifier"]
        species = self.algorithms["random-species-classifier"]

        unprocessed = SourceImage.objects.create(path="unprocessed.jpg")
        null_only = SourceImage.objects.create(path="null_only.jpg")
        unclassified = SourceImage.objects.create(path="unclassified.jpg")
        fully_classified = SourceImage.objects.create(path="fully_classified.jpg")

        Detection.objects.create(source_image=null_only, detection_algorithm=detector, bbox=None)

        Detection.objects.create(source_image=unclassified, detection_algorithm=detector, bbox=[0.1, 0.2, 0.3, 0.4])

        real_det = Detection.objects.create(
            source_image=fully_classified, detection_algorithm=detector, bbox=[0.1, 0.2, 0.3, 0.4]
        )
        taxon = Taxon.objects.create(name="Test Mixed Batch Taxon")
        Classification.objects.create(
            detection=real_det, taxon=taxon, algorithm=binary, score=0.9, timestamp=datetime.datetime.now()
        )
        Classification.objects.create(
            detection=real_det, taxon=taxon, algorithm=species, score=0.8, timestamp=datetime.datetime.now()
        )

        images = [unprocessed, null_only, unclassified, fully_classified]
        result = list(filter_processed_images(images, self.pipeline))
        self.assertEqual(result, [unprocessed, unclassified])

    def test_filter_processed_images_query_count_is_bounded_per_batch(self):
        """
        With N images and batch_size=B, the query count should scale as
        O(N / B), not O(N). Locks in the bulk-query rewrite from issue #1321.

        Each batch issues at most:
          - 1 Detection bulk select
          - 1 Classification bulk select (only when real detections exist)
        Plus one initial pipeline.algorithms.all() that's shared across batches.
        """
        from ami.ml.models.pipeline import filter_processed_images

        detector = self.algorithms["random-detector"]
        binary = self.algorithms["random-binary-classifier"]
        species = self.algorithms["random-species-classifier"]
        taxon = Taxon.objects.create(name="Bounded Query Test Taxon")

        # 10 images. Batch 1: 5 fully-classified (triggers classification query).
        # Batch 2: 5 unprocessed (no detections, classification query skipped).
        images = [SourceImage.objects.create(path=f"bulk-{i}.jpg") for i in range(10)]
        for image in images[:5]:
            real_det = Detection.objects.create(
                source_image=image, detection_algorithm=detector, bbox=[0.1, 0.2, 0.3, 0.4]
            )
            Classification.objects.create(
                detection=real_det, taxon=taxon, algorithm=binary, score=0.9, timestamp=datetime.datetime.now()
            )
            Classification.objects.create(
                detection=real_det, taxon=taxon, algorithm=species, score=0.8, timestamp=datetime.datetime.now()
            )

        # Expected: 1 (pipeline) + 2 (detection × 2 batches) + 1 (classification, batch 1 only) = 4.
        with self.assertNumQueries(4):
            result = list(filter_processed_images(images, self.pipeline, batch_size=5))

        # First 5 fully classified → skipped. Last 5 fresh → yielded.
        self.assertEqual(result, images[5:])

    def test_filter_processed_images_emits_throttled_collect_progress(self):
        """
        When `job` and `total` are passed, filter_processed_images should call
        job.save(update_fields=["progress"]) at most once per
        COLLECT_PROGRESS_SAVE_INTERVAL_SECONDS of wall time, capped at
        COLLECT_PROGRESS_MAX_FRACTION. Keeps the reaper's "no forward progress"
        heuristic happy on multi-minute Collect stages without hot-saving the
        Job row on every chunk (issue #1321 follow-up).
        """
        from unittest.mock import patch

        from ami.jobs.models import Job, MLJob
        from ami.ml.models.pipeline import COLLECT_PROGRESS_MAX_FRACTION, filter_processed_images

        job = Job.objects.create(
            project=self.project,
            name="collect progress cadence test",
            pipeline=self.pipeline,
            job_type_key=MLJob.key,
        )
        # First save triggered MLJob.setup → "collect" stage exists.
        job.progress.get_stage("collect")

        images = [SourceImage.objects.create(path=f"cadence-{i}.jpg") for i in range(10)]

        # batch_size=3 over 10 images → 4 batches. Each monotonic() call
        # advances the clock by 3s. Expected sequence: init=0, batch1=3
        # (gap 3, no save), batch2=6 (gap 6, SAVE → last=6), batch3=9
        # (gap 3, no save), batch4=12 (gap 6, SAVE → last=12). Two saves.
        #
        # Counter-based stub (vs an iter/next sequence) means extra
        # monotonic() calls added to filter_processed_images later will
        # advance time faster and the assertion will fail with a clear
        # cadence mismatch, not StopIteration.
        clock = {"t": 0.0}

        def fake_monotonic():
            t = clock["t"]
            clock["t"] += 3.0
            return t

        with patch("ami.ml.models.pipeline.time.monotonic", side_effect=fake_monotonic):
            with patch.object(Job, "save", autospec=True) as mock_save:
                list(filter_processed_images(images, self.pipeline, batch_size=3, job=job, total=10))

        self.assertEqual(mock_save.call_count, 2, "Expected throttle to allow exactly 2 saves")
        for call in mock_save.call_args_list:
            self.assertEqual(
                call.kwargs.get("update_fields"),
                ["progress", "updated_at"],
                "Throttled saves must include `updated_at` so Django's auto_now fires "
                "and the reaper's stale-job heuristic sees forward motion.",
            )

        # Final emitted fraction comes from the second save (batch 4): processed=10,
        # total=10 → raw 1.0, capped at COLLECT_PROGRESS_MAX_FRACTION.
        collect_stage = job.progress.get_stage("collect")
        self.assertEqual(collect_stage.progress, COLLECT_PROGRESS_MAX_FRACTION)

    def test_filter_processed_images_skips_progress_emission_without_job(self):
        """
        Legacy callers that omit `job` (the only callers before this change)
        should see zero job.save() calls — the throttle block is fully gated
        on both `job` and `total` being passed.
        """
        from unittest.mock import patch

        from ami.jobs.models import Job
        from ami.ml.models.pipeline import filter_processed_images

        images = [SourceImage.objects.create(path=f"nojob-{i}.jpg") for i in range(5)]
        with patch.object(Job, "save", autospec=True) as mock_save:
            list(filter_processed_images(images, self.pipeline, batch_size=2))

        self.assertEqual(mock_save.call_count, 0)

    def test_null_detections_are_algorithm_specific(self):
        """
        Null detections from different pipelines/algorithms should not be shared.
        Each algorithm's null detection is tracked separately so that
        get_was_processed(algorithm_key=...) returns the correct per-algorithm status.
        """
        from ami.ml.models.pipeline import save_results

        image = self.test_images[0]

        # Pipeline 1 processes image, finds nothing
        results_1 = self.fake_pipeline_results([image], self.pipeline)
        results_1.detections = []
        save_results(results_1)

        # Create a second pipeline with a DIFFERENT detector algorithm
        detector_2, _ = Algorithm.objects.get_or_create(
            key="constant-detector",
            defaults={"name": "Constant Detector", "task_type": "detection"},
        )
        pipeline_2 = Pipeline.objects.create(name="Test Pipeline 2 Null Detect")
        pipeline_2.algorithms.set([detector_2])

        # Pipeline 2 processes the same image, also finds nothing
        results_2 = self.fake_pipeline_results([image], pipeline_2)
        results_2.detections = []
        save_results(results_2)

        # Both algorithms should independently mark the image as processed
        detector_1_key = self.algorithms["random-detector"].key
        self.assertTrue(image.get_was_processed(algorithm_key=detector_1_key))
        self.assertTrue(
            image.get_was_processed(algorithm_key="constant-detector"),
            "Pipeline 2's null detection should be created separately",
        )

        # Each pipeline must have its own null detection in the DB
        null_detections = image.detections.filter(bbox__isnull=True)
        self.assertEqual(null_detections.count(), 2, "Each pipeline should have its own null detection")

    def test_null_detection_deduplication_same_pipeline(self):
        """
        Running the same pipeline twice on the same image should not create
        duplicate null detections — the second run reuses the existing one.
        """
        from ami.ml.models.pipeline import save_results

        image = self.test_images[0]

        # Run pipeline twice, both with no detections
        results_1 = self.fake_pipeline_results([image], self.pipeline)
        results_1.detections = []
        save_results(results_1)

        results_2 = self.fake_pipeline_results([image], self.pipeline)
        results_2.detections = []
        save_results(results_2)

        # Should still be exactly one null detection
        null_detections = image.detections.filter(bbox__isnull=True)
        self.assertEqual(null_detections.count(), 1, "Same pipeline should not create duplicate null detections")

    def test_null_detection_does_not_create_phantom_occurrence(self):
        """
        Issue #1310: a null detection (empty-bbox sentinel marking "image processed,
        nothing found") must NOT spawn an Occurrence. Occurrences with no
        determination and no real detections leak to the API as ghost rows.
        """
        image = self.test_images[0]
        results = self.fake_pipeline_results([image], self.pipeline)
        results.detections = []  # pipeline found nothing

        save_results(results)

        null_dets = image.detections.filter(bbox__isnull=True)
        self.assertEqual(null_dets.count(), 1, "Null marker should still be created")
        self.assertIsNone(
            null_dets.first().occurrence,
            "Null detection must NOT be associated with an Occurrence",
        )
        # No phantom Occurrence in DB tied to this image at all
        phantom_occs = Occurrence.objects.filter(detections__source_image=image, determination__isnull=True)
        self.assertEqual(
            phantom_occs.count(),
            0,
            "No Occurrence with NULL determination should exist for an image that had no detections",
        )

    def test_captures_not_marked_processed_after_failure(self):
        """
        Issue #1310: null markers should only flag images as processed AFTER all
        downstream save steps (classifications, occurrences) succeed. If any
        downstream step raises, the image must remain unmarked so the next run
        re-processes it.

        Reproduces the field bug where 400 images ended up with null markers but
        no real detections — created when null-creation ran ahead of a later step
        that failed.
        """
        from unittest.mock import patch

        from ami.ml.models.pipeline import filter_processed_images

        # Mix: image_with_real has a detection in the response, image_without_real does not.
        # The without-real image is the one that would get a null marker.
        image_with_real, image_without_real = self.test_images
        results = self.fake_pipeline_results(self.test_images, self.pipeline)
        # Trim detections to only the first image so the second qualifies for null-marker creation
        results.detections = [d for d in results.detections if str(d.source_image_id) == str(image_with_real.pk)]

        # Inject failure in a step that runs AFTER detection bulk_create
        with patch(
            "ami.ml.models.pipeline.create_classifications",
            side_effect=RuntimeError("simulated classification failure"),
        ):
            with self.assertRaises(RuntimeError):
                save_results(results)

        # The image with no real detection must NOT have a null marker —
        # the run failed, so it should be re-tried.
        null_dets = image_without_real.detections.filter(bbox__isnull=True)
        self.assertEqual(
            null_dets.count(),
            0,
            "Image without real detections must not be marked processed when downstream step fails",
        )
        # filter_processed_images should still yield it for the next run
        retry_yield = list(filter_processed_images([image_without_real], self.pipeline))
        self.assertEqual(
            retry_yield,
            [image_without_real],
            "Image with failed run must be re-yielded for processing",
        )

    def test_null_marker_not_persisted_when_broker_dispatch_fails(self):
        """
        Issue #1310 (takeaway-review follow-up): null markers must be the FINAL
        write in save_results. Failures in any of the trailing steps —
        create_detection_images.delay (broker outage), update_calculated_fields_for_events
        (DB error), Deployment.update_calculated_fields (DB error) — must leave the
        image unmarked.

        This test patches the celery dispatch to raise, simulating a broker
        outage between the real-detection save and the null-marker save.
        """
        from unittest.mock import patch

        from ami.ml.models.pipeline import filter_processed_images

        image_with_real, image_without_real = self.test_images
        results = self.fake_pipeline_results(self.test_images, self.pipeline)
        results.detections = [d for d in results.detections if str(d.source_image_id) == str(image_with_real.pk)]

        with patch(
            "ami.ml.models.pipeline.create_detection_images.delay",
            side_effect=RuntimeError("simulated broker outage"),
        ):
            with self.assertRaises(RuntimeError):
                save_results(results)

        null_dets = image_without_real.detections.filter(bbox__isnull=True)
        self.assertEqual(
            null_dets.count(),
            0,
            "Null marker must not be persisted when create_detection_images.delay fails",
        )
        retry_yield = list(filter_processed_images([image_without_real], self.pipeline))
        self.assertEqual(
            retry_yield,
            [image_without_real],
            "Image with failed broker dispatch must be re-yielded for processing",
        )


class TestAlgorithmCategoryMaps(TestCase):
    def setUp(self):
        self.algorithm_responses = {
            key: get_or_create_algorithm_and_category_map(val) for key, val in ALGORITHM_CHOICES.items()
        }
        self.algorithms = {key: Algorithm.objects.get(key=key) for key in ALGORITHM_CHOICES.keys()}

    def test_create_algorithms_and_category_map(self):
        assert len(self.algorithms) > 0
        assert (
            Algorithm.objects.filter(
                key__in=self.algorithms.keys(),
            )
            .exclude(category_map=None)
            .count()
        ) > 0

    def test_algorithm_category_maps(self):
        for algorithm in Algorithm.objects.filter(
            key__in=self.algorithms.keys(),
        ).exclude(category_map=None):
            assert algorithm.category_map  # For type checker, not the test
            assert algorithm.category_map.labels
            assert algorithm.category_map.labels_hash
            assert algorithm.category_map.data

            # Ensure the full labels in the data match the simple, ordered list of labels
            sorted_data = sorted(algorithm.category_map.data, key=lambda x: x["index"])
            assert [category["label"] for category in sorted_data] == algorithm.category_map.labels

    def test_labels_hash_auto_generation(self):
        """Test that labels_hash is automatically generated when creating AlgorithmCategoryMap instances."""
        from ami.ml.models import AlgorithmCategoryMap

        # Test data
        test_data = [
            {"index": 0, "label": "coleoptera"},
            {"index": 1, "label": "diptera"},
            {"index": 2, "label": "lepidoptera"},
        ]
        test_labels = AlgorithmCategoryMap.labels_from_data(test_data)

        # Create instance using objects.create()
        category_map = AlgorithmCategoryMap.objects.create(labels=test_labels, data=test_data, version="test-v1")

        # Verify labels_hash was automatically generated
        self.assertIsNotNone(category_map.labels_hash)

        # Verify the hash matches what make_labels_hash would produce
        expected_hash = AlgorithmCategoryMap.make_labels_hash(test_labels)
        self.assertEqual(category_map.labels_hash, expected_hash)

        # Test that creating another instance with same labels produces same hash
        category_map2 = AlgorithmCategoryMap.objects.create(labels=test_labels, data=test_data, version="test-v2")

        self.assertEqual(category_map.labels_hash, category_map2.labels_hash)

    def test_labels_data_conversion_methods(self):
        from ami.ml.models import AlgorithmCategoryMap

        # Test data
        test_data = [
            {"index": 0, "label": "coleoptera"},
            {"index": 1, "label": "diptera"},
            {"index": 2, "label": "lepidoptera"},
        ]
        test_labels = AlgorithmCategoryMap.labels_from_data(test_data)

        # Convert labels to data and back
        converted_data = AlgorithmCategoryMap.data_from_labels(test_labels)
        converted_labels = AlgorithmCategoryMap.labels_from_data(converted_data)

        # Verify conversions are correct
        self.assertEqual(test_data, converted_data)
        self.assertEqual(test_labels, converted_labels)


class TestPostProcessingTasks(TestCase):
    @classmethod
    def setUpTestData(cls):
        # Project, taxa, images, events, and the collection are read-only from the
        # tests' point of view — build them once per class. Detections (and the
        # task runs that mutate them) happen per-test inside each test's
        # rolled-back transaction.
        cls.project, cls.deployment = setup_test_project()
        create_taxa(project=cls.project)
        cls._create_images_with_dimensions(deployment=cls.deployment)
        group_images_into_events(deployment=cls.deployment)

        # Create a simple SourceImageCollection for testing
        cls.collection = SourceImageCollection.objects.create(
            name="Test PostProcessing Collection",
            project=cls.project,
            method="manual",
            kwargs={"image_ids": list(cls.deployment.captures.values_list("pk", flat=True))},
        )
        cls.collection.populate_sample()

    @classmethod
    def _create_images_with_dimensions(
        cls,
        deployment,
        num_images: int = 5,
        width: int = 640,
        height: int = 480,
        update_deployment: bool = True,
    ):
        """
        Create SourceImages for a deployment with specified width and height.
        """

        created = []
        base_time = datetime.datetime.now(datetime.timezone.utc)

        for i in range(num_images):
            random_prefix = uuid.uuid4().hex[:8]
            path = pathlib.Path("test") / f"{random_prefix}_{i}.jpg"

            image = SourceImage.objects.create(
                deployment=deployment,
                project=deployment.project,
                timestamp=base_time + datetime.timedelta(minutes=i * 5),
                path=path,
                width=width,
                height=height,
            )
            created.append(image)

        if update_deployment:
            deployment.save(update_calculated_fields=True, regroup_async=False)

    def test_small_size_filter_assigns_not_identifiable(self):
        """
        Test that SmallSizeFilterTask correctly assigns 'Not identifiable'
        to detections below the configured minimum size.
        """
        # Create small detections on the collection images
        for image in self.collection.images.all():
            Detection.objects.create(
                source_image=image,
                bbox=[0, 0, 10, 10],  # small detection
                created_at=datetime.datetime.now(datetime.timezone.utc),
            ).associate_new_occurrence()

        # Prepare the task configuration
        task = SmallSizeFilterTask(
            source_image_collection_id=self.collection.pk,
            size_threshold=0.01,
        )

        task.run()

        # Verify that all small detections are now classified as "Not identifiable"
        not_identifiable_taxon = Taxon.objects.get(name="Not identifiable")
        detections = Detection.objects.filter(source_image__in=self.collection.images.all())

        for det in detections:
            latest_classification = Classification.objects.filter(detection=det).order_by("-created_at").first()
            self.assertIsNotNone(latest_classification, "Each detection should have a classification.")
            self.assertEqual(
                latest_classification.taxon,
                not_identifiable_taxon,
                f"Detection {det.pk} should be classified as 'Not identifiable'",
            )
            occurrence = det.occurrence
            self.assertIsNotNone(occurrence, f"Detection {det.pk} should belong to an occurrence.")
            occurrence.refresh_from_db()
            self.assertEqual(
                occurrence.determination,
                not_identifiable_taxon,
                f"Occurrence {occurrence.pk} should have its determination set to 'Not identifiable'.",
            )

    def test_occurrence_scope_only_touches_that_occurrence(self):
        """Per-occurrence scope: running with ``occurrence_id`` flags only that
        occurrence's detections and leaves sibling occurrences untouched."""
        detections = []
        for image in self.collection.images.all():
            det = Detection.objects.create(
                source_image=image,
                bbox=[0, 0, 10, 10],  # small
                created_at=datetime.datetime.now(datetime.timezone.utc),
            )
            det.associate_new_occurrence()
            detections.append(det)
        self.assertGreaterEqual(len(detections), 2)

        target = detections[0]
        SmallSizeFilterTask(occurrence_id=target.occurrence_id, size_threshold=0.01).run()

        not_identifiable_taxon = Taxon.objects.get(name="Not identifiable")
        self.assertEqual(
            Classification.objects.filter(detection=target, taxon=not_identifiable_taxon).count(),
            1,
            "The scoped occurrence's detection should be flagged.",
        )
        for other in detections[1:]:
            self.assertFalse(
                Classification.objects.filter(detection=other, taxon=not_identifiable_taxon).exists(),
                f"Detection {other.pk} outside the scoped occurrence should be untouched.",
            )

    def test_run_reports_stage_metrics_on_job(self):
        """The task surfaces ``detections_checked`` / ``detections_flagged`` /
        ``occurrences_updated`` as stage params on its Job so an operator can see
        what a run examined and changed without reading the log."""
        from ami.jobs.models import Job

        for image in self.collection.images.all():
            Detection.objects.create(
                source_image=image,
                bbox=[0, 0, 10, 10],  # small → flagged
                created_at=datetime.datetime.now(datetime.timezone.utc),
            ).associate_new_occurrence()
        total = Detection.objects.filter(source_image__in=self.collection.images.all()).count()
        self.assertGreater(total, 0)

        job = Job.objects.create(
            project=self.project,
            name="stage metrics test",
            job_type_key="post_processing",
            params={
                "task": "small_size_filter",
                "config": {"source_image_collection_id": self.collection.pk, "size_threshold": 0.01},
            },
        )
        job.progress.add_stage("Post Processing", key="post_processing")
        job.save()

        SmallSizeFilterTask(
            job=job,
            source_image_collection_id=self.collection.pk,
            size_threshold=0.01,
        ).run()

        job.refresh_from_db()
        params = {p.name: p.value for p in job.progress.get_stage("post_processing").params}
        self.assertEqual(params.get("detections_checked"), total)
        self.assertEqual(params.get("detections_flagged"), total)  # every detection is small
        # Each detection has its own occurrence here, so the deduped occurrence
        # count equals the detection count.
        self.assertEqual(params.get("occurrences_updated"), total)

    def test_progress_save_bumps_updated_at_for_reaper(self):
        """A progress heartbeat bumps ``Job.updated_at`` so the stale-job reaper
        leaves an actively-running post-processing job alone.

        ``check_stale_jobs`` revokes running jobs whose ``updated_at`` is older
        than ``STALLED_JOBS_MAX_MINUTES``. The progress save narrows to
        ``update_fields``, and Django does not auto-add ``auto_now`` fields to
        that list, so ``update_progress`` / ``report_stage_metrics`` must include
        ``updated_at`` explicitly. Without it a long run looks frozen and is
        reaped mid-flight even while streaming progress. This pins that both save
        paths move ``updated_at`` forward.
        """
        from ami.jobs.models import Job

        job = Job.objects.create(
            project=self.project,
            name="reaper heartbeat test",
            job_type_key="post_processing",
            params={
                "task": "small_size_filter",
                "config": {"source_image_collection_id": self.collection.pk, "size_threshold": 0.01},
            },
        )
        job.progress.add_stage("Post Processing", key="post_processing")
        job.save()

        task = SmallSizeFilterTask(
            job=job,
            source_image_collection_id=self.collection.pk,
            size_threshold=0.01,
        )

        # Freeze a baseline older than the reaper cutoff, then confirm each
        # heartbeat path drags updated_at back to "now". USE_TZ is False, so
        # updated_at is naive local time — mirror check_stale_jobs' own
        # naive datetime.now() comparison.
        stale = datetime.datetime.now() - datetime.timedelta(minutes=Job.STALLED_JOBS_MAX_MINUTES + 5)

        Job.objects.filter(pk=job.pk).update(updated_at=stale)
        task.update_progress(0.5)
        job.refresh_from_db()
        self.assertGreater(job.updated_at, stale, "update_progress must bump updated_at")

        Job.objects.filter(pk=job.pk).update(updated_at=stale)
        task.report_stage_metrics({"classifications_checked": 1})
        job.refresh_from_db()
        self.assertGreater(job.updated_at, stale, "report_stage_metrics must bump updated_at")

    def test_post_processing_stage_is_started_before_the_task_runs(self):
        """The stage reads as running from the moment the job starts.

        A task's first progress report can be minutes into a large run, and a stage
        left at CREATED renders as "Waiting to start" until then. See #1376.
        """
        from unittest.mock import patch

        from ami.jobs.models import Job, JobState, PostProcessingJob

        job = Job.objects.create(
            project=self.project,
            name="stage status test",
            job_type_key="post_processing",
            params={
                "task": "small_size_filter",
                "config": {"source_image_collection_id": self.collection.pk, "size_threshold": 0.01},
            },
        )

        observed = {}

        def _capture(self_task):
            stage = self_task.job.progress.get_stage("post_processing")
            observed["status"] = stage.status
            observed["label"] = stage.status_label

        with patch.object(SmallSizeFilterTask, "run", _capture):
            PostProcessingJob.run(job)

        self.assertEqual(observed["status"], JobState.STARTED)
        self.assertEqual(observed["label"], "0% complete")

    def test_occurrences_updated_counts_only_changed_determinations(self):
        """``occurrences_updated`` counts occurrences whose determination actually
        changed, not every occurrence the filter re-saved.

        An occurrence already pinned to a human identification keeps that
        determination when its detection is flagged "Not identifiable", so it must
        not inflate the metric. Only the un-identified occurrence, whose
        determination flips, is counted.
        """
        from ami.jobs.models import Job

        images = list(self.collection.images.all())
        self.assertGreaterEqual(len(images), 2)

        # Occurrence A: small detection, but a human identification pins the
        # determination — flagging the detection does not change it.
        human_taxon = Taxon.objects.create(name="Human-pinned species", rank=TaxonRank.SPECIES)
        identifier = User.objects.create_user(email="identifier@insectai.org")  # type: ignore[attr-defined]
        det_with_id = Detection.objects.create(
            source_image=images[0],
            bbox=[0, 0, 10, 10],
            created_at=datetime.datetime.now(datetime.timezone.utc),
        )
        det_with_id.associate_new_occurrence()
        Identification.objects.create(user=identifier, occurrence=det_with_id.occurrence, taxon=human_taxon)

        # Occurrence B: small detection, no identification — its determination
        # flips to "Not identifiable" and is the only real change.
        det_plain = Detection.objects.create(
            source_image=images[1],
            bbox=[0, 0, 10, 10],
            created_at=datetime.datetime.now(datetime.timezone.utc),
        )
        det_plain.associate_new_occurrence()

        job = Job.objects.create(
            project=self.project,
            name="changed-determination metric test",
            job_type_key="post_processing",
            params={
                "task": "small_size_filter",
                "config": {"source_image_collection_id": self.collection.pk, "size_threshold": 0.01},
            },
        )
        job.progress.add_stage("Post Processing", key="post_processing")
        job.save()

        SmallSizeFilterTask(
            job=job,
            source_image_collection_id=self.collection.pk,
            size_threshold=0.01,
        ).run()

        job.refresh_from_db()
        params = {p.name: p.value for p in job.progress.get_stage("post_processing").params}
        # Both detections are flagged small, but only the un-identified
        # occurrence's determination changes, so only it is counted.
        self.assertEqual(params.get("detections_flagged"), 2)
        self.assertEqual(params.get("occurrences_updated"), 1)


class TestTaskStateManager(TestCase):
    """Test TaskStateManager for job progress tracking."""

    def setUp(self):
        """Set up test fixtures."""
        from django.core.cache import cache

        from ami.ml.orchestration.async_job_state import AsyncJobStateManager

        cache.clear()
        self.job_id = 123
        self.manager = AsyncJobStateManager(self.job_id)
        self.image_ids = ["img1", "img2", "img3", "img4", "img5"]

    def _init_and_verify(self, image_ids):
        """Helper to initialize job and verify initial state."""
        self.manager.initialize_job(image_ids)
        progress = self.manager.get_progress("process")
        assert progress is not None
        self.assertEqual(progress.total, len(image_ids))
        self.assertEqual(progress.remaining, len(image_ids))
        self.assertEqual(progress.processed, 0)
        self.assertEqual(progress.percentage, 0.0)
        self.assertEqual(progress.failed, 0)
        return progress

    def test_initialize_job(self):
        """Test job initialization sets up tracking for all stages."""
        self._init_and_verify(self.image_ids)

        # Verify both stages are initialized
        for stage in self.manager.STAGES:
            progress = self.manager.get_progress(stage)
            assert progress is not None
            self.assertEqual(progress.total, len(self.image_ids))
            self.assertEqual(progress.failed, 0)

    def test_progress_tracking(self):
        """Test progress updates correctly as images are processed."""
        self._init_and_verify(self.image_ids)

        # Process 2 images
        progress = self.manager.update_state({"img1", "img2"}, "process")
        assert progress is not None
        self.assertEqual(progress.remaining, 3)
        self.assertEqual(progress.processed, 2)
        self.assertEqual(progress.percentage, 0.4)

        # Process 2 more images
        progress = self.manager.update_state({"img3", "img4"}, "process")
        assert progress is not None
        self.assertEqual(progress.remaining, 1)
        self.assertEqual(progress.processed, 4)
        self.assertEqual(progress.percentage, 0.8)

        # Process last image
        progress = self.manager.update_state({"img5"}, "process")
        assert progress is not None
        self.assertEqual(progress.remaining, 0)
        self.assertEqual(progress.processed, 5)
        self.assertEqual(progress.percentage, 1.0)

    def test_update_state_concurrent(self):
        """Test that concurrent workers update state correctly without data races."""
        self._init_and_verify(self.image_ids)

        # Three workers process disjoint image sets truly concurrently
        errors: list[BaseException] = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = [
                executor.submit(self.manager.update_state, {"img1", "img2"}, "process"),
                executor.submit(self.manager.update_state, {"img3"}, "process"),
                executor.submit(self.manager.update_state, {"img4", "img5"}, "process"),
            ]
            _errors = [f.exception() for f in concurrent.futures.as_completed(futures)]
            errors = [e for e in _errors if e is not None]

        self.assertEqual(errors, [], f"Concurrent workers raised exceptions: {errors}")

        # Final state reflects all concurrent updates
        final = self.manager.get_progress("process")
        assert final is not None
        self.assertEqual(final.processed, 5)
        self.assertEqual(final.remaining, 0)

        # SREM is idempotent: retrying already-processed images doesn't change counts
        progress_retry = self.manager.update_state({"img1", "img2"}, "process")
        assert progress_retry is not None
        self.assertEqual(progress_retry.processed, 5)

    def test_stages_independent(self):
        """Test that different stages track progress independently."""
        self._init_and_verify(self.image_ids)

        # Update process stage
        self.manager.update_state({"img1", "img2"}, "process")
        progress_process = self.manager.get_progress("process")
        assert progress_process is not None
        self.assertEqual(progress_process.remaining, 3)

        # Results stage should still have all images pending
        progress_results = self.manager.get_progress("results")
        assert progress_results is not None
        self.assertEqual(progress_results.remaining, 5)

    def test_empty_job(self):
        """Test handling of job with no images."""
        self.manager.initialize_job([])
        progress = self.manager.get_progress("process")
        assert progress is not None
        self.assertEqual(progress.total, 0)
        self.assertEqual(progress.percentage, 1.0)  # Empty job is 100% complete

    def test_cleanup(self):
        """Test cleanup removes all tracking keys."""
        self._init_and_verify(self.image_ids)

        # Verify keys exist
        progress = self.manager.get_progress("process")
        self.assertIsNotNone(progress)

        # Cleanup
        self.manager.cleanup()

        # Verify keys are gone
        progress = self.manager.get_progress("process")
        self.assertIsNone(progress)

    def test_failed_image_tracking(self):
        """Test basic failed image tracking with no double-counting on retries."""
        self._init_and_verify(self.image_ids)

        # Mark 2 images as failed in process stage
        progress = self.manager.update_state({"img1", "img2"}, "process", failed_image_ids={"img1", "img2"})
        assert progress is not None
        self.assertEqual(progress.failed, 2)

        # Retry same 2 images (fail again) - SADD is idempotent, no double-counting
        progress = self.manager.update_state(set(), "process", failed_image_ids={"img1", "img2"})
        assert progress is not None
        self.assertEqual(progress.failed, 2)

        # Fail a different image
        progress = self.manager.update_state(set(), "process", failed_image_ids={"img3"})
        assert progress is not None
        self.assertEqual(progress.failed, 3)

    def test_failed_and_processed_mixed(self):
        """Test mixed successful and failed processing in same batch."""
        self._init_and_verify(self.image_ids)

        # Process 2 successfully, 2 fail, 1 remains pending
        progress = self.manager.update_state(
            {"img1", "img2", "img3", "img4"}, "process", failed_image_ids={"img3", "img4"}
        )
        assert progress is not None
        self.assertEqual(progress.processed, 4)
        self.assertEqual(progress.failed, 2)
        self.assertEqual(progress.remaining, 1)
        self.assertEqual(progress.percentage, 0.8)

    def test_cleanup_removes_failed_set(self):
        """Test that cleanup removes failed image set."""
        self._init_and_verify(self.image_ids)

        # Add failed images and verify they're tracked
        progress = self.manager.update_state({"img1", "img2"}, "process", failed_image_ids={"img1", "img2"})
        assert progress is not None
        self.assertEqual(progress.failed, 2)

        # Cleanup
        self.manager.cleanup()

        # Verify all state is gone (get_progress returns None when total_key is deleted)
        progress = self.manager.get_progress("process")
        self.assertIsNone(progress)

    def test_update_state_raises_on_redis_error(self):
        """
        A transient Redis failure during update_state must propagate, not be
        swallowed as None. The None return is reserved for the genuine
        "state actually gone" case (see test below). Conflating the two is
        the #1219 bug that escalated transient connection resets into fatal
        job FAILUREs.
        """
        from unittest.mock import MagicMock, patch

        from redis.exceptions import RedisError

        self._init_and_verify(self.image_ids)

        # Replace the pipeline context manager with one whose execute() raises.
        # Everything upstream of execute() is safely called (srem/sadd/scard/get
        # on a pipeline only queue commands; they don't hit the network until
        # execute runs), so we only need to blow up at the execute boundary.
        pipe = MagicMock()
        pipe.execute.side_effect = RedisError("Connection reset by peer")
        fake_redis = MagicMock()
        fake_redis.pipeline.return_value.__enter__.return_value = pipe

        with patch.object(self.manager, "_get_redis", return_value=fake_redis):
            with self.assertRaises(RedisError):
                self.manager.update_state({"img1", "img2"}, "process")

    def test_update_state_returns_none_when_state_genuinely_missing(self):
        """
        When the job's total-images key is actually missing from Redis (job
        was never initialized, cleaned up, or TTL expired), update_state
        returns None. This is the only case that should trigger the
        terminal "state missing" failure path in the caller.
        """
        # Do NOT call initialize_job — the total key doesn't exist.
        progress = self.manager.update_state({"img1", "img2"}, "process")
        self.assertIsNone(progress)


class TestSaveResultsRefreshesDeploymentCounts(TestCase):
    """save_results must refresh Deployment cached counts, not just Event counts.

    Reproduces the "Station counts for occurrences and taxa are not always
    getting updated" report: prior to the fix, save_results refreshed
    update_calculated_fields_for_events but never the parent Deployment, so
    deployment.occurrences_count / taxa_count stayed at the pre-job value
    until something else (a manual deployment.save) ran.
    """

    def setUp(self):
        self.project = Project.objects.create(name="Refresh Counts Project")
        self.deployment = Deployment.objects.create(name="d1", project=self.project)
        event_time = datetime.datetime(2026, 4, 16, 22, 0, 0)
        self.event = Event.objects.create(
            project=self.project,
            deployment=self.deployment,
            group_by="2026-04-16",
            start=event_time,
            end=event_time,
        )
        self.image = SourceImage.objects.create(
            deployment=self.deployment,
            project=self.project,
            event=self.event,
            timestamp=event_time,
            path="refresh_counts_test.jpg",
        )
        self.collection = SourceImageCollection.objects.create(project=self.project, name="c")
        self.collection.images.add(self.image)

        self.pipeline = Pipeline.objects.create(name="Refresh Counts Pipeline (Random)")
        self.algorithms = {
            key: get_or_create_algorithm_and_category_map(val) for key, val in ALGORITHM_CHOICES.items()
        }
        self.pipeline.algorithms.set(
            [
                self.algorithms["random-detector"],
                self.algorithms["random-binary-classifier"],
                self.algorithms["random-species-classifier"],
            ]
        )

        self.deployment.update_calculated_fields(save=True)
        self.deployment.refresh_from_db()
        self.assertEqual(self.deployment.occurrences_count, 0)
        self.assertEqual(self.deployment.taxa_count, 0)

    def _fake_results(self):
        detector = ALGORITHM_CHOICES["random-detector"]
        binary_classifier = ALGORITHM_CHOICES["random-binary-classifier"]
        species_classifier = ALGORITHM_CHOICES["random-species-classifier"]
        assert binary_classifier.category_map and species_classifier.category_map

        detection = DetectionResponse(
            source_image_id=self.image.pk,
            bbox=BoundingBox(x1=0.0, y1=0.0, x2=1.0, y2=1.0),
            inference_time=0.1,
            algorithm=AlgorithmReference(name=detector.name, key=detector.key),
            timestamp=self.image.timestamp,
            classifications=[
                ClassificationResponse(
                    classification=binary_classifier.category_map.labels[0],
                    labels=binary_classifier.category_map.labels,
                    scores=[0.95],
                    algorithm=AlgorithmReference(name=binary_classifier.name, key=binary_classifier.key),
                    timestamp=self.image.timestamp,
                    terminal=False,
                ),
                ClassificationResponse(
                    classification=species_classifier.category_map.labels[0],
                    labels=species_classifier.category_map.labels,
                    scores=[0.85],
                    algorithm=AlgorithmReference(name=species_classifier.name, key=species_classifier.key),
                    timestamp=self.image.timestamp,
                    terminal=True,
                ),
            ],
        )
        return PipelineResultsResponse(
            pipeline=self.pipeline.slug,
            algorithms={
                detector.key: detector,
                binary_classifier.key: binary_classifier,
                species_classifier.key: species_classifier,
            },
            total_time=0.01,
            source_images=[SourceImageResponse(id=self.image.pk, url=self.image.path)],
            detections=[detection],
        )

    def test_deployment_counts_refresh_after_save_results(self):
        save_results(self._fake_results())

        self.deployment.refresh_from_db()
        self.assertGreater(
            self.deployment.occurrences_count,
            0,
            "Deployment.occurrences_count should reflect occurrences created by save_results",
        )
        self.assertGreater(
            self.deployment.taxa_count,
            0,
            "Deployment.taxa_count should reflect taxa from occurrences created by save_results",
        )


class AlgorithmProjectTestBase(APITestCase):
    """Shared fixture for the two project-scoped algorithm listings.

    Project A has an enabled pipeline carrying one algorithm that ran ("Algo Used")
    and one that never did ("Algo Configured Unused"), plus a disabled pipeline whose
    algorithm's determinations survive ("Algo Superseded"). Project B has its own
    used algorithm. "Algo Orphan" belongs to no pipeline and never ran anywhere.
    """

    def setUp(self):
        from ami.ml.models import ProjectPipelineConfig

        self.user = User.objects.create_user(email="algos@example.com", is_staff=True)  # type: ignore
        self.project = Project.objects.create(name="Algo Project A", create_defaults=False)
        self.other_project = Project.objects.create(name="Algo Project B", create_defaults=False)

        # Project A: an enabled-pipeline algorithm that has run, and one that never did.
        self.algo_used = Algorithm.objects.create(name="Algo Used", version=1)
        self.algo_configured_unused = Algorithm.objects.create(name="Algo Configured Unused", version=1)
        # Project A: an old version on a now-disabled pipeline, whose determinations survive.
        self.algo_superseded = Algorithm.objects.create(name="Algo Superseded", version=1)
        # Project B: a different algorithm, also used.
        self.algo_other_project = Algorithm.objects.create(name="Algo Other Project", version=1)
        # Unrelated algorithm attached to no pipeline and never run.
        self.algo_orphan = Algorithm.objects.create(name="Algo Orphan", version=1)

        enabled_pipeline = Pipeline.objects.create(name="Enabled Pipeline")
        enabled_pipeline.algorithms.add(self.algo_used, self.algo_configured_unused)
        ProjectPipelineConfig.objects.create(project=self.project, pipeline=enabled_pipeline, enabled=True)

        disabled_pipeline = Pipeline.objects.create(name="Disabled Pipeline")
        disabled_pipeline.algorithms.add(self.algo_superseded)
        ProjectPipelineConfig.objects.create(project=self.project, pipeline=disabled_pipeline, enabled=False)

        other_pipeline = Pipeline.objects.create(name="Other Project Pipeline")
        other_pipeline.algorithms.add(self.algo_other_project)
        ProjectPipelineConfig.objects.create(project=self.other_project, pipeline=other_pipeline, enabled=True)

        self._classify_in_project(self.algo_used, self.project)
        self._classify_in_project(self.algo_superseded, self.project)
        self._classify_in_project(self.algo_other_project, self.other_project)

        self.client.force_authenticate(user=self.user)

    def _classify_in_project(self, algorithm, project):
        """Give ``algorithm`` a classification whose capture belongs to ``project``."""
        source_image = SourceImage.objects.create(project=project)
        detection = Detection.objects.create(source_image=source_image)
        return Classification.objects.create(
            detection=detection,
            algorithm=algorithm,
            timestamp=datetime.datetime.now(datetime.timezone.utc),
        )


class TestAlgorithmViewSetProjectFilter(AlgorithmProjectTestBase):
    """
    The algorithm list endpoint scoped to a project shows what the project can run:
    the algorithms on its enabled pipelines.

    It reflects configuration, not history — a freshly configured project sees its
    algorithms before anything has run, and an algorithm only on a disabled pipeline
    is not offered even if it ran in the past. The algorithms that actually produced
    results are served separately as occurrence filter choices (see
    TestOccurrenceAlgorithmChoices), and detail pages stay reachable for any
    algorithm through the unscoped detail endpoint.
    """

    def _list_algorithm_names(self, project_id=None):
        params = {"project_id": project_id} if project_id is not None else {}
        url = reverse_with_params("api:algorithm-list", params=params)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        return {row["name"] for row in response.json()["results"]}

    def test_project_list_shows_enabled_pipeline_algorithms(self):
        """The scoped list is exactly the enabled pipelines' algorithms — including
        one that has never run, so a new project can see what it is set up to use
        before any job has completed."""
        names = self._list_algorithm_names(project_id=self.project.pk)
        self.assertEqual(names, {"Algo Used", "Algo Configured Unused"})

    def test_disabled_pipeline_algorithm_is_not_listed(self):
        """An algorithm only on a pipeline the project has disabled is not part of
        what the project can run, even though its past determinations survive. Those
        stay reachable through the occurrence filter choices and the detail endpoint."""
        names = self._list_algorithm_names(project_id=self.project.pk)
        self.assertNotIn("Algo Superseded", names)

    def test_other_project_only_sees_its_own_algorithms(self):
        names = self._list_algorithm_names(project_id=self.other_project.pk)
        self.assertEqual(names, {"Algo Other Project"})

    def test_unscoped_request_returns_all_algorithms(self):
        """Without project_id, current behavior lists all algorithms (unchanged)."""
        names = self._list_algorithm_names()
        for name in (
            "Algo Used",
            "Algo Superseded",
            "Algo Configured Unused",
            "Algo Other Project",
            "Algo Orphan",
        ):
            self.assertIn(name, names)

    def test_detail_endpoint_unscoped_even_with_project_id(self):
        """Detail stays unscoped so a link from a historical classification — here an
        algorithm outside the project's enabled set — still resolves to its details
        and category map."""
        url = reverse_with_params(
            "api:algorithm-detail",
            kwargs={"pk": self.algo_orphan.pk},
            params={"project_id": self.project.pk},
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["name"], "Algo Orphan")


class TestOccurrenceAlgorithmChoices(AlgorithmProjectTestBase):
    """
    The occurrence filter's algorithm choices, served at /occurrences/algorithms/,
    are exactly the algorithms that produced results in the project.

    An algorithm qualifies by owning output rows: a detection made by it (detectors,
    which never author a Classification) or a classification from it (classifiers and
    standalone post-processing algorithms such as class masking). A superseded
    pipeline version stays a choice as long as its results survive, and a configured
    algorithm that never ran is not offered — the filter never lists a value with
    zero matching occurrences.
    """

    def _choice_names(self, project_id):
        url = reverse_with_params("api:occurrence-algorithms", params={"project_id": project_id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        return {row["name"] for row in response.json()["results"]}

    def test_choices_are_exactly_the_algorithms_that_produced_results(self):
        """The classifier that ran and the superseded version whose determinations
        survive are choices; the enabled pipeline's never-run algorithm is not.
        This pins the semantic that choices follow results, not setup."""
        names = self._choice_names(self.project.pk)
        self.assertEqual(names, {"Algo Used", "Algo Superseded"})

    def test_configured_but_never_run_algorithm_is_not_a_choice(self):
        """Filtering by an algorithm that never produced a result would always return
        zero occurrences, so configuration alone does not admit one."""
        names = self._choice_names(self.project.pk)
        self.assertNotIn("Algo Configured Unused", names)

    def test_detector_that_ran_is_a_choice_although_it_never_classified(self):
        """Detectors set ``Detection.detection_algorithm`` and never write a
        Classification, so they are reachable only through their detections. This pins
        the regression where scoping choices purely by classification authorship
        dropped every localizer."""
        detector = Algorithm.objects.create(name="Algo Detector", version=1, task_type="localization")

        source_image = SourceImage.objects.create(project=self.project)
        Detection.objects.create(source_image=source_image, detection_algorithm=detector)
        self.assertFalse(Classification.objects.filter(algorithm=detector).exists())

        self.assertIn("Algo Detector", self._choice_names(self.project.pk))

    def test_post_processing_algorithm_with_classifications_is_a_choice(self):
        """A post-processing algorithm has no pipeline but produces determinations in
        the project, so it must be offered — otherwise the user cannot filter
        occurrences by the masked result."""
        masked_algo = Algorithm.objects.create(name="Class Masked Classifier", version=1)
        self._classify_in_project(masked_algo, self.project)

        self.assertIn("Class Masked Classifier", self._choice_names(self.project.pk))

    def test_classifications_in_other_project_do_not_leak(self):
        """An algorithm whose classifications live in another project must not appear."""
        other_masked_algo = Algorithm.objects.create(name="Other Project Masked", version=1)
        self._classify_in_project(other_masked_algo, self.other_project)

        self.assertNotIn("Other Project Masked", self._choice_names(self.project.pk))

    def test_project_id_is_required(self):
        """Choices are relative to a project; without one the request is rejected
        rather than listing every algorithm on the platform."""
        url = reverse_with_params("api:occurrence-algorithms")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 400)

    def test_response_is_paginated_like_a_list_endpoint(self):
        """The endpoint returns the standard ``{count, results}`` shape the
        frontend's entity picker consumes."""
        url = reverse_with_params("api:occurrence-algorithms", params={"project_id": self.project.pk})
        data = self.client.get(url).json()
        self.assertEqual(data["count"], 2)
        self.assertEqual(len(data["results"]), 2)

    def test_used_lookup_is_deduplicated_in_the_database(self):
        """``used_in_project`` matches one classification row per determination, so it
        must deduplicate in SQL rather than in Python.

        Without that, the rows fetched grow with a project's classification count —
        hundreds of thousands on a real masking run — to identify a handful of algorithms.
        The listed names are correct either way, so this asserts the row count of the
        underlying lookup rather than the endpoint's output. The ``.order_by()`` matters:
        Classification's default ordering would otherwise widen the DISTINCT back to one
        row per classification.
        """
        masked_algo = Algorithm.objects.create(name="Chatty Masked Classifier", version=1)
        for _ in range(5):
            self._classify_in_project(masked_algo, self.project)

        lookup = Classification.objects.filter(
            algorithm_id=masked_algo.pk,
            detection__source_image__project=self.project,
        ).values_list("algorithm_id", flat=True)

        self.assertEqual(len(list(lookup)), 5, "The lookup matches one row per classification")
        self.assertEqual(
            len(list(lookup.order_by().distinct())), 1, "Deduplicating collapses them to the one algorithm"
        )
        self.assertIn("Chatty Masked Classifier", self._choice_names(self.project.pk))


class TestDetectionEmbeddings(TestCase):
    """
    Feature vectors returned with a classification are stored as DetectionEmbedding rows,
    so that a classifier head can be retrained from verified labels later without running
    the backbone over every crop again.
    """

    def setUp(self):
        self.project = Project.objects.create(name="Embedding Test Project")
        self.test_images = [
            SourceImage.objects.create(path="embed1-20240101000000.jpg", project=self.project),
            SourceImage.objects.create(path="embed2-20240101001000.jpg", project=self.project),
        ]
        self.pipeline = Pipeline.objects.create(name="Embedding Test Pipeline")
        self.algorithms = {
            key: get_or_create_algorithm_and_category_map(val) for key, val in ALGORITHM_CHOICES.items()
        }
        self.pipeline.algorithms.set(
            [
                self.algorithms["random-detector"],
                self.algorithms["random-species-classifier"],
            ]
        )

    def _results(self, features: list[float] | None) -> PipelineResultsResponse:
        detector = ALGORITHM_CHOICES["random-detector"]
        classifier = ALGORITHM_CHOICES["random-species-classifier"]
        assert classifier.category_map
        return PipelineResultsResponse(
            pipeline=self.pipeline.slug,
            total_time=0.01,
            source_images=[SourceImageResponse(id=image.pk, url=image.path) for image in self.test_images],
            detections=[
                DetectionResponse(
                    source_image_id=image.pk,
                    bbox=BoundingBox(x1=0.0, y1=0.0, x2=1.0, y2=1.0),
                    algorithm=AlgorithmReference(name=detector.name, key=detector.key),
                    timestamp=datetime.datetime.now(),
                    classifications=[
                        ClassificationResponse(
                            classification=classifier.category_map.labels[0],
                            labels=classifier.category_map.labels,
                            scores=[0.77],
                            features=features,
                            algorithm=AlgorithmReference(name=classifier.name, key=classifier.key),
                            timestamp=datetime.datetime.now(),
                            terminal=True,
                        ),
                    ],
                )
                for image in self.test_images
            ],
        )

    def _enable_flag(self):
        self.project.feature_flags.store_classification_embeddings = True
        self.project.save()

    def test_embeddings_are_not_saved_when_the_flag_is_off(self):
        save_results(self._results(features=[0.5] * EMBEDDING_DIMENSIONS))
        self.assertEqual(DetectionEmbedding.objects.count(), 0, "Storing embeddings must be opt-in")

    def test_embeddings_are_saved_when_the_flag_is_on(self):
        self._enable_flag()
        save_results(self._results(features=[0.5] * EMBEDDING_DIMENSIONS))

        self.assertEqual(DetectionEmbedding.objects.count(), len(self.test_images))
        embedding = DetectionEmbedding.objects.first()
        assert embedding
        self.assertEqual(embedding.algorithm, self.algorithms["random-species-classifier"])
        self.assertEqual(len(embedding.vector.to_list()), EMBEDDING_DIMENSIONS)

    def test_a_classification_without_features_stores_nothing(self):
        self._enable_flag()
        save_results(self._results(features=None))
        self.assertEqual(DetectionEmbedding.objects.count(), 0)

    def test_a_vector_of_the_wrong_width_is_skipped_not_fatal(self):
        """A backbone of a different width must not break the job."""
        self._enable_flag()
        save_results(self._results(features=[0.5] * 768))
        self.assertEqual(DetectionEmbedding.objects.count(), 0)
        self.assertEqual(
            Classification.objects.filter(detection__source_image__project=self.project).count(),
            len(self.test_images),
            "Classifications are still saved",
        )

    def test_reprocessing_the_same_detections_does_not_raise(self):
        """
        The unique constraint on (detection, algorithm) must be ignored, not raised,
        so re-running a pipeline over processed captures stays safe.
        """
        self._enable_flag()
        results = self._results(features=[0.5] * EMBEDDING_DIMENSIONS)
        save_results(results)
        self.project.feature_flags.reprocess_all_images = True
        self.project.save()
        save_results(results)
        self.assertEqual(DetectionEmbedding.objects.count(), len(self.test_images), "No duplicate embeddings")

    def test_nearest_neighbour_search_finds_the_closest_vector(self):
        """The point of storing these: find similar crops without leaving the database."""
        from pgvector.django import CosineDistance

        self._enable_flag()
        save_results(self._results(features=[0.5] * EMBEDDING_DIMENSIONS))

        near = [0.5] * EMBEDDING_DIMENSIONS
        far = [0.5] * (EMBEDDING_DIMENSIONS - 1) + [-40.0]
        # Constrained to one algorithm: vectors from different backbones are not comparable.
        results = (
            DetectionEmbedding.objects.filter(algorithm=self.algorithms["random-species-classifier"])
            .annotate(near=CosineDistance("vector", near))
            .annotate(far=CosineDistance("vector", far))
            .first()
        )
        assert results
        self.assertLess(results.near, results.far, "An identical vector must be closer than a different one")


class TestExportVerifiedTrainingData(TestCase):
    """
    The export command turns what people verified in the UI into a training set for a
    classifier head: embeddings in, labels from the human identifications.
    """

    def setUp(self):
        self.project = Project.objects.create(name="Export Test Project")
        self.project.feature_flags.store_classification_embeddings = True
        self.project.save()

        self.user = User.objects.create_user(email="verifier@example.com", password="testpass123")
        self.images = [
            SourceImage.objects.create(path=f"export{i}-2024010100{i:02d}00.jpg", project=self.project)
            for i in range(20)
        ]
        self.pipeline = Pipeline.objects.create(name="Export Test Pipeline")
        self.algorithms = {
            key: get_or_create_algorithm_and_category_map(val) for key, val in ALGORITHM_CHOICES.items()
        }
        self.classifier = self.algorithms["random-species-classifier"]
        self.pipeline.algorithms.set([self.algorithms["random-detector"], self.classifier])

        save_results(self._results())
        self.taxa = [
            Taxon.objects.create(name="Testus unus", rank=TaxonRank.SPECIES.name),
            Taxon.objects.create(name="Testus duo", rank=TaxonRank.SPECIES.name),
        ]

    def _results(self) -> PipelineResultsResponse:
        detector = ALGORITHM_CHOICES["random-detector"]
        classifier = ALGORITHM_CHOICES["random-species-classifier"]
        assert classifier.category_map
        return PipelineResultsResponse(
            pipeline=self.pipeline.slug,
            total_time=0.01,
            source_images=[SourceImageResponse(id=image.pk, url=image.path) for image in self.images],
            detections=[
                DetectionResponse(
                    source_image_id=image.pk,
                    bbox=BoundingBox(x1=0.0, y1=0.0, x2=1.0, y2=1.0),
                    algorithm=AlgorithmReference(name=detector.name, key=detector.key),
                    timestamp=datetime.datetime.now(),
                    classifications=[
                        ClassificationResponse(
                            classification=classifier.category_map.labels[0],
                            labels=classifier.category_map.labels,
                            scores=[0.5],
                            # A different vector per image, so the classes are separable.
                            features=[float(i)] * EMBEDDING_DIMENSIONS,
                            algorithm=AlgorithmReference(name=classifier.name, key=classifier.key),
                            timestamp=datetime.datetime.now(),
                            terminal=True,
                        ),
                    ],
                )
                for i, image in enumerate(self.images)
            ],
        )

    def _verify_all(self):
        """A human confirms a species for every occurrence, alternating between two taxa."""
        for i, occurrence in enumerate(Occurrence.objects.filter(project=self.project).order_by("pk")):
            Identification.objects.create(
                occurrence=occurrence,
                taxon=self.taxa[i % len(self.taxa)],
                user=self.user,
            )

    def _run_export(self, **kwargs) -> dict:
        import tempfile

        from django.core.management import call_command

        with tempfile.TemporaryDirectory() as tmp:
            out = pathlib.Path(tmp) / "export"
            call_command(
                "export_verified_training_data",
                project=self.project.pk,
                algorithm=self.classifier.key,
                output=str(out),
                test_fraction=0.5,
                stdout=io.StringIO(),
                **kwargs,
            )
            data = np.load(out.with_suffix(".npz"))
            meta = json.loads(out.with_suffix(".json").read_text())
            return {"npz": {k: data[k] for k in data.files}, "meta": meta}

    def test_export_requires_something_verified(self):
        from django.core.management import call_command
        from django.core.management.base import CommandError

        with self.assertRaises(CommandError):
            call_command(
                "export_verified_training_data",
                project=self.project.pk,
                algorithm=self.classifier.key,
                stdout=io.StringIO(),
            )

    def test_export_pairs_embeddings_with_human_labels(self):
        self._verify_all()
        result = self._run_export(min_per_species=1)

        self.assertEqual(result["npz"]["features"].shape, (len(self.images), EMBEDDING_DIMENSIONS))
        self.assertEqual(sorted(result["meta"]["classes"]), ["Testus duo", "Testus unus"])
        self.assertEqual(result["meta"]["rows"], len(self.images))
        self.assertEqual(result["meta"]["algorithm"]["key"], self.classifier.key)

    def test_a_withdrawn_identification_is_not_exported(self):
        self._verify_all()
        Identification.objects.all().update(withdrawn=True)

        from django.core.management import call_command
        from django.core.management.base import CommandError

        with self.assertRaises(CommandError):
            call_command(
                "export_verified_training_data",
                project=self.project.pk,
                algorithm=self.classifier.key,
                stdout=io.StringIO(),
            )

    def test_the_split_is_stable_across_runs(self):
        """An eval set that moves between runs cannot be used to compare two heads."""
        self._verify_all()
        first = self._run_export(min_per_species=1)
        second = self._run_export(min_per_species=1)
        self.assertTrue((first["npz"]["split"] == second["npz"]["split"]).all())
        self.assertEqual(first["meta"]["settings"]["split_grouped_by"], "occurrence")

    def test_rare_species_are_dropped(self):
        self._verify_all()
        # Give one occurrence a species nothing else has.
        rare = Taxon.objects.create(name="Testus rarus", rank=TaxonRank.SPECIES.name)
        occurrence = Occurrence.objects.filter(project=self.project).order_by("pk").first()
        assert occurrence
        Identification.objects.create(occurrence=occurrence, taxon=rare, user=self.user)

        result = self._run_export(min_per_species=2)
        self.assertNotIn("Testus rarus", result["meta"]["classes"])


class TestTrainingDataAPI(APITestCase):
    """
    The endpoint a trainer pulls from: verified labels paired with their embeddings.
    """

    def setUp(self):
        self.project = Project.objects.create(name="Training API Project")
        self.project.feature_flags.store_classification_embeddings = True
        self.project.save()
        self.user = User.objects.create_user(email="trainer@example.com", password="testpass123")
        self.project.members.add(self.user)

        self.images = [
            SourceImage.objects.create(path=f"train{i}-2024010100{i:02d}00.jpg", project=self.project)
            for i in range(4)
        ]
        self.pipeline = Pipeline.objects.create(name="Training API Pipeline")
        self.algorithms = {
            key: get_or_create_algorithm_and_category_map(val) for key, val in ALGORITHM_CHOICES.items()
        }
        self.classifier = self.algorithms["random-species-classifier"]
        self.pipeline.algorithms.set([self.algorithms["random-detector"], self.classifier])

        detector = ALGORITHM_CHOICES["random-detector"]
        classifier = ALGORITHM_CHOICES["random-species-classifier"]
        assert classifier.category_map
        save_results(
            PipelineResultsResponse(
                pipeline=self.pipeline.slug,
                total_time=0.01,
                source_images=[SourceImageResponse(id=i.pk, url=i.path) for i in self.images],
                detections=[
                    DetectionResponse(
                        source_image_id=image.pk,
                        bbox=BoundingBox(x1=0.0, y1=0.0, x2=1.0, y2=1.0),
                        algorithm=AlgorithmReference(name=detector.name, key=detector.key),
                        timestamp=datetime.datetime.now(),
                        classifications=[
                            ClassificationResponse(
                                classification=classifier.category_map.labels[0],
                                labels=classifier.category_map.labels,
                                scores=[0.5],
                                features=[float(i)] * EMBEDDING_DIMENSIONS,
                                algorithm=AlgorithmReference(name=classifier.name, key=classifier.key),
                                timestamp=datetime.datetime.now(),
                                terminal=True,
                            )
                        ],
                    )
                    for i, image in enumerate(self.images)
                ],
            )
        )
        self.taxon = Taxon.objects.create(name="Trainicus testus", rank=TaxonRank.SPECIES.name)
        for occurrence in Occurrence.objects.filter(project=self.project):
            Identification.objects.create(occurrence=occurrence, taxon=self.taxon, user=self.user)

        self.url = reverse_with_params("api:training-data-list")
        self.summary_url = reverse_with_params("api:training-data-summary")
        self.params = {"project_id": self.project.pk, "algorithm": self.classifier.key}

    def test_anonymous_users_get_nothing(self):
        response = self.client.get(self.url, self.params)
        self.assertEqual(response.status_code, 401)

    def test_rows_carry_the_human_label_and_the_embedding(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.url, self.params)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], len(self.images))
        row = response.json()["results"][0]
        self.assertEqual(row["label"], self.taxon.name)
        self.assertEqual(len(row["features"]), EMBEDDING_DIMENSIONS)
        self.assertIn(row["split"], ("train", "test"))

    def test_features_can_be_left_out(self):
        """Callers deciding whether a retrain is worth it should not pull megabytes."""
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.url, {**self.params, "include_features": "false"})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("features", response.json()["results"][0])

    def test_algorithm_is_required(self):
        """Mixing backbones would produce a meaningless training set, so it cannot be omitted."""
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.url, {"project_id": self.project.pk})
        self.assertEqual(response.status_code, 400)

    def test_unknown_algorithm_is_404(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.url, {**self.params, "algorithm": "does-not-exist"})
        self.assertEqual(response.status_code, 404)

    def test_project_is_required(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.url, {"algorithm": self.classifier.key})
        self.assertEqual(response.status_code, 400)

    def test_unverified_occurrences_are_not_returned(self):
        self.client.force_authenticate(user=self.user)
        Identification.objects.all().update(withdrawn=True)
        response = self.client.get(self.url, self.params)
        self.assertEqual(response.json()["count"], 0)

    def test_summary_reports_counts_without_sending_vectors(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.summary_url, self.params)
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["rows"], len(self.images))
        self.assertEqual(body["counts"][self.taxon.name], len(self.images))
        self.assertEqual(body["dimensions"], EMBEDDING_DIMENSIONS)
        self.assertEqual(body["train"] + body["test"], len(self.images))
        self.assertEqual(body["settings"]["split_grouped_by"], "occurrence")

    def test_the_split_matches_the_export_command(self):
        """The API and the export must not disagree about what is held out."""
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.url, {**self.params, "include_features": "false"})
        for row in response.json()["results"]:
            self.assertEqual(row["split"], training_data.split_for(row["occurrence_id"]))


class TestTrainableFlag(TestCase):
    """A service declares which of its algorithms can be retrained; Antenna mirrors that."""

    def test_trainable_is_mirrored_from_the_service_config(self):
        config = ALGORITHM_CHOICES["random-species-classifier"].copy(update={"trainable": True})
        algorithm = get_or_create_algorithm_and_category_map(config)
        self.assertTrue(algorithm.trainable)

    def test_algorithms_are_not_trainable_by_default(self):
        algorithm = get_or_create_algorithm_and_category_map(ALGORITHM_CHOICES["random-detector"])
        self.assertFalse(algorithm.trainable)

    def test_the_flag_follows_the_service_when_it_changes(self):
        """A service that gains training support must not need its algorithm deleted."""
        key = "random-species-classifier"
        get_or_create_algorithm_and_category_map(ALGORITHM_CHOICES[key])
        updated = get_or_create_algorithm_and_category_map(ALGORITHM_CHOICES[key].copy(update={"trainable": True}))
        self.assertTrue(updated.trainable)


class TestTrainingDatasetAndJob(TestCase):
    """
    Antenna prepares the training set as a file and hands the service a URL to it.
    """

    def setUp(self):
        self.project = Project.objects.create(name="Training Job Project")
        self.project.feature_flags.store_classification_embeddings = True
        self.project.save()
        self.user = User.objects.create_user(email="trainjob@example.com", password="testpass123")

        self.images = [
            SourceImage.objects.create(path=f"tj{i}-2024010100{i:02d}00.jpg", project=self.project) for i in range(12)
        ]
        self.pipeline = Pipeline.objects.create(name="Training Job Pipeline")
        self.algorithms = {
            key: get_or_create_algorithm_and_category_map(val) for key, val in ALGORITHM_CHOICES.items()
        }
        self.classifier = self.algorithms["random-species-classifier"]
        self.classifier.trainable = True
        # Half in, half out. The held-out split is a hash of the occurrence id, so the
        # default 0.2 can leave no rows on one side and make the build refuse.
        self.classifier.training_config.test_fraction = 0.5
        self.classifier.save()
        self.pipeline.algorithms.set([self.algorithms["random-detector"], self.classifier])

        detector = ALGORITHM_CHOICES["random-detector"]
        classifier = ALGORITHM_CHOICES["random-species-classifier"]
        assert classifier.category_map
        save_results(
            PipelineResultsResponse(
                pipeline=self.pipeline.slug,
                total_time=0.01,
                source_images=[SourceImageResponse(id=i.pk, url=i.path) for i in self.images],
                detections=[
                    DetectionResponse(
                        source_image_id=image.pk,
                        bbox=BoundingBox(x1=0.0, y1=0.0, x2=1.0, y2=1.0),
                        algorithm=AlgorithmReference(name=detector.name, key=detector.key),
                        timestamp=datetime.datetime.now(),
                        classifications=[
                            ClassificationResponse(
                                classification=classifier.category_map.labels[0],
                                labels=classifier.category_map.labels,
                                scores=[0.5],
                                features=[float(i)] * EMBEDDING_DIMENSIONS,
                                algorithm=AlgorithmReference(name=classifier.name, key=classifier.key),
                                timestamp=datetime.datetime.now(),
                                terminal=True,
                            )
                        ],
                    )
                    for i, image in enumerate(self.images)
                ],
            )
        )
        self.taxa = [
            Taxon.objects.create(name="Datasetus unus", rank=TaxonRank.SPECIES.name),
            Taxon.objects.create(name="Datasetus duo", rank=TaxonRank.SPECIES.name),
        ]

    def _verify_all(self):
        for i, occurrence in enumerate(Occurrence.objects.filter(project=self.project).order_by("pk")):
            Identification.objects.create(occurrence=occurrence, taxon=self.taxa[i % 2], user=self.user)

    def test_dataset_holds_the_embeddings_and_the_human_labels(self):
        from ami.ml.training_dataset import build_training_dataset

        self._verify_all()
        result = build_training_dataset(
            project=self.project, algorithm=self.classifier, min_per_species=1, test_fraction=0.5
        )

        with default_storage.open(result["path"], "rb") as f:
            archive = np.load(f, allow_pickle=True)
            features = archive["features"]
            classes = [str(c) for c in archive["classes"]]
            metadata = json.loads(str(archive["metadata"]))

        self.assertEqual(features.shape, (len(self.images), EMBEDDING_DIMENSIONS))
        self.assertEqual(sorted(classes), sorted(t.name for t in self.taxa))
        self.assertEqual(metadata["rows"], len(self.images))
        self.assertEqual(metadata["train"] + metadata["test"], len(self.images))
        default_storage.delete(result["path"])

    def test_vectors_are_stored_as_float16(self):
        """float16 is what Postgres holds, so anything wider ships bytes that carry nothing."""
        from ami.ml.training_dataset import build_training_dataset

        self._verify_all()
        result = build_training_dataset(
            project=self.project, algorithm=self.classifier, min_per_species=1, test_fraction=0.5
        )
        with default_storage.open(result["path"], "rb") as f:
            self.assertEqual(np.load(f, allow_pickle=True)["features"].dtype, np.float16)
        default_storage.delete(result["path"])

    def test_the_dataset_names_the_url_it_was_written_to(self):
        """
        The version a retrain produces has to name the exact set it was fitted on.

        The service echoes this metadata back in its result, and that is where
        ``Algorithm.training_info.dataset_url`` comes from, so a missing url leaves every
        retrained version with no record of its training data.
        """
        from ami.ml.training_dataset import build_training_dataset

        self._verify_all()
        result = build_training_dataset(
            project=self.project, algorithm=self.classifier, min_per_species=1, test_fraction=0.5
        )

        with default_storage.open(result["path"], "rb") as f:
            metadata = json.loads(str(np.load(f, allow_pickle=True)["metadata"]))

        self.assertEqual(metadata["url"], result["url"])
        self.assertIn(result["path"], metadata["url"])
        default_storage.delete(result["path"])

    def test_nothing_verified_means_no_file_is_written(self):
        from ami.ml.training_dataset import NotEnoughVerifiedData, build_training_dataset

        with self.assertRaises(NotEnoughVerifiedData):
            build_training_dataset(project=self.project, algorithm=self.classifier)

    def test_the_job_fails_cleanly_when_there_is_nothing_to_train_on(self):
        """A data problem should read as a message, not a traceback."""
        from ami.jobs.models import Job, JobState, TrainClassifierJob

        job = Job.objects.create(
            project=self.project,
            name="Retrain",
            job_type_key=TrainClassifierJob.key,
            params={"algorithm_key": self.classifier.key},
        )
        job.run()
        job.refresh_from_db()
        self.assertEqual(job.status, JobState.FAILURE.name)
        self.assertIn("error", job.result)

    def test_the_job_refuses_an_algorithm_the_service_cannot_train(self):
        from ami.jobs.models import Job, TrainClassifierJob

        self._verify_all()
        job = Job.objects.create(
            project=self.project,
            name="Retrain a detector",
            job_type_key=TrainClassifierJob.key,
            params={"algorithm_key": self.algorithms["random-detector"].key},
        )
        with self.assertRaises(ValueError):
            job.run()

    def test_the_job_refuses_when_only_a_pull_worker_serves_the_algorithm(self):
        """Antenna cannot POST to a worker with no endpoint, so it must say so, not hang."""
        from ami.jobs.models import Job, TrainClassifierJob

        self._verify_all()
        self.project.processing_services.clear()
        worker = ProcessingService.objects.create(name="Pull worker", endpoint_url=None)
        worker.projects.add(self.project)
        worker.pipelines.add(self.pipeline)

        job = Job.objects.create(
            project=self.project,
            name="Retrain",
            job_type_key=TrainClassifierJob.key,
            params={"algorithm_key": self.classifier.key, "min_per_species": 1},
        )
        with self.assertRaises(ValueError) as ctx:
            job.run()
        self.assertIn("pull-mode", str(ctx.exception).lower())


class TestAbsoluteMediaURL(TestCase):
    def test_an_absolute_url_is_left_alone(self):
        """In production MEDIA_URL is already an S3 URL."""
        from ami.ml.training_dispatch import absolute_media_url

        url = "https://bucket.s3.amazonaws.com/uploads/training/set.npz"
        self.assertEqual(absolute_media_url(url), url)

    def test_a_relative_path_gets_a_base(self):
        from ami.ml.training_dispatch import absolute_media_url

        self.assertEqual(
            absolute_media_url("/media/training/set.npz", "http://antenna:8000"),
            "http://antenna:8000/media/training/set.npz",
        )


class TestGenerateEmbeddingsJob(TestCase):
    """
    The job that fills in embeddings for verified crops, so a head can be retrained
    without running the backbone over the same image twice.
    """

    def setUp(self):
        self.project = Project.objects.create(name="Embedding Job Project")
        self.project.feature_flags.store_classification_embeddings = True
        self.project.save()
        self.user = User.objects.create_user(email="embedder@example.com", password="testpass123")
        self.images = [
            SourceImage.objects.create(path=f"ej{i}-2024010100{i:02d}00.jpg", project=self.project) for i in range(3)
        ]
        self.pipeline = Pipeline.objects.create(name="Embedding Job Pipeline")
        self.algorithms = {
            key: get_or_create_algorithm_and_category_map(val) for key, val in ALGORITHM_CHOICES.items()
        }
        self.classifier = self.algorithms["random-species-classifier"]
        self.classifier.trainable = True
        self.classifier.save()
        self.detector = self.algorithms["random-detector"]
        self.pipeline.algorithms.set([self.detector, self.classifier])
        self.taxon = Taxon.objects.create(name="Embeddicus testus", rank=TaxonRank.SPECIES.name)

    def _job(self, **params):
        from ami.jobs.models import GenerateEmbeddingsJob, Job

        return Job.objects.create(
            project=self.project,
            name="Generate embeddings",
            job_type_key=GenerateEmbeddingsJob.key,
            pipeline=self.pipeline,
            params=params or None,
        )

    def _detections_with_occurrences(self, verified: bool):
        for image in self.images:
            detection = Detection.objects.create(
                source_image=image, bbox=[0, 0, 10, 10], detection_algorithm=self.detector
            )
            occurrence = detection.associate_new_occurrence()
            if verified:
                Identification.objects.create(occurrence=occurrence, taxon=self.taxon, user=self.user)

    def test_it_refuses_when_the_project_would_discard_the_result(self):
        """Running the backbone to throw the vectors away is pure waste."""
        from ami.jobs.models import GenerateEmbeddingsJob

        self.project.feature_flags.store_classification_embeddings = False
        self.project.save()
        with self.assertRaises(ValueError) as ctx:
            GenerateEmbeddingsJob.run(self._job())
        self.assertIn("store_classification_embeddings", str(ctx.exception))

    def test_it_refuses_a_pipeline_with_no_trainable_algorithm(self):
        from ami.jobs.models import GenerateEmbeddingsJob

        self.classifier.trainable = False
        self.classifier.save()
        with self.assertRaises(ValueError) as ctx:
            GenerateEmbeddingsJob.run(self._job())
        self.assertIn("trainable", str(ctx.exception))

    def test_it_targets_the_trainable_algorithm(self):
        from ami.jobs.models import GenerateEmbeddingsJob

        self.assertEqual(GenerateEmbeddingsJob.target_algorithm(self._job()), self.classifier)

    def test_an_unknown_algorithm_key_is_rejected(self):
        from ami.jobs.models import GenerateEmbeddingsJob

        with self.assertRaises(ValueError):
            GenerateEmbeddingsJob.target_algorithm(self._job(algorithm_key="not-on-this-pipeline"))

    def test_only_verified_detections_are_collected(self):
        """Embedding everything would cost gigabytes; only a labelled crop can train a head."""
        from ami.jobs.models import GenerateEmbeddingsJob

        self._detections_with_occurrences(verified=False)
        job = self._job()
        self.assertEqual(GenerateEmbeddingsJob.images_needing_embeddings(job, self.classifier), [])

        self._detections_with_occurrences(verified=True)
        images = GenerateEmbeddingsJob.images_needing_embeddings(job, self.classifier)
        self.assertEqual(len(images), len(self.images))

    def test_detections_that_already_have_an_embedding_are_skipped(self):
        """The whole point is not to compute the same vector twice."""
        from ami.jobs.models import GenerateEmbeddingsJob

        self._detections_with_occurrences(verified=True)
        job = self._job()
        for detection in Detection.objects.filter(source_image__project=self.project):
            DetectionEmbedding.objects.create(
                detection=detection, algorithm=self.classifier, vector=[0.1] * EMBEDDING_DIMENSIONS
            )
        self.assertEqual(GenerateEmbeddingsJob.images_needing_embeddings(job, self.classifier), [])

    def test_nothing_to_do_finishes_successfully(self):
        from ami.jobs.models import GenerateEmbeddingsJob, JobState

        job = self._job()
        GenerateEmbeddingsJob.run(job)
        job.refresh_from_db()
        self.assertEqual(job.status, JobState.SUCCESS.name)


class TestAlgorithmVersioning(TestCase):
    """
    Every retrain produces a new algorithm version, so a prediction can always be traced
    back to the exact weights that made it.
    """

    def setUp(self):
        from ami.jobs.models import Job, TrainClassifierJob

        self.project = Project.objects.create(name="Versioning Project")
        self.parent = get_or_create_algorithm_and_category_map(ALGORITHM_CHOICES["random-species-classifier"])
        self.parent.trainable = True
        self.parent.save()
        self.job = Job.objects.create(
            project=self.project,
            name="Retrain",
            job_type_key=TrainClassifierJob.key,
            params={"algorithm_key": self.parent.key},
        )
        self.payload = {
            "result": {
                "labels": ["Alpha one", "Beta two", "Gamma three"],
                "rows": {"total": 30, "kept": 30, "train": 24, "test": 6},
                "candidate_metrics": {"top1": 0.9, "macro_recall": 0.88, "n": 6},
                "incumbent_metrics": {"top1": 0.7, "n": 6},
                "trained_at": "2026-09-03T21:08:03",
                "warnings": ["only 6 held-out rows"],
                "promote": True,
            },
            "dataset": {"rows": 30},
            "dataset_url": "/media/training/set-job-1.npz",
        }

    def _register(self):
        from ami.jobs.models import TrainClassifierJob

        return TrainClassifierJob.register_new_version(job=self.job, payload=self.payload)

    def test_a_retrain_creates_a_new_row_not_an_edit(self):
        """A Classification points at an Algorithm row, so a version must never change in place."""
        before = Algorithm.objects.count()
        new = self._register()
        assert new
        self.assertEqual(Algorithm.objects.count(), before + 1)
        self.assertNotEqual(new.pk, self.parent.pk)
        self.parent.refresh_from_db()
        self.assertEqual(self.parent.version, 1)

    def test_the_new_version_keeps_the_name_and_bumps_the_number(self):
        new = self._register()
        assert new
        self.assertEqual(new.name, self.parent.name)
        self.assertEqual(new.version, self.parent.version + 1)
        self.assertNotEqual(new.key, self.parent.key)

    def test_versions_keep_incrementing(self):
        first = self._register()
        second = self._register()
        assert first and second
        self.assertEqual(second.version, first.version + 1)

    def test_provenance_is_recorded(self):
        new = self._register()
        assert new
        info = new.training_info
        self.assertEqual(info.dataset_url, "/media/training/set-job-1.npz")
        self.assertEqual(info.dataset_classes, 3)
        self.assertEqual(info.dataset_rows, 30)
        self.assertEqual(info.metrics["top1"], 0.9)
        self.assertEqual(info.previous_metrics["top1"], 0.7)
        self.assertEqual(info.parent_algorithm_key, self.parent.key)
        self.assertEqual(info.job_id, self.job.pk)
        self.assertEqual(info.warnings, ["only 6 held-out rows"])

    def test_the_new_version_carries_its_own_class_list(self):
        """The retrained head predicts a different set of species than its parent."""
        new = self._register()
        assert new
        assert new.category_map
        self.assertEqual(new.category_map.labels, ["Alpha one", "Beta two", "Gamma three"])
        self.assertNotEqual(new.category_map_id, self.parent.category_map_id)

    def test_no_class_list_means_no_version(self):
        """Registering a head that cannot say what it predicts would be untraceable."""
        self.payload["result"]["labels"] = []
        self.assertIsNone(self._register())

    def test_an_unknown_parent_means_no_version(self):
        self.job.params = {"algorithm_key": "does-not-exist"}
        self.job.save()
        self.assertIsNone(self._register())


class TestAlgorithmTrainingConfig(TestCase):
    """Settings are seeded from the service once, then owned by Antenna."""

    def test_config_is_seeded_from_the_service(self):
        from ami.ml.schemas import AlgorithmTrainingConfig

        # A key nothing else registers, so this exercises the create path rather than
        # finding an algorithm some other fixture already made.
        config = ALGORITHM_CHOICES["random-species-classifier"].copy(
            update={
                # Unique name as well as key: Algorithm is unique on (name, version) too.
                "name": "Seeded Config Classifier",
                "key": "seeded-config-classifier",
                "training_config": AlgorithmTrainingConfig(head_type="mlp1", epochs=50),
            }
        )
        algorithm = get_or_create_algorithm_and_category_map(config)
        self.assertEqual(algorithm.training_config.head_type, "mlp1")
        self.assertEqual(algorithm.training_config.epochs, 50)

    def test_re_registering_does_not_overwrite_an_edited_config(self):
        """An admin who tunes these must not have them reset on the next /info read."""
        from ami.ml.schemas import AlgorithmTrainingConfig

        base = ALGORITHM_CHOICES["random-species-classifier"].copy(
            update={"name": "Edited Config Classifier", "key": "edited-config-classifier"}
        )
        algorithm = get_or_create_algorithm_and_category_map(base)
        algorithm.training_config = AlgorithmTrainingConfig(head_type="mlp1", epochs=999)
        algorithm.save()

        again = get_or_create_algorithm_and_category_map(
            base.copy(update={"training_config": AlgorithmTrainingConfig(epochs=300)})
        )
        self.assertEqual(again.training_config.epochs, 999)

    def test_defaults_exist_without_the_service_sending_any(self):
        algorithm = get_or_create_algorithm_and_category_map(ALGORITHM_CHOICES["random-detector"])
        self.assertEqual(algorithm.training_config.min_per_species, 2)
        self.assertEqual(algorithm.training_info.trained_at, None)


class TestTrainingSetMembership(TestCase):
    """
    Which occurrences a training run consumed, so an evaluation set can avoid them.
    """

    def setUp(self):
        from ami.jobs.models import Job, TrainClassifierJob

        self.project = Project.objects.create(name="Training Set Membership Project")
        self.user = User.objects.create_user(email="membership@example.com", password="testpass123")
        self.taxon = Taxon.objects.create(name="Memberus testus", rank=TaxonRank.SPECIES.name)
        self.images = [
            SourceImage.objects.create(path=f"tsm{i}-2024010100{i:02d}00.jpg", project=self.project) for i in range(4)
        ]
        self.occurrences = []
        for image in self.images:
            detection = Detection.objects.create(source_image=image, bbox=[0, 0, 10, 10])
            occurrence = detection.associate_new_occurrence()
            Identification.objects.create(occurrence=occurrence, taxon=self.taxon, user=self.user)
            self.occurrences.append(occurrence)

        self.job = Job.objects.create(project=self.project, name="Retrain", job_type_key=TrainClassifierJob.key)

    def test_recording_writes_one_row_per_occurrence(self):
        from ami.ml.models.training_set import TrainingSetMembership, record_training_set

        record_training_set([o.pk for o in self.occurrences], job=self.job)
        self.assertEqual(TrainingSetMembership.objects.filter(job=self.job).count(), len(self.occurrences))

    def test_recording_twice_does_not_duplicate(self):
        """A retried job must not double-count what it consumed."""
        from ami.ml.models.training_set import TrainingSetMembership, record_training_set

        ids = [o.pk for o in self.occurrences]
        record_training_set(ids, job=self.job)
        record_training_set(ids, job=self.job)
        self.assertEqual(TrainingSetMembership.objects.filter(job=self.job).count(), len(ids))

    def test_the_version_is_attached_after_training(self):
        """The version does not exist while the set is built, so it is linked afterwards."""
        from ami.ml.models.training_set import TrainingSetMembership, attach_algorithm, record_training_set

        algorithm = get_or_create_algorithm_and_category_map(ALGORITHM_CHOICES["random-species-classifier"])
        record_training_set([o.pk for o in self.occurrences], job=self.job)
        self.assertEqual(TrainingSetMembership.objects.filter(algorithm__isnull=True).count(), len(self.occurrences))

        linked = attach_algorithm(job=self.job, algorithm=algorithm)
        self.assertEqual(linked, len(self.occurrences))
        self.assertEqual(TrainingSetMembership.objects.filter(algorithm=algorithm).count(), len(self.occurrences))

    def test_used_occurrences_are_excluded_from_the_evaluation_pool(self):
        """Scoring a model on what it learned from reports a number that means nothing."""
        from ami.ml.models.training_set import occurrences_safe_to_evaluate_on, record_training_set

        pool = occurrences_safe_to_evaluate_on(self.project)
        self.assertEqual(pool.count(), len(self.occurrences))

        record_training_set([self.occurrences[0].pk, self.occurrences[1].pk], job=self.job)
        pool = occurrences_safe_to_evaluate_on(self.project)
        self.assertEqual(pool.count(), len(self.occurrences) - 2)
        self.assertNotIn(self.occurrences[0], pool)

    def test_an_unverified_occurrence_is_not_in_the_pool(self):
        from ami.ml.models.training_set import occurrences_safe_to_evaluate_on

        image = SourceImage.objects.create(path="tsm-extra-20240101010000.jpg", project=self.project)
        detection = Detection.objects.create(source_image=image, bbox=[0, 0, 10, 10])
        unverified = detection.associate_new_occurrence()

        self.assertNotIn(unverified, occurrences_safe_to_evaluate_on(self.project))


class TestTaxaListDecidesTheClassList(TestCase):
    """
    A project's taxa list sets which species a retrained head can predict. The verified
    crops only decide how well it predicts each one.
    """

    def setUp(self):
        self.project = Project.objects.create(name="Taxa List Training Project")
        self.project.feature_flags.store_classification_embeddings = True
        self.project.save()
        self.user = User.objects.create_user(email="taxalist@example.com", password="testpass123")

        self.algorithms = {
            key: get_or_create_algorithm_and_category_map(val) for key, val in ALGORITHM_CHOICES.items()
        }
        self.classifier = self.algorithms["random-species-classifier"]
        self.classifier.trainable = True
        self.classifier.save()
        self.pipeline = Pipeline.objects.create(name="Taxa List Pipeline")
        self.pipeline.algorithms.set([self.algorithms["random-detector"], self.classifier])

        self.verified_taxa = [
            Taxon.objects.create(name=f"Verifiedus {n}", rank=TaxonRank.SPECIES.name) for n in ("alpha", "beta")
        ]
        self.unverified_taxa = [
            Taxon.objects.create(name=f"Unverifiedus {n}", rank=TaxonRank.SPECIES.name) for n in ("gamma", "delta")
        ]

        # Twenty crops, split between the two verified species, each with an embedding.
        # The held-out split is a hash of the occurrence id, so a small set can land
        # entirely on one side and make the build refuse. Twenty makes that vanishingly rare.
        self.images = [
            SourceImage.objects.create(path=f"tl{i}-2024010100{i:02d}00.jpg", project=self.project) for i in range(20)
        ]
        for i, image in enumerate(self.images):
            detection = Detection.objects.create(source_image=image, bbox=[0, 0, 10, 10])
            occurrence = detection.associate_new_occurrence()
            Identification.objects.create(occurrence=occurrence, taxon=self.verified_taxa[i % 2], user=self.user)
            DetectionEmbedding.objects.create(
                detection=detection, algorithm=self.classifier, vector=[float(i)] * EMBEDDING_DIMENSIONS
            )

    def _taxa_list(self, taxa):
        taxa_list, _ = TaxaList.objects.get_or_create_for_project(name="Region list", project=self.project)
        taxa_list.taxa.set(taxa)
        return taxa_list

    def _build(self, **kwargs):
        from ami.ml.training_dataset import build_training_dataset

        return build_training_dataset(project=self.project, algorithm=self.classifier, test_fraction=0.5, **kwargs)

    def test_without_a_taxa_list_the_classes_come_from_what_was_verified(self):
        result = self._build(min_per_species=1)
        self.assertEqual(sorted(result["metadata"]["classes"]), sorted(t.name for t in self.verified_taxa))
        self.assertIsNone(result["metadata"]["taxa_list"])
        default_storage.delete(result["path"])

    def test_the_taxa_list_sets_the_classes(self):
        """This is what stops a head shrinking to whatever someone happened to verify."""
        taxa_list = self._taxa_list(self.verified_taxa + self.unverified_taxa)
        result = self._build(taxa_list=taxa_list, min_per_species=1)

        meta = result["metadata"]
        self.assertEqual(len(meta["classes"]), 4)
        self.assertEqual(meta["taxa_list"]["name"], taxa_list.name)
        default_storage.delete(result["path"])

    def test_species_in_the_list_with_no_crops_are_kept_and_reported(self):
        taxa_list = self._taxa_list(self.verified_taxa + self.unverified_taxa)
        result = self._build(taxa_list=taxa_list, min_per_species=1)

        meta = result["metadata"]
        self.assertEqual(sorted(meta["classes_without_verified_data"]), sorted(t.name for t in self.unverified_taxa))
        for taxon in self.unverified_taxa:
            self.assertEqual(meta["counts"][taxon.name], 0)
        default_storage.delete(result["path"])

    def test_verified_species_outside_the_list_are_dropped_and_reported(self):
        taxa_list = self._taxa_list([self.verified_taxa[0]] + self.unverified_taxa)
        result = self._build(taxa_list=taxa_list, min_per_species=1)

        meta = result["metadata"]
        self.assertIn(self.verified_taxa[1].name, meta["dropped_species"])
        self.assertNotIn(self.verified_taxa[1].name, meta["classes"])
        default_storage.delete(result["path"])

    def test_the_project_default_is_used_when_none_is_passed(self):
        taxa_list = self._taxa_list(self.verified_taxa + self.unverified_taxa)
        self.project.default_taxa_list = taxa_list
        self.project.save()

        result = self._build(min_per_species=1)
        self.assertEqual(len(result["metadata"]["classes"]), 4)
        default_storage.delete(result["path"])

    def test_an_empty_taxa_list_is_refused(self):
        from ami.ml.training_dataset import NotEnoughVerifiedData

        with self.assertRaises(NotEnoughVerifiedData):
            self._build(taxa_list=self._taxa_list([]), min_per_species=1)

    def test_the_job_prefers_its_own_taxa_list_over_the_project_default(self):
        from ami.jobs.models import Job, TrainClassifierJob

        project_default = self._taxa_list(self.verified_taxa)
        self.project.default_taxa_list = project_default
        self.project.save()

        chosen, _ = TaxaList.objects.get_or_create_for_project(name="Chosen list", project=self.project)
        chosen.taxa.set(self.unverified_taxa)

        job = Job.objects.create(
            project=self.project,
            name="Retrain",
            job_type_key=TrainClassifierJob.key,
            params={"algorithm_key": self.classifier.key, "taxa_list_id": chosen.pk},
        )
        self.assertEqual(TrainClassifierJob.target_taxa_list(job), chosen)

    def test_an_unknown_taxa_list_id_is_refused(self):
        from ami.jobs.models import Job, TrainClassifierJob

        job = Job.objects.create(
            project=self.project,
            name="Retrain",
            job_type_key=TrainClassifierJob.key,
            params={"algorithm_key": self.classifier.key, "taxa_list_id": 999999},
        )
        with self.assertRaises(ValueError):
            TrainClassifierJob.target_taxa_list(job)


class TestTrainingCallback(APITestCase):
    """
    Training can outlast the request that started it, so the service reports back to a
    callback instead of holding the connection open.
    """

    def setUp(self):
        from ami.jobs.models import Job, TrainClassifierJob

        self.project = Project.objects.create(name="Callback Project")
        self.algorithm = get_or_create_algorithm_and_category_map(ALGORITHM_CHOICES["random-species-classifier"])
        self.algorithm.trainable = True
        self.algorithm.save()
        self.job = Job.objects.create(
            project=self.project,
            name="Retrain",
            job_type_key=TrainClassifierJob.key,
            params={"algorithm_key": self.algorithm.key, "media_base_url": "http://antenna:8000"},
        )
        self.url = f"/api/v2/jobs/{self.job.pk}/training-result/"
        self.payload = {
            "result": {
                "labels": ["Alpha one", "Beta two"],
                "rows": {"total": 10, "kept": 10, "train": 8, "test": 2},
                "candidate_metrics": {"top1": 0.9, "n": 2},
                "incumbent_metrics": {"top1": 0.5, "n": 2},
                "trained_at": "2026-09-13T15:00:00",
                "warnings": [],
                "promote": True,
            },
            "dataset": {"rows": 10},
            "dataset_url": "/media/training/x.npz",
        }

    def _token(self):
        from ami.ml.training_dispatch import make_callback_token

        return make_callback_token(self.job)

    def _post(self, token=None):
        headers = {"HTTP_AUTHORIZATION": f"Token {token}"} if token else {}
        return self.client.post(self.url, self.payload, format="json", **headers)

    def test_a_valid_token_records_the_result(self):
        from ami.jobs.models import JobState

        response = self._post(self._token())
        self.assertEqual(response.status_code, 200)
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, JobState.SUCCESS.name)
        self.assertEqual(self.job.result["result"]["candidate_metrics"]["top1"], 0.9)

    def test_no_token_is_refused(self):
        """The service has no Antenna account, so the token is the only thing authorising it."""
        self.assertEqual(self._post().status_code, 403)

    def test_a_forged_token_is_refused(self):
        self.assertEqual(self._post("not-a-real-token").status_code, 403)

    def test_another_jobs_token_is_refused(self):
        from ami.jobs.models import Job, TrainClassifierJob
        from ami.ml.training_dispatch import make_callback_token

        other = Job.objects.create(project=self.project, name="Other", job_type_key=TrainClassifierJob.key)
        self.assertEqual(self._post(make_callback_token(other)).status_code, 403)

    def test_a_second_result_does_not_overwrite_the_first(self):
        """A retry or a late answer must not undo what already landed."""
        self._post(self._token())
        self.payload["result"]["candidate_metrics"]["top1"] = 0.1
        response = self._post(self._token())

        self.assertEqual(response.status_code, 200)
        self.job.refresh_from_db()
        self.assertEqual(self.job.result["result"]["candidate_metrics"]["top1"], 0.9)

    def test_a_result_for_a_non_training_job_is_refused(self):
        from ami.jobs.models import Job, MLJob
        from ami.ml.training_dispatch import make_callback_token

        other = Job.objects.create(project=self.project, name="ML", job_type_key=MLJob.key)
        response = self.client.post(
            f"/api/v2/jobs/{other.pk}/training-result/",
            self.payload,
            format="json",
            headers={"authorization": f"Token {make_callback_token(other)}"},
        )
        self.assertEqual(response.status_code, 400)

    def test_the_callback_url_points_at_this_job(self):
        from ami.ml.training_dispatch import callback_url_for

        self.assertEqual(callback_url_for(self.job), f"http://antenna:8000/api/v2/jobs/{self.job.pk}/training-result/")


class TestTrainingDataPermissions(APITestCase):
    """
    Verified labels are project data, so reading them needs membership of that project,
    not merely an account.
    """

    def setUp(self):
        self.project = Project.objects.create(name="Permissions Project")
        self.member = User.objects.create_user(email="member@example.com", password="testpass123")
        self.outsider = User.objects.create_user(email="outsider@example.com", password="testpass123")
        self.superuser = User.objects.create_superuser(email="super@example.com", password="testpass123")
        self.project.members.add(self.member)

        self.algorithm = get_or_create_algorithm_and_category_map(ALGORITHM_CHOICES["random-species-classifier"])
        self.url = reverse_with_params("api:training-data-list")
        self.params = {"project_id": self.project.pk, "algorithm": self.algorithm.key}

    def _status_for(self, user):
        self.client.force_authenticate(user=user)
        return self.client.get(self.url, self.params).status_code

    def test_a_member_can_read_the_training_data(self):
        self.assertEqual(self._status_for(self.member), 200)

    def test_a_superuser_can_read_the_training_data(self):
        self.assertEqual(self._status_for(self.superuser), 200)

    def test_anonymous_cannot(self):
        self.client.force_authenticate(user=None)
        self.assertIn(self.client.get(self.url, self.params).status_code, (401, 403))

    def test_an_outsider_can_read_a_public_project(self):
        """Antenna publishes non-draft projects, and these labels are that project's data."""
        self.assertEqual(self._status_for(self.outsider), 200)

    def test_an_outsider_cannot_read_a_draft_project(self):
        """A draft project is private, so its verified labels are too."""
        self.project.draft = True
        self.project.save()
        self.assertEqual(self._status_for(self.outsider), 403)

    def test_a_member_can_still_read_their_draft_project(self):
        self.project.draft = True
        self.project.save()
        self.assertEqual(self._status_for(self.member), 200)


class TestTrainingConfigIsUsed(TestCase):
    """
    Settings published by the service and stored on the algorithm actually drive a run.
    """

    def setUp(self):
        from ami.jobs.models import Job, TrainClassifierJob
        from ami.ml.schemas import AlgorithmTrainingConfig

        self.project = Project.objects.create(name="Config Project")
        self.algorithm = get_or_create_algorithm_and_category_map(ALGORITHM_CHOICES["random-species-classifier"])
        self.algorithm.trainable = True
        self.algorithm.training_config = AlgorithmTrainingConfig(
            min_per_species=7, test_fraction=0.4, split_salt="from-config", head_type="mlp1", epochs=42
        )
        self.algorithm.save()
        self.job = Job.objects.create(
            project=self.project,
            name="Retrain",
            job_type_key=TrainClassifierJob.key,
            params={"algorithm_key": self.algorithm.key},
        )

    def _payload(self):
        from ami.ml.training_dispatch import send_training_request

        captured = {}

        class FakeResponse:
            ok = True

            def json(self):
                return {"labels": []}

        def fake_post(url, json=None, timeout=None):
            captured.update(json)
            return FakeResponse()

        with unittest.mock.patch("ami.ml.training_dispatch.create_session") as session:
            session.return_value.post = fake_post
            send_training_request(
                job=self.job,
                service=unittest.mock.Mock(endpoint_url="http://service:2000", name="svc"),
                algorithm=self.algorithm,
                dataset={"url": "/media/training/x.npz"},
            )
        return captured

    def test_the_fitting_settings_reach_the_service(self):
        payload = self._payload()
        self.assertEqual(payload["head_type"], "mlp1")
        self.assertEqual(payload["epochs"], 42)
        self.assertEqual(payload["min_per_species"], 7)

    def test_a_job_can_override_the_config_for_one_run(self):
        self.job.params = {**self.job.params, "epochs": 5, "head_type": "linear"}
        self.job.save()

        payload = self._payload()
        self.assertEqual(payload["epochs"], 5)
        self.assertEqual(payload["head_type"], "linear")
        # Not overridden, so it still comes from the config.
        self.assertEqual(payload["min_per_species"], 7)


class TestTrainingResultIsRecordedOnce(TestCase):
    """
    A service posts its callback before returning from /train, so a fast run reports twice.
    Only the first report may count, or each retrain registers two algorithm versions.
    """

    def setUp(self):
        from ami.jobs.models import Job, TrainClassifierJob

        self.project = Project.objects.create(name="Duplicate Result Project")
        self.parent = get_or_create_algorithm_and_category_map(ALGORITHM_CHOICES["random-species-classifier"])
        self.parent.trainable = True
        self.parent.save()
        self.job = Job.objects.create(
            project=self.project,
            name="Retrain",
            job_type_key=TrainClassifierJob.key,
            params={"algorithm_key": self.parent.key},
        )
        self.payload = {
            "result": {
                "labels": ["Alpha one", "Beta two"],
                "rows": {"total": 10, "kept": 10, "train": 8, "test": 2},
                "candidate_metrics": {"top1": 0.9, "n": 2},
                "incumbent_metrics": {"top1": 0.5, "n": 2},
                "trained_at": "2026-09-13T19:00:00",
                "warnings": [],
                "promote": True,
            },
            "dataset": {"rows": 10},
            "dataset_url": "/media/training/x.npz",
        }

    def test_reporting_twice_registers_one_version(self):
        from ami.jobs.models import TrainClassifierJob

        before = Algorithm.objects.filter(name=self.parent.name).count()
        TrainClassifierJob.record_result(job=self.job, payload=self.payload)
        TrainClassifierJob.record_result(job=self.job, payload=self.payload)

        self.assertEqual(Algorithm.objects.filter(name=self.parent.name).count(), before + 1)

    def test_a_stale_copy_of_the_job_cannot_report_again(self):
        """The inline caller holds a copy from before the callback landed."""
        from ami.jobs.models import Job, TrainClassifierJob

        stale = Job.objects.get(pk=self.job.pk)
        TrainClassifierJob.record_result(job=self.job, payload=self.payload)

        before = Algorithm.objects.filter(name=self.parent.name).count()
        TrainClassifierJob.record_result(job=stale, payload=self.payload)
        self.assertEqual(Algorithm.objects.filter(name=self.parent.name).count(), before)

    def test_the_first_result_is_the_one_kept(self):
        from ami.jobs.models import TrainClassifierJob

        TrainClassifierJob.record_result(job=self.job, payload=self.payload)
        second = {**self.payload, "result": {**self.payload["result"], "candidate_metrics": {"top1": 0.1}}}
        TrainClassifierJob.record_result(job=self.job, payload=second)

        self.job.refresh_from_db()
        self.assertEqual(self.job.result["result"]["candidate_metrics"]["top1"], 0.9)


class TestOccurrenceSetAPI(APITestCase):
    """
    The endpoint the evaluation-set picker reads.

    A set is either one project's or global, so what this returns decides which sets a
    person can score a model against.
    """

    def setUp(self):
        self.project = Project.objects.create(name="Set Project")
        self.other_project = Project.objects.create(name="Someone Else's Project")
        self.user = User.objects.create_user(email="sets@example.com", password="testpass123")
        self.project.members.add(self.user)

        self.own = OccurrenceSet.objects.create(name="This project's blind set")
        self.own.projects.add(self.project)
        self.global_set = OccurrenceSet.objects.create(name="Platform-wide blind set")
        self.theirs = OccurrenceSet.objects.create(name="Another project's blind set")
        self.theirs.projects.add(self.other_project)

        self.url = reverse_with_params("api:occurrenceset-list")

    def _names(self, response):
        return sorted(item["name"] for item in response.json()["results"])

    def test_a_project_sees_its_own_sets_and_the_global_ones(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.url, {"project_id": self.project.pk})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._names(response), sorted([self.own.name, self.global_set.name]))

    def test_another_project_s_set_is_not_offered(self):
        """Scoring against a set from another project would compare models on data
        this project cannot see."""
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.url, {"project_id": self.project.pk})

        self.assertNotIn(self.theirs.name, self._names(response))

    def test_listing_without_a_project_is_refused(self):
        """Without a project the queryset has nothing to scope to, so it would return
        every set on the platform."""
        self.client.force_authenticate(user=self.user)

        self.assertEqual(self.client.get(self.url).status_code, 400)

    def test_the_sets_are_read_only(self):
        """Membership is built deliberately: two models can only be compared if they were
        scored on exactly the same occurrences."""
        self.client.force_authenticate(user=self.user)
        response = self.client.post(self.url, {"name": "Made up in passing"}, format="json")

        # 405 if the method is refused first, 403 if the permission check gets there
        # first. Either way the endpoint will not create one.
        self.assertIn(response.status_code, (403, 405))

    def test_a_draft_project_s_sets_are_hidden_from_outsiders(self):
        """A draft project is not published, so neither is what it scores models on."""
        draft = Project.objects.create(name="Unpublished Project", draft=True)
        secret = OccurrenceSet.objects.create(name="Draft project's set")
        secret.projects.add(draft)

        self.client.force_authenticate(user=None)
        response = self.client.get(self.url, {"project_id": draft.pk})

        self.assertNotIn(secret.name, self._names(response))

    def test_a_global_set_is_offered_to_anonymous_readers_too(self):
        """Global means every project, and Antenna publishes non-draft projects."""
        self.client.force_authenticate(user=None)
        response = self.client.get(self.url, {"project_id": self.project.pk})

        self.assertIn(self.global_set.name, self._names(response))


class TestAlgorithmEvaluation(TestCase):
    """
    Scoring an algorithm against a fixed set of verified occurrences, so two models can be
    compared on identical data.
    """

    def setUp(self):
        self.project = Project.objects.create(name="Evaluation Project")
        self.user = User.objects.create_user(email="evaluator@example.com", password="testpass123")
        self.taxa = [Taxon.objects.create(name=f"Evaluus {n}", rank=TaxonRank.SPECIES.name) for n in ("alpha", "beta")]
        self.outsider_taxon = Taxon.objects.create(name="Outsideus ignotus", rank=TaxonRank.SPECIES.name)

        self.algorithm = get_or_create_algorithm_and_category_map(ALGORITHM_CHOICES["random-species-classifier"])
        self.category_map = AlgorithmCategoryMap.objects.create(
            labels=[t.name for t in self.taxa],
            data=[{"index": i, "label": t.name} for i, t in enumerate(self.taxa)],
            version="eval-test",
        )
        self.algorithm.category_map = self.category_map
        self.algorithm.save()

        self.occurrence_set = OccurrenceSet.objects.create(name="Blind set")
        self.occurrence_set.projects.add(self.project)

    def _occurrence(self, truth, predicted=None, index=0):
        """One verified occurrence, optionally with a prediction from the algorithm."""
        image = SourceImage.objects.create(
            path=f"ev{index}-{truth.pk}-2024010100{index:02d}00.jpg", project=self.project
        )
        detection = Detection.objects.create(source_image=image, bbox=[0, 0, 10, 10])
        occurrence = detection.associate_new_occurrence()
        Identification.objects.create(occurrence=occurrence, taxon=truth, user=self.user)
        if predicted:
            Classification.objects.create(
                detection=detection,
                taxon=predicted,
                algorithm=self.algorithm,
                score=0.9,
                timestamp=datetime.datetime.now(),
                category_map=self.category_map,
            )
        self.occurrence_set.occurrences.add(occurrence)
        return occurrence

    def test_a_perfect_run_scores_one(self):
        from ami.ml import evaluation

        for i, taxon in enumerate(self.taxa):
            self._occurrence(truth=taxon, predicted=taxon, index=i)

        result = evaluation.score(self.occurrence_set, self.algorithm)
        self.assertEqual(result["micro_accuracy"], 1.0)
        self.assertEqual(result["occurrences_scored"], 2)

    def test_a_wrong_prediction_lowers_the_score(self):
        from ami.ml import evaluation

        self._occurrence(truth=self.taxa[0], predicted=self.taxa[0], index=0)
        self._occurrence(truth=self.taxa[1], predicted=self.taxa[0], index=1)

        result = evaluation.score(self.occurrence_set, self.algorithm)
        self.assertEqual(result["micro_accuracy"], 0.5)

    def test_species_the_algorithm_cannot_predict_are_left_out(self):
        """Counting those wrong would punish a regional head for a question nobody asked it."""
        from ami.ml import evaluation

        self._occurrence(truth=self.taxa[0], predicted=self.taxa[0], index=0)
        self._occurrence(truth=self.outsider_taxon, predicted=self.taxa[0], index=1)

        result = evaluation.score(self.occurrence_set, self.algorithm)
        self.assertEqual(result["occurrences_scored"], 1)
        self.assertEqual(result["occurrences_skipped"], 1)
        self.assertEqual(result["micro_accuracy"], 1.0)

    def test_the_per_species_average_differs_from_the_plain_share(self):
        """Long-tailed data: one common species must not hide failure on a rare one."""
        from ami.ml import evaluation

        for i in range(4):
            self._occurrence(truth=self.taxa[0], predicted=self.taxa[0], index=i)
        self._occurrence(truth=self.taxa[1], predicted=self.taxa[0], index=9)

        result = evaluation.score(self.occurrence_set, self.algorithm)
        self.assertEqual(result["micro_accuracy"], 0.8)
        self.assertEqual(result["macro_accuracy"], 0.5)

    def test_an_algorithm_that_never_ran_says_so(self):
        """A missing step should read as a missing step, not an accuracy of zero."""
        from ami.ml import evaluation

        self._occurrence(truth=self.taxa[0], predicted=None, index=0)
        with self.assertRaises(evaluation.NothingToScore):
            evaluation.score(self.occurrence_set, self.algorithm)

    def test_results_are_stored_per_species(self):
        from ami.ml import evaluation

        self._occurrence(truth=self.taxa[0], predicted=self.taxa[0], index=0)
        self._occurrence(truth=self.taxa[1], predicted=self.taxa[0], index=1)

        result = evaluation.score(self.occurrence_set, self.algorithm)
        stored = evaluation.save_evaluation(self.occurrence_set, self.algorithm, result)

        self.assertEqual(stored.micro_accuracy, 0.5)
        self.assertEqual(stored.taxa.count(), 2)
        self.assertEqual(stored.taxa.get(taxon=self.taxa[0]).accuracy, 1.0)
        self.assertEqual(stored.taxa.get(taxon=self.taxa[1]).accuracy, 0.0)

    def test_scoring_again_replaces_the_earlier_result(self):
        """A second run over the same set is a correction, not a new fact."""
        from ami.ml import evaluation

        self._occurrence(truth=self.taxa[0], predicted=self.taxa[0], index=0)
        result = evaluation.score(self.occurrence_set, self.algorithm)
        evaluation.save_evaluation(self.occurrence_set, self.algorithm, result)
        evaluation.save_evaluation(self.occurrence_set, self.algorithm, result)

        self.assertEqual(
            AlgorithmEvaluation.objects.filter(algorithm=self.algorithm, occurrence_set=self.occurrence_set).count(),
            1,
        )

    def test_a_set_with_no_project_is_global(self):
        """One set can compare models across projects."""
        shared = OccurrenceSet.objects.create(name="Shared across projects")
        self.assertTrue(shared.is_global)
        self.assertFalse(self.occurrence_set.is_global)
        self.assertIn(shared, OccurrenceSet.objects.for_project(self.project))


class TestPerformanceReporting(TestCase):
    """
    The numbers the model-performance screens read: the best model for a taxa list, and how
    each algorithm has done on one species.
    """

    def setUp(self):
        self.project = Project.objects.create(name="Reporting Project")
        self.user = User.objects.create_user(email="reporter@example.com", password="testpass123")
        self.common = Taxon.objects.create(name="Reportus communis", rank=TaxonRank.SPECIES.name)
        self.rare = Taxon.objects.create(name="Reportus rarus", rank=TaxonRank.SPECIES.name)
        self.taxa_list = TaxaList.objects.create(name="Reporting list")
        self.taxa_list.taxa.set([self.common, self.rare])
        self.taxa_list.projects.add(self.project)
        self.occurrence_set = OccurrenceSet.objects.create(name="Reporting set")

    def _algorithm(self, key: str) -> Algorithm:
        return Algorithm.objects.create(name=key, key=key)

    def _evaluation(self, algorithm: Algorithm, micro: float, macro: float, per_taxon: dict) -> AlgorithmEvaluation:
        evaluation = AlgorithmEvaluation.objects.create(
            algorithm=algorithm,
            occurrence_set=self.occurrence_set,
            micro_accuracy=micro,
            macro_accuracy=macro,
            occurrences_scored=sum(scored for _, scored in per_taxon.values()),
            species_scored=len(per_taxon),
        )
        for taxon, (correct, scored) in per_taxon.items():
            TaxonEvaluation.objects.create(
                evaluation=evaluation,
                taxon=taxon,
                accuracy=correct / scored,
                occurrences_scored=scored,
                correct=correct,
            )
        return evaluation

    def test_the_best_model_is_the_one_that_handles_the_rare_species(self):
        """Ranked on the per-species average, or a model that only knows the common one wins."""
        from ami.ml import reporting

        self._evaluation(self._algorithm("common-only"), micro=0.9, macro=0.5, per_taxon={self.common: (9, 10)})
        even = self._evaluation(
            self._algorithm("handles-both"),
            micro=0.8,
            macro=0.8,
            per_taxon={self.common: (8, 10), self.rare: (8, 10)},
        )

        self.assertEqual(reporting.best_evaluation_for_taxa_list(self.taxa_list), even)

    def test_a_list_nothing_has_been_scored_on_has_no_best_model(self):
        from ami.ml import reporting

        self.assertIsNone(reporting.best_evaluation_for_taxa_list(self.taxa_list))

    def test_a_species_lists_every_algorithm_scored_on_it(self):
        from ami.ml import reporting

        self._evaluation(self._algorithm("first"), micro=1.0, macro=1.0, per_taxon={self.rare: (2, 2)})
        self._evaluation(self._algorithm("second"), micro=0.5, macro=0.5, per_taxon={self.rare: (1, 2)})

        rows = reporting.performance_for_taxon(self.rare)
        self.assertEqual([row["algorithm"]["key"] for row in rows], ["first", "second"])
        self.assertEqual([row["accuracy"] for row in rows], [1.0, 0.5])
        self.assertEqual(rows[0]["occurrence_set"]["name"], self.occurrence_set.name)

    def test_a_species_nothing_has_been_scored_on_lists_nothing(self):
        from ami.ml import reporting

        self.assertEqual(reporting.performance_for_taxon(self.common), [])

    def test_an_algorithm_lists_its_own_scores(self):
        from ami.ml import reporting

        algorithm = self._algorithm("scored-twice")
        self._evaluation(algorithm, micro=1.0, macro=1.0, per_taxon={self.common: (2, 2)})
        other_set = OccurrenceSet.objects.create(name="Second set")
        AlgorithmEvaluation.objects.create(
            algorithm=algorithm,
            occurrence_set=other_set,
            micro_accuracy=0.5,
            macro_accuracy=0.5,
            occurrences_scored=2,
            species_scored=1,
        )

        rows = reporting.latest_evaluations(algorithm)
        self.assertEqual({row["occurrence_set"]["name"] for row in rows}, {"Reporting set", "Second set"})
        self.assertEqual(len(reporting.latest_evaluations(algorithm, limit=1)), 1)

    def test_the_algorithms_list_does_not_query_per_row(self):
        """Evaluations are prefetched: adding scored algorithms must not add queries."""
        from django.core.cache import caches
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        from ami.ml.models import Pipeline, ProcessingService, ProjectPipelineConfig

        service = ProcessingService.objects.create(name="Reporting service", endpoint_url="http://example.com")
        service.projects.add(self.project)
        pipeline = Pipeline.objects.create(name="Reporting pipeline", slug="reporting-pipeline")
        pipeline.projects.add(self.project)
        ProjectPipelineConfig.objects.update_or_create(
            project=self.project, pipeline=pipeline, defaults={"enabled": True}
        )

        self.client.force_login(self.user)
        url = f"/api/v2/ml/algorithms/?project_id={self.project.pk}"

        def query_count() -> int:
            # Cold cache on both runs, or a warm one hides the scaling.
            caches["default"].clear()
            with CaptureQueriesContext(connection) as ctx:
                res = self.client.get(url)
            self.assertEqual(res.status_code, 200)
            return len(ctx.captured_queries)

        for index in range(2):
            algorithm = self._algorithm(f"listed-{index}")
            pipeline.algorithms.add(algorithm)
            self._evaluation(algorithm, micro=1.0, macro=1.0, per_taxon={self.common: (1, 1)})
        two_algorithms = query_count()

        for index in range(2, 6):
            algorithm = self._algorithm(f"listed-{index}")
            pipeline.algorithms.add(algorithm)
            self._evaluation(algorithm, micro=1.0, macro=1.0, per_taxon={self.common: (1, 1)})
        six_algorithms = query_count()

        self.assertLessEqual(six_algorithms, two_algorithms)
