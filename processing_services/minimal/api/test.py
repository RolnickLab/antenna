"""Contract tests for the minimal processing service. Run with: python -m unittest api.test"""

import unittest
from unittest import mock

import PIL.Image
from fastapi.testclient import TestClient

from . import algorithms
from .api import app, pipelines

IMAGE = {"id": "1", "url": "http://example.com/1.jpg"}


class TestAPI(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        patcher = mock.patch("api.schemas.get_image", return_value=PIL.Image.new("RGB", (640, 480)))
        patcher.start()
        self.addCleanup(patcher.stop)

    def process(self, pipeline: str, detections: list | None = None, status: int = 200) -> dict:
        response = self.client.post(
            "/process",
            json={"pipeline": pipeline, "source_images": [IMAGE], "config": {}, "detections": detections},
        )
        self.assertEqual(response.status_code, status, response.text)
        return response.json()

    def test_health_checks(self):
        self.assertEqual(self.client.get("/livez").json(), {"status": True})
        self.assertEqual(set(self.client.get("/readyz").json()["status"]), {p.config.slug for p in pipelines})

    def test_info_lists_every_algorithm_a_response_can_name(self):
        info = self.client.get("/info").json()
        listed = {p["slug"]: {a["key"] for a in p["algorithms"]} for p in info["pipelines"]}
        for slug, keys in listed.items():
            for detection in self.process(slug)["detections"]:
                returned = {detection["algorithm"]["key"]} | {
                    c["algorithm"]["key"] for c in detection["classifications"]
                }
                self.assertLessEqual(returned, keys, slug)

    def test_classifiers_have_category_maps_and_detectors_do_not(self):
        info = self.client.get("/info").json()
        for pipeline in info["pipelines"]:
            for algorithm in pipeline["algorithms"]:
                has_map = algorithm["category_map"] is not None
                self.assertEqual(has_map, algorithm["task_type"] == "classification", algorithm["key"])

    def test_each_pipeline_returns_one_detection_per_image_with_classifications(self):
        for pipeline in pipelines:
            data = self.process(pipeline.config.slug)
            self.assertEqual(data["source_images"], [IMAGE])
            [detection] = data["detections"]
            self.assertEqual(detection["source_image_id"], IMAGE["id"])
            self.assertTrue(detection["classifications"])
            self.assertTrue(detection["classifications"][-1]["terminal"])

    def test_existing_detections_are_classified_without_detecting_again(self):
        box = {"x1": 10.0, "y1": 20.0, "x2": 110.0, "y2": 220.0}
        sent = {"source_image": IMAGE, "bbox": box, "algorithm": {"name": "Other", "key": "other-detector"}}
        [detection] = self.process("constant", detections=[sent])["detections"]
        self.assertEqual(detection["bbox"], box)
        self.assertEqual(detection["algorithm"]["key"], "other-detector")
        self.assertEqual(detection["classifications"][0]["algorithm"]["key"], algorithms.CONSTANT_CLASSIFIER.key)

    def test_unknown_pipeline_is_rejected(self):
        self.process("no-such-pipeline", status=422)
