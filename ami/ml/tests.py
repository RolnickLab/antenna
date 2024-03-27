import datetime

from django.test import TestCase

from ami.main.models import Project, SourceImage, SourceImageCollection
from ami.ml.models import Algorithm, Pipeline
from ami.ml.models.pipeline import collect_images, save_results
from ami.ml.schemas import (
    BoundingBox,
    ClassificationResponse,
    DetectionResponse,
    PipelineResponse,
    SourceImageResponse,
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
            name="Test Pipeline",
        )
        algorithms = [
            Algorithm.objects.create(name="Test Object Detector"),
            Algorithm.objects.create(name="Test Classifier"),
        ]
        self.pipeline.algorithms.set(algorithms)

    def test_create_pipeline(self):
        self.assertEqual(self.pipeline.slug, "test-pipeline")
        self.assertEqual(self.pipeline.algorithms.count(), 2)

        for algorithm in self.pipeline.algorithms.all():
            self.assertIn(algorithm.key, ["test-object-detector", "test-classifier"])

    def test_collect_images(self):
        images = list(collect_images(collection=self.image_collection, pipeline=self.pipeline))
        assert len(images) == 2

    def fake_pipeline_results(self, source_images: list[SourceImage]):
        source_image_results = [SourceImageResponse(id=image.pk, url=image.path) for image in source_images]
        detection_results = [
            DetectionResponse(
                source_image_id=image.pk,
                bbox=BoundingBox(x1=0.0, y1=0.0, x2=1.0, y2=1.0),
                inference_time=0.4,
                algorithm=self.pipeline.algorithms.all()[0].name,
                timestamp=datetime.datetime.now(),
            )
            for image in self.test_images
        ]
        classification_results = [
            ClassificationResponse(
                source_image_id=image.pk,
                classification="Test taxon",
                bbox=BoundingBox(x1=0.0, y1=0.0, x2=1.0, y2=1.0),
                labels=["Test taxon"],
                scores=[0.64333],
                algorithm=self.pipeline.algorithms.all()[1].name,
                timestamp=datetime.datetime.now(),
            )
            for image in self.test_images
        ]
        fake_results = PipelineResponse(
            pipeline=self.pipeline.slug,
            total_time=0.0,
            source_images=source_image_results,
            detections=detection_results,
            classifications=classification_results,
        )
        return fake_results

    def test_save_results(self):
        saved_objects = save_results(self.fake_pipeline_results(self.test_images))

        for image in self.test_images:
            image.save()
            self.assertEqual(image.detections_count, 1)
        print(saved_objects)

    def test_skip_existing_results(self):
        images = list(collect_images(collection=self.image_collection, pipeline=self.pipeline))
        self.assertEqual(len(images), self.image_collection.images.count())
        save_results(self.fake_pipeline_results(images))
        images_again = list(collect_images(collection=self.image_collection, pipeline=self.pipeline))
        self.assertEqual(len(images_again), 0)
