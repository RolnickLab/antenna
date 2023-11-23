from django.test import TestCase

from ami.main.models import SourceImage
from ami.ml.models.pipeline import save_results
from ami.ml.schemas import (
    BoundingBox,
    ClassificationResponse,
    DetectionResponse,
    PipelineResponse,
    SourceImageResponse,
)


class TestPipeline(TestCase):
    def setUp(self):
        self.test_images = [SourceImage.objects.create()]

    def test_save_results(self):
        source_image_id = str(self.test_images[0].pk)
        fake_results = PipelineResponse(
            pipeline="panama-moths-2023",
            total_time=0.0,
            source_images=[
                SourceImageResponse(
                    id=source_image_id,
                    url="https://example.com",
                ),
            ],
            detections=[
                DetectionResponse(
                    source_image_id=source_image_id,
                    bbox=BoundingBox(x1=0.0, y1=0.0, x2=1.0, y2=1.0),
                    inference_time=0.4,
                    algorithm="Test Detector",
                ),
            ],
            classifications=[
                ClassificationResponse(
                    source_image_id=source_image_id,
                    classification="Test taxon",
                    bbox=BoundingBox(x1=0.0, y1=0.0, x2=1.0, y2=1.0),
                    labels=["Test taxon"],
                    scores=[0.64333],
                    algorithm="Test Classifier",
                ),
            ],
        )
        saved_objects = save_results(fake_results)

        for image in self.test_images:
            image.save()
            self.assertEqual(image.detections_count, 1)
        print(saved_objects)

    def test_save_multiple(self):
        for _ in range(3):
            self.test_save_results()
