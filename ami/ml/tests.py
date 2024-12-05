import datetime
import unittest

from django.test import TestCase
from rich import print

from ami.main.models import Classification, Detection, Project, SourceImage, SourceImageCollection
from ami.ml.models import Algorithm, Pipeline
from ami.ml.models.pipeline import collect_images, create_algorithms_and_category_map, save_results
from ami.ml.schemas import (
    AlgorithmReference,
    AlgorithmResponse,
    BoundingBox,
    ClassificationResponse,
    DetectionResponse,
    PipelineResponse,
    SourceImageResponse,
)
from ami.tests.fixtures.main import create_captures_from_files, create_ml_pipeline, setup_test_project
from ami.tests.fixtures.ml import ALGORITHM_CHOICES


class TestPipelineWithMLBackend(TestCase):
    def setUp(self):
        self.project, self.deployment = setup_test_project()
        self.captures = create_captures_from_files(self.deployment, skip_existing=False)
        self.test_images = [image for image, frame in self.captures]
        self.pipeline = create_ml_pipeline(self.project)

    def test_run_pipeline(self):
        # Send images to ML backend to process and return detections
        pipeline_response = self.pipeline.process_images(self.test_images)
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

        self.algorithms, _created_objects = create_algorithms_and_category_map(ALGORITHM_CHOICES, [])
        self.pipeline.algorithms.set(self.algorithms.values())

    def test_create_pipeline(self):
        self.assertEqual(self.pipeline.slug, "test-pipeline")
        self.assertEqual(self.pipeline.algorithms.count(), 3)

        for algorithm in self.pipeline.algorithms.all():
            assert isinstance(algorithm, Algorithm)
            self.assertIn(algorithm.key, [algo.key for algo in ALGORITHM_CHOICES.values()])

    def test_collect_images(self):
        images = list(collect_images(collection=self.image_collection, pipeline=self.pipeline))
        assert len(images) == 2

    def fake_pipeline_results(self, source_images: list[SourceImage], pipeline: Pipeline):
        source_image_results = [SourceImageResponse(id=image.pk, url=image.path) for image in source_images]
        detector = ALGORITHM_CHOICES["random-detector"]
        species_classifier = ALGORITHM_CHOICES["random-species-classifier"]
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
        fake_results = PipelineResponse(
            pipeline=pipeline.slug,
            algorithms={detector.key: detector, species_classifier.key: species_classifier},
            total_time=0.0,
            source_images=source_image_results,
            detections=detection_results,
        )
        return fake_results

    def test_save_results(self):
        saved_objects = save_results(
            self.fake_pipeline_results(self.test_images, self.pipeline),
            return_created=True,
        )

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

    def test_unknown_algorithm_returned_by_backend(self):
        fake_results = self.fake_pipeline_results(self.test_images, self.pipeline)

        new_detector = AlgorithmResponse(
            name="Unknown Detector 5.1b-mobile", key="unknown-detector", task_type="detection"
        )
        new_classifier = AlgorithmResponse(
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

    def no_test_reprocessing_after_unknown_algorithm_added(self):
        # @TODO fix issue with "None" algorithm on some detections

        images = list(collect_images(collection=self.image_collection, pipeline=self.pipeline))

        save_results(self.fake_pipeline_results(images, self.pipeline))

        new_detector = AlgorithmResponse(
            name="Unknown Detector 5.1b-mobile", key="unknown-detector", task_type="detection"
        )
        new_classifier = AlgorithmResponse(
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
        saved_detections = [obj for obj in saved_objects if isinstance(obj, Detection)]
        saved_classifications = [obj for obj in saved_objects if isinstance(obj, Classification)]

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
