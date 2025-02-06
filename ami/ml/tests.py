import datetime
import unittest

from django.test import TestCase
from rest_framework.test import APIRequestFactory, APITestCase

from ami.base.serializers import reverse_with_params
from ami.main.models import Classification, Detection, Project, SourceImage, SourceImageCollection
from ami.ml.models import Algorithm, Pipeline, ProcessingService
from ami.ml.models.pipeline import collect_images, get_or_create_algorithm_and_category_map, save_results
from ami.ml.schemas import (
    AlgorithmConfigResponse,
    AlgorithmReference,
    BoundingBox,
    ClassificationResponse,
    DetectionResponse,
    PipelineResultsResponse,
    SourceImageResponse,
)
from ami.tests.fixtures.main import create_captures_from_files, create_processing_service, setup_test_project
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
        return resp.json()

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


class TestPipelineWithProcessingService(TestCase):
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

    def test_alignment_of_predictions_and_category_map(self):
        # Ensure that the scores and labels are aligned
        pipeline = self.processing_service_instance.pipelines.all().get(slug="random")
        pipeline_response = pipeline.process_images(self.test_images, project_id=self.project.pk)
        results = save_results(pipeline_response, return_created=True)
        assert results is not None, "Expecected results to be returned in a PipelineSaveResults object"
        assert results.classifications, "Expected classifications to be returned in the results"
        for classification in results.classifications:
            assert classification.scores
            taxa_with_scores = list(classification.predictions_with_taxa(sort=True))
            assert taxa_with_scores
            assert classification.score == taxa_with_scores[0][1]
            assert classification.taxon == taxa_with_scores[0][0]

    def test_top_n_alignment(self):
        # Ensure that the top_n parameter works
        pipeline = self.processing_service_instance.pipelines.all().get(slug="random")
        pipeline_response = pipeline.process_images(self.test_images, project_id=self.project.pk)
        results = save_results(pipeline_response, return_created=True)
        assert results is not None, "Expecected results to be returned in a PipelineSaveResults object"
        assert results.classifications, "Expected classifications to be returned in the results"
        for classification in results.classifications:
            top_n = classification.top_n(n=3)
            assert classification.score == top_n[0]["score"]
            assert classification.taxon == top_n[0]["taxon"]


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
            key: get_or_create_algorithm_and_category_map(val) for key, val in ALGORITHM_CHOICES.items()
        }
        self.pipeline.algorithms.set([algo for algo in self.algorithms.values()])

    def test_create_pipeline(self):
        assert self.pipeline.slug.startswith("test-pipeline")
        self.assertEqual(self.pipeline.algorithms.count(), len(ALGORITHM_CHOICES))

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
                        labels=None,
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
                        labels=None,
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

    def no_test_skip_existing_results(self):
        # @TODO fix issue with "None" algorithm on some detections

        images = list(collect_images(collection=self.image_collection, pipeline=self.pipeline))
        total_images = len(images)
        self.assertEqual(total_images, self.image_collection.images.count())

        save_results(self.fake_pipeline_results(images, self.pipeline), return_created=True)

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

    def _test_skip_existing_per_batch_during_processing(self):
        # Send the same batch to two simultaneous processing pipelines
        # @TODO this needs to test the `process_images()` function with a real pipeline
        # @TODO enable test when a pipeline is added to the CI environment in PR #576
        pass

    def test_unknown_algorithm_returned_by_processing_service(self):
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

        # @TODO assert a warning was logged
        save_results(fake_results)

        # Ensure new algorithms were added to the database
        new_algorithm_count = Algorithm.objects.count()
        self.assertEqual(new_algorithm_count, current_total_algorithm_count + 2)

        # Ensure new algorithms were also added to the pipeline
        self.assertTrue(self.pipeline.algorithms.filter(name=new_detector.name, key=new_detector.key).exists())
        self.assertTrue(self.pipeline.algorithms.filter(name=new_classifier.name, key=new_classifier.key).exists())

    @unittest.skip("Not implemented yet")
    def test_reprocessing_after_unknown_algorithm_added(self):
        # @TODO fix issue with "None" algorithm on some detections

        images = list(collect_images(collection=self.image_collection, pipeline=self.pipeline))

        save_results(self.fake_pipeline_results(images, self.pipeline))

        new_detector = AlgorithmConfigResponse(
            name="Unknown Detector 5.1b-mobile", key="unknown-detector", task_type="detection"
        )
        new_classifier = AlgorithmConfigResponse(
            name="Unknown Classifier 3.0b-mega", key="unknown-classifier", task_type="classification"
        )

        fake_results = self.fake_pipeline_results(images, self.pipeline)

        # Change the algorithm names to unknown ones
        for detection in fake_results.detections:
            detection.algorithm = AlgorithmReference(name=new_detector.name, key=new_detector.key)

            for classification in detection.classifications:
                classification.algorithm = AlgorithmReference(name=new_classifier.name, key=new_classifier.key)

        fake_results.algorithms[new_detector.key] = new_detector
        fake_results.algorithms[new_classifier.key] = new_classifier

        # print("FAKE RESULTS")
        # print(fake_results)
        # print("END FAKE RESULTS")

        saved_objects = save_results(fake_results, return_created=True)
        assert saved_objects is not None
        saved_detections = saved_objects.detections
        saved_classifications = saved_objects.classifications

        for obj in saved_detections:
            assert obj.detection_algorithm  # For type checker, not the test

            # Ensure the new detector was used for the detection
            self.assertEqual(obj.detection_algorithm.name, new_detector.name)

            # Ensure each detection has classification objects
            self.assertTrue(obj.classifications.exists())

            # Ensure detection has a correct classification object
            for classification in obj.classifications.all():
                self.assertIn(classification, saved_classifications)

        for obj in saved_classifications:
            assert obj.algorithm  # For type checker, not the test

            # Ensure the new classifier was used for the classification
            self.assertEqual(obj.algorithm.name, new_classifier.name)

            # Ensure each classification has the correct detection object
            self.assertIn(obj.detection, saved_detections, "Wrong detection object for classification object.")

        # Ensure new algorithms were added to the pipeline
        self.assertTrue(self.pipeline.algorithms.filter(name=new_detector.name).exists())
        self.assertTrue(self.pipeline.algorithms.filter(name=new_classifier.name).exists())

        detection_algos_used = Detection.objects.all().values_list("detection_algorithm__name", flat=True).distinct()
        self.assertTrue(new_detector.name in detection_algos_used)
        # Ensure None is not in the list
        self.assertFalse(None in detection_algos_used)
        classification_algos_used = Classification.objects.all().values_list("algorithm__name", flat=True)
        self.assertTrue(new_classifier.name in classification_algos_used)
        # Ensure None is not in the list
        self.assertFalse(None in classification_algos_used)

        # The algorithms are new, but they were registered to the pipeline, so the images should be skipped.
        images_again = list(collect_images(collection=self.image_collection, pipeline=self.pipeline))
        remaining_images_to_process = len(images_again)
        self.assertEqual(remaining_images_to_process, 0)

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
