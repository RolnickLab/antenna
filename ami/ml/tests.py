import datetime

from django.test import TestCase
from rest_framework.test import APIRequestFactory, APITestCase
from rich import print

from ami.base.serializers import reverse_with_params
from ami.main.models import Classification, Detection, Project, SourceImage, SourceImageCollection
from ami.ml.models import Algorithm, Pipeline, ProcessingService
from ami.ml.models.pipeline import collect_images, save_results
from ami.ml.schemas import (
    BoundingBox,
    ClassificationResponse,
    DetectionResponse,
    PipelineResponse,
    SourceImageResponse,
)
from ami.tests.fixtures.main import create_captures_from_files, create_processing_service, setup_test_project
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

    def _create_processing_service(self, name: str, slug: str, endpoint_url: str):
        processing_services_create_url = reverse_with_params("api:processingservice-list")
        self.client.force_authenticate(user=self.user)
        processing_service_data = {
            "project": self.project.pk,
            "name": name,
            "endpoint_url": endpoint_url,
            "slug": slug,
        }
        resp = self.client.post(processing_services_create_url, processing_service_data)
        self.client.force_authenticate(user=None)
        self.assertEqual(resp.status_code, 201)
        return resp.json()

    def _get_processing_service_id_by_slug(self, slug: str) -> int:
        processing_services_list_url = reverse_with_params("api:processingservice-list")
        self.client.force_authenticate(user=self.user)
        resp = self.client.get(processing_services_list_url)
        self.client.force_authenticate(user=None)
        self.assertEqual(resp.status_code, 200)

        # Find the processing service ID by slug
        resp = resp.json()
        processing_services = resp["results"]
        processing_service = next((b for b in processing_services if b["slug"] == slug), None)
        self.assertIsNotNone(processing_service, f"No processing service found with slug '{slug}'")
        return processing_service["id"]

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
            slug="processing_service_test",
            endpoint_url="http://processing_service:2000",
        )

    def test_project_was_added(self):
        response = self._create_processing_service(
            name="Processing Service Test",
            slug="processing_service_test",
            endpoint_url="http://processing_service:2000",
        )
        processing_service_id = response["id"]
        processing_service = ProcessingService.objects.get(pk=processing_service_id)
        self.assertIn(self.project, processing_service.projects.all())

    def test_processing_service_pipeline_registration(self):
        # register a processing service
        response = self._create_processing_service(
            name="Processing Service Test",
            slug="processing_service_test",
            endpoint_url="http://processing_service:2000",
        )
        processing_service_id = response["id"]

        # sync the processing service to create/add the associate pipelines
        response = self._register_pipelines(processing_service_id)
        processing_service = ProcessingService.objects.get(pk=processing_service_id)
        pipelines_queryset = processing_service.pipelines.all()

        self.assertEqual(pipelines_queryset.count(), len(response["pipelines"]))


class TestPipelineWithProcessingService(TestCase):
    def setUp(self):
        self.project, self.deployment = setup_test_project()
        self.captures = create_captures_from_files(self.deployment, skip_existing=False)
        self.test_images = [image for image, frame in self.captures]
        self.processing_service_instance = create_processing_service(self.project)
        self.processing_service = self.processing_service_instance
        self.pipeline = self.processing_service_instance.pipelines.all().filter(slug="constant").first()

    def test_run_pipeline(self):
        # Send images to Processing Service to process and return detections
        pipeline_response = self.pipeline.process_images(self.test_images, job_id=None)
        assert pipeline_response.detections


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
            name="Test Pipeline",
        )
        self.algorithms = {
            "detector": Algorithm.objects.create(name="Test Object Detector"),
            "binary_classifier": Algorithm.objects.create(name="Test Filter"),
            "species_classifier": Algorithm.objects.create(name="Test Classifier"),
        }
        self.pipeline.algorithms.set(self.algorithms.values())

    def test_create_pipeline(self):
        self.assertEqual(self.pipeline.slug, "test-pipeline")
        self.assertEqual(self.pipeline.algorithms.count(), 3)

        for algorithm in self.pipeline.algorithms.all():
            self.assertIn(algorithm.key, ["test-object-detector", "test-filter", "test-classifier"])

    def test_collect_images(self):
        images = list(collect_images(collection=self.image_collection, pipeline=self.pipeline))
        assert len(images) == 2

    def fake_pipeline_results(self, source_images: list[SourceImage], pipeline: Pipeline):
        source_image_results = [SourceImageResponse(id=image.pk, url=image.path) for image in source_images]
        detection_results = [
            DetectionResponse(
                source_image_id=image.pk,
                bbox=BoundingBox(x1=0.0, y1=0.0, x2=1.0, y2=1.0),
                inference_time=0.4,
                algorithm=self.algorithms["detector"].name,
                timestamp=datetime.datetime.now(),
                classifications=[
                    ClassificationResponse(
                        classification="Test taxon",
                        labels=["Test taxon"],
                        scores=[0.64333],
                        algorithm=self.algorithms["species_classifier"].name,
                        timestamp=datetime.datetime.now(),
                        terminal=True,
                    ),
                ],
            )
            for image in self.test_images
        ]
        fake_results = PipelineResponse(
            pipeline=self.pipeline.slug,
            total_time=0.0,
            source_images=source_image_results,
            detections=detection_results,
        )
        return fake_results

    def test_save_results(self):
        saved_objects = save_results(self.fake_pipeline_results(self.test_images, self.pipeline))

        for image in self.test_images:
            image.save()
            self.assertEqual(image.detections_count, 1)

        print(saved_objects)
        # @TODO test the cached counts for detections, etc are updated on Events, Deployments, etc.

    def no_test_skip_existing_results(self):
        # @TODO fix issue with "None" algorithm on some detections

        images = list(collect_images(collection=self.image_collection, pipeline=self.pipeline))
        total_images = len(images)
        self.assertEqual(total_images, self.image_collection.images.count())

        save_results(self.fake_pipeline_results(images, self.pipeline))

        images_again = list(collect_images(collection=self.image_collection, pipeline=self.pipeline))

        # Collect all detection algroithms used on the detections
        detection_algos_used = set(Detection.objects.all().values_list("detection_algorithm__name", flat=True))
        # Assert it was only one algorithm, and it was the one we used
        self.assertEqual(detection_algos_used, {self.algorithms["detector"].name}, "Wrong detection algorithm used.")

        # Collect all classification algorithms used on the classifications
        classification_algos_used = set(Classification.objects.all().values_list("algorithm__name", flat=True))
        # Assert it was only one algorithm, and it was the one we used
        self.assertEqual(
            classification_algos_used,
            {self.algorithms["species_classifier"].name},
            "Wrong classification algorithm used.",
        )

        remaining_images_to_process = len(images_again)
        self.assertEqual(remaining_images_to_process, 0)

    def test_skip_existing_with_new_detector(self):
        images = list(collect_images(collection=self.image_collection, pipeline=self.pipeline))
        total_images = len(images)
        self.assertEqual(total_images, self.image_collection.images.count())
        save_results(self.fake_pipeline_results(images, self.pipeline))
        self.pipeline.algorithms.set(
            [
                Algorithm.objects.create(name="NEW Object Detector 2.0"),
                self.algorithms["species_classifier"],  # Same classifier
            ]
        )
        images_again = list(collect_images(collection=self.image_collection, pipeline=self.pipeline))
        remaining_images_to_process = len(images_again)
        self.assertEqual(remaining_images_to_process, total_images)

    def test_skip_existing_with_new_classifier(self):
        """
        @TODO add support for skipping the detection model if only the classifier has changed.
        """
        images = list(collect_images(collection=self.image_collection, pipeline=self.pipeline))
        total_images = len(images)
        self.assertEqual(total_images, self.image_collection.images.count())
        save_results(self.fake_pipeline_results(images, self.pipeline))
        self.pipeline.algorithms.set(
            [
                self.algorithms["detector"],  # Same object detector
                Algorithm.objects.create(name="NEW Classifier 2.0"),
            ]
        )
        images_again = list(collect_images(collection=self.image_collection, pipeline=self.pipeline))
        remaining_images_to_process = len(images_again)
        self.assertEqual(remaining_images_to_process, total_images)

    def _test_skip_existing_per_batch_during_processing(self):
        # Send the same batch to two simultaneous processing pipelines
        # @TODO this needs to test the `process_images()` function with a real pipeline
        # @TODO enable test when a pipeline is added to the CI environment in PR #576
        pass

    def test_unknown_algorithm_returned_by_processing_service(self):
        fake_results = self.fake_pipeline_results(self.test_images, self.pipeline)

        new_detector_name = "Unknown Detector 5.1b-mobile"
        new_classifier_name = "Unknown Classifier 3.0b-mega"

        for detection in fake_results.detections:
            detection.algorithm = new_detector_name

            for classification in detection.classifications:
                classification.algorithm = new_classifier_name

        current_total_algorithm_count = Algorithm.objects.count()

        # @TODO assert a warning was logged
        save_results(fake_results)

        # Ensure new algorithms were added to the database
        new_algorithm_count = Algorithm.objects.count()
        self.assertEqual(new_algorithm_count, current_total_algorithm_count + 2)

        # Ensure new algorithms were also added to the pipeline
        self.assertTrue(self.pipeline.algorithms.filter(name=new_detector_name).exists())
        self.assertTrue(self.pipeline.algorithms.filter(name=new_classifier_name).exists())

    def no_test_reprocessing_after_unknown_algorithm_added(self):
        # @TODO fix issue with "None" algorithm on some detections

        images = list(collect_images(collection=self.image_collection, pipeline=self.pipeline))

        saved_objects = save_results(self.fake_pipeline_results(images, self.pipeline))

        new_detector_name = "Unknown Detector 5.1b-mobile"
        new_classifier_name = "Unknown Classifier 3.0b-mega"
        fake_results = self.fake_pipeline_results(images, self.pipeline)
        # Change the algorithm names to unknown ones
        for detection in fake_results.detections:
            detection.algorithm = new_detector_name

            for classification in detection.classifications:
                classification.algorithm = new_classifier_name

        # print("FAKE RESULTS")
        # print(fake_results)
        # print("END FAKE RESULTS")

        saved_objects = save_results(fake_results)
        saved_detections = [obj for obj in saved_objects if isinstance(obj, Detection)]
        saved_classifications = [obj for obj in saved_objects if isinstance(obj, Classification)]

        for obj in saved_detections:
            assert obj.detection_algorithm  # For type checker, not the test

            # Ensure the new detector was used for the detection
            self.assertEqual(obj.detection_algorithm.name, new_detector_name)

            # Ensure each detection has classification objects
            self.assertTrue(obj.classifications.exists())

            # Ensure detection has a correct classification object
            for classification in obj.classifications.all():
                self.assertIn(classification, saved_classifications)

        for obj in saved_classifications:
            assert obj.algorithm  # For type checker, not the test

            # Ensure the new classifier was used for the classification
            self.assertEqual(obj.algorithm.name, new_classifier_name)

            # Ensure each classification has the correct detection object
            self.assertIn(obj.detection, saved_detections, "Wrong detection object for classification object.")

        # Ensure new algorithms were added to the pipeline
        self.assertTrue(self.pipeline.algorithms.filter(name=new_detector_name).exists())
        self.assertTrue(self.pipeline.algorithms.filter(name=new_classifier_name).exists())

        detection_algos_used = Detection.objects.all().values_list("detection_algorithm__name", flat=True).distinct()
        self.assertTrue(new_detector_name in detection_algos_used)
        # Ensure None is not in the list
        self.assertFalse(None in detection_algos_used)
        classification_algos_used = Classification.objects.all().values_list("algorithm__name", flat=True)
        self.assertTrue(new_classifier_name in classification_algos_used)
        # Ensure None is not in the list
        self.assertFalse(None in classification_algos_used)

        # The algorithms are new, but they were registered to the pipeline, so the images should be skipped.
        images_again = list(collect_images(collection=self.image_collection, pipeline=self.pipeline))
        remaining_images_to_process = len(images_again)
        self.assertEqual(remaining_images_to_process, 0)
