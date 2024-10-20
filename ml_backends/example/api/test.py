import unittest

from fastapi.testclient import TestClient

from .api import app
from .pipeline import DummyPipeline
from .schemas import PipelineRequest, SourceImage, SourceImageRequest


class TestPipeline(unittest.TestCase):
    def test_dummy_pipeline(self):
        source_images = [
            SourceImage(id="1", url="https://example.com/image1.jpg"),
            SourceImage(id="2", url="https://example.com/image2.jpg"),
        ]
        pipeline = DummyPipeline(source_images=source_images)
        detections = pipeline.run()

        self.assertEqual(len(detections), 20)
        for detection in detections:
            self.assertEqual(detection.source_image_id, "1")
            self.assertIsNotNone(detection.bbox)
            self.assertEqual(len(detection.classifications), 1)
            classification = detection.classifications[0]
            self.assertEqual(classification.classification, "moth")
            self.assertEqual(classification.labels, ["moth"])
            self.assertEqual(len(classification.scores), 1)
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
        request = PipelineRequest(pipeline="random", source_images=source_image_requests)
        response = self.client.post("/pipeline/process", json=request.dict())

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["pipeline"], "random")
        self.assertEqual(len(data["source_images"]), 2)
        self.assertEqual(len(data["detections"]), 20)
        self.assertGreater(data["total_time"], 0.0)
