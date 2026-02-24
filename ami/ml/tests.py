import datetime
import pathlib
import unittest
import uuid

from django.test import TestCase
from rest_framework.test import APIRequestFactory, APITestCase

from ami.base.serializers import reverse_with_params
from ami.main.models import (
    Classification,
    Detection,
    Project,
    SourceImage,
    SourceImageCollection,
    Taxon,
    group_images_into_events,
)
from ami.ml.models import Algorithm, Pipeline, ProcessingService
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
        processing_services_create_url = reverse_with_params("api:processingservice-list")
        self.client.force_authenticate(user=self.user)
        processing_service_data = {
            "project": self.project.pk,
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
        processing_services_create_url = reverse_with_params("api:processingservice-list")
        self.client.force_authenticate(user=self.user)
        processing_service_data = {
            "project": self.project.pk,
            "name": "Pull Mode Service",
            "description": "Service without endpoint",
        }
        resp = self.client.post(processing_services_create_url, processing_service_data)
        self.client.force_authenticate(user=None)

        self.assertEqual(resp.status_code, 201)
        data = resp.json()

        # Check that endpoint_url is null
        self.assertIsNone(data["instance"]["endpoint_url"])

        # Check that status indicates no endpoint configured
        self.assertFalse(data["status"]["request_successful"])
        self.assertIn("No endpoint URL configured", data["status"]["error"])
        self.assertIsNone(data["status"]["endpoint_url"])

    def test_get_status_with_null_endpoint_url(self):
        """Test get_status method when endpoint_url is None"""
        service = ProcessingService.objects.create(name="Pull Mode Service", endpoint_url=None)
        service.projects.add(self.project)

        status = service.get_status()

        self.assertFalse(status.request_successful)
        self.assertIsNone(status.server_live)
        self.assertIsNone(status.endpoint_url)
        self.assertIsNotNone(status.error)
        self.assertIn("No endpoint URL configured", (status.error or ""))
        self.assertEqual(status.pipelines_online, [])

    def test_get_pipeline_configs_with_null_endpoint_url(self):
        """Test get_pipeline_configs method when endpoint_url is None"""
        service = ProcessingService.objects.create(name="Pull Mode Service", endpoint_url=None)

        configs = service.get_pipeline_configs()

        self.assertEqual(configs, [])


class TestPipelineWithProcessingService(TestCase):
    def test_run_pipeline_with_errors_from_processing_service(self):
        """
        Run a real pipeline and verify that if an error occurs for one image, the error is logged in job.logs.stderr.
        """
        from ami.jobs.models import Job

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
        stderr_logs = job.logs.stderr
        # Check that an error message mentioning the failed image is present
        assert any(
            "Failed to process" in log for log in stderr_logs
        ), f"Expected error message in job.logs.stderr, got: {stderr_logs}"

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
    def setUp(self):
        # Create test project, deployment, and default setup
        self.project, self.deployment = setup_test_project()
        create_taxa(project=self.project)
        self._create_images_with_dimensions(deployment=self.deployment)
        group_images_into_events(deployment=self.deployment)

        # Create a simple SourceImageCollection for testing
        self.collection = SourceImageCollection.objects.create(
            name="Test PostProcessing Collection",
            project=self.project,
            method="manual",
            kwargs={"image_ids": list(self.deployment.captures.values_list("pk", flat=True))},
        )
        self.collection.populate_sample()

    def _create_images_with_dimensions(
        self,
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
        progress = self.manager._commit_update(set(), "process")
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
            progress = self.manager._commit_update(set(), stage)
            assert progress is not None
            self.assertEqual(progress.total, len(self.image_ids))
            self.assertEqual(progress.failed, 0)

    def test_progress_tracking(self):
        """Test progress updates correctly as images are processed."""
        self._init_and_verify(self.image_ids)

        # Process 2 images
        progress = self.manager._commit_update({"img1", "img2"}, "process")
        assert progress is not None
        self.assertEqual(progress.remaining, 3)
        self.assertEqual(progress.processed, 2)
        self.assertEqual(progress.percentage, 0.4)

        # Process 2 more images
        progress = self.manager._commit_update({"img3", "img4"}, "process")
        assert progress is not None
        self.assertEqual(progress.remaining, 1)
        self.assertEqual(progress.processed, 4)
        self.assertEqual(progress.percentage, 0.8)

        # Process last image
        progress = self.manager._commit_update({"img5"}, "process")
        assert progress is not None
        self.assertEqual(progress.remaining, 0)
        self.assertEqual(progress.processed, 5)
        self.assertEqual(progress.percentage, 1.0)

    def test_update_state_with_locking(self):
        """Test update_state acquires lock, updates progress, and releases lock."""
        from django.core.cache import cache

        self._init_and_verify(self.image_ids)

        # First update should succeed
        progress = self.manager.update_state({"img1", "img2"}, "process", "task1")
        assert progress is not None
        self.assertEqual(progress.processed, 2)

        # Simulate concurrent update by holding the lock
        lock_key = f"job:{self.job_id}:process_results_lock"
        cache.set(lock_key, "other_task", timeout=60)

        # Update should fail (lock held by another task)
        progress = self.manager.update_state({"img3"}, "process", "task1")
        self.assertIsNone(progress)

        # Release the lock and retry
        cache.delete(lock_key)
        progress = self.manager.update_state({"img3"}, "process", "task1")
        assert progress is not None
        self.assertEqual(progress.processed, 3)

    def test_stages_independent(self):
        """Test that different stages track progress independently."""
        self._init_and_verify(self.image_ids)

        # Update process stage
        self.manager._commit_update({"img1", "img2"}, "process")
        progress_process = self.manager._commit_update(set(), "process")
        assert progress_process is not None
        self.assertEqual(progress_process.remaining, 3)

        # Results stage should still have all images pending
        progress_results = self.manager._commit_update(set(), "results")
        assert progress_results is not None
        self.assertEqual(progress_results.remaining, 5)

    def test_empty_job(self):
        """Test handling of job with no images."""
        self.manager.initialize_job([])
        progress = self.manager._commit_update(set(), "process")
        assert progress is not None
        self.assertEqual(progress.total, 0)
        self.assertEqual(progress.percentage, 1.0)  # Empty job is 100% complete

    def test_cleanup(self):
        """Test cleanup removes all tracking keys."""
        self._init_and_verify(self.image_ids)

        # Verify keys exist
        progress = self.manager._commit_update(set(), "process")
        self.assertIsNotNone(progress)

        # Cleanup
        self.manager.cleanup()

        # Verify keys are gone
        progress = self.manager._commit_update(set(), "process")
        self.assertIsNone(progress)

    def test_failed_image_tracking(self):
        """Test basic failed image tracking with no double-counting on retries."""
        self._init_and_verify(self.image_ids)

        # Mark 2 images as failed in process stage
        progress = self.manager._commit_update({"img1", "img2"}, "process", failed_image_ids={"img1", "img2"})
        assert progress is not None
        self.assertEqual(progress.failed, 2)

        # Retry same 2 images (fail again) - should not double-count
        progress = self.manager._commit_update(set(), "process", failed_image_ids={"img1", "img2"})
        assert progress is not None
        self.assertEqual(progress.failed, 2)

        # Fail a different image
        progress = self.manager._commit_update(set(), "process", failed_image_ids={"img3"})
        assert progress is not None
        self.assertEqual(progress.failed, 3)

    def test_failed_and_processed_mixed(self):
        """Test mixed successful and failed processing in same batch."""
        self._init_and_verify(self.image_ids)

        # Process 2 successfully, 2 fail, 1 remains pending
        progress = self.manager._commit_update(
            {"img1", "img2", "img3", "img4"}, "process", failed_image_ids={"img3", "img4"}
        )
        assert progress is not None
        self.assertEqual(progress.processed, 4)
        self.assertEqual(progress.failed, 2)
        self.assertEqual(progress.remaining, 1)
        self.assertEqual(progress.percentage, 0.8)

    def test_cleanup_removes_failed_set(self):
        """Test that cleanup removes failed image set."""
        from django.core.cache import cache

        self._init_and_verify(self.image_ids)

        # Add failed images
        self.manager._commit_update({"img1", "img2"}, "process", failed_image_ids={"img1", "img2"})

        # Verify failed set exists
        failed_set = cache.get(self.manager._failed_key)
        self.assertEqual(len(failed_set), 2)

        # Cleanup
        self.manager.cleanup()

        # Verify failed set is gone
        failed_set = cache.get(self.manager._failed_key)
        self.assertIsNone(failed_set)
