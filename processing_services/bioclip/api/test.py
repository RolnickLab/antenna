import unittest

from fastapi.testclient import TestClient

from .api import app
from .pipelines import CustomPipeline
from .schemas import PipelineRequest, SourceImage, SourceImageRequest


class TestPipeline(unittest.TestCase):
    def test_custom_pipeline(self):
        # @TODO: Load actual antenna images?
        pipeline = CustomPipeline(
            source_images=[
                SourceImage(
                    id="1001",
                    url=(
                        "https://huggingface.co/datasets/huggingface/"
                        "documentation-images/resolve/main/pipeline-cat-chonk.jpeg"
                    ),
                ),
                SourceImage(id="1002", url="https://cdn.britannica.com/79/191679-050-C7114D2B/Adult-capybara.jpg"),
            ],
            detector_batch_size=2,
            classifier_batch_size=2,
        )
        detections = pipeline.run()

        self.assertEqual(len(detections), 20)
        expected_labels = ["lynx, catamount", "beaver"]
        for detection_id, detection in enumerate(detections):
            self.assertEqual(detection.source_image_id, pipeline.source_images[detection_id].id)
            self.assertIsNotNone(detection.bbox)
            self.assertEqual(len(detection.classifications), 1)
            classification = detection.classifications[0]
            self.assertEqual(classification.classification, expected_labels[detection_id])
            self.assertGreaterEqual(classification.scores[0], 0.0)
            self.assertLessEqual(classification.scores[0], 1.0)


class TestAPI(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_root(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.url, "http://testserver/docs")

    def test_process(self):
        source_images = [
            SourceImage(id="1", url="https://example.com/image1.jpg"),
            SourceImage(id="2", url="https://example.com/image2.jpg"),
        ]
        source_image_requests = [SourceImageRequest(**image.dict()) for image in source_images]
        request = PipelineRequest(pipeline="local-pipeline", source_images=source_image_requests, config={})
        response = self.client.post("/process", json=request.dict())

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["pipeline"], "local-pipeline")
        self.assertEqual(len(data["source_images"]), 2)
        self.assertEqual(len(data["detections"]), 2)
        self.assertGreater(data["total_time"], 0.0)
