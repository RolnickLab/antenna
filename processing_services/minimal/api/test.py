"""Contract tests for the minimal processing service. Run with: python -m unittest api.test"""

import unittest
from unittest import mock

import PIL.Image
from fastapi.testclient import TestClient

from . import algorithms, vectors
from .api import ALL_PIPELINES, app, select_pipelines

IMAGE = {"id": "1", "url": "http://example.com/1.jpg"}
DETECTOR = {"name": "Some detector", "key": "some-detector"}
EXTRACTOR_KEY = algorithms.CONSTANT_FEATURE_EXTRACTOR.key


def detection_request(bbox: dict | None, crop_image_url: str | None = None) -> dict:
    return {"source_image": IMAGE, "bbox": bbox, "crop_image_url": crop_image_url, "algorithm": DETECTOR}


class TestAPI(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        patcher = mock.patch("api.schemas.get_image", return_value=PIL.Image.new("RGB", (640, 480)))
        patcher.start()
        self.addCleanup(patcher.stop)

    def process(self, pipeline: str, config: dict | None = None, detections: list | None = None, status=200):
        response = self.client.post(
            "/process",
            json={"pipeline": pipeline, "source_images": [IMAGE], "config": config, "detections": detections},
        )
        self.assertEqual(response.status_code, status, response.text)
        return response.json()

    def info_algorithm_keys(self) -> dict[str, set[str]]:
        info = self.client.get("/info").json()
        return {pipeline["slug"]: {a["key"] for a in pipeline["algorithms"]} for pipeline in info["pipelines"]}

    def test_health_checks(self):
        self.assertEqual(self.client.get("/livez").json(), {"status": True})
        self.assertEqual(set(self.client.get("/readyz").json()["status"]), {p.config.slug for p in ALL_PIPELINES})

    def test_every_returned_algorithm_is_listed_in_info(self):
        listed = self.info_algorithm_keys()
        for slug in listed:
            data = self.process(slug, {"features_for_all_detections": True})
            for detection in data["detections"]:
                returned = {detection["algorithm"]["key"]}
                returned |= {c["algorithm"]["key"] for c in detection["classifications"]}
                returned |= {e["algorithm"]["key"] for e in detection["embeddings"] or []}
                self.assertLessEqual(returned, listed[slug], slug)

    def test_the_extractor_adds_one_fixed_length_deterministic_vector_per_detection(self):
        first = self.process("constant-with-feature-extractor")["detections"]
        second = self.process("constant-with-feature-extractor")["detections"]
        self.assertTrue(first)
        for detection in first:
            [embedding] = detection["embeddings"]
            self.assertEqual(embedding["algorithm"]["key"], EXTRACTOR_KEY)
            self.assertEqual(len(embedding["features"]), vectors.EXTRACTOR_VECTOR_LENGTH)
            self.assertTrue(detection["classifications"])
        self.assertEqual(first[0]["embeddings"], second[0]["embeddings"])

    def test_an_empty_extractor_key_turns_the_extractor_off(self):
        data = self.process("constant-with-feature-extractor", {"embedding_extractor": ""})
        self.assertTrue(all(d["embeddings"] is None for d in data["detections"]))

    def test_an_extractor_the_pipeline_does_not_offer_is_rejected(self):
        self.process("constant-with-feature-extractor", {"embedding_extractor": "other"}, status=422)
        self.process("constant", {"embedding_extractor": EXTRACTOR_KEY}, status=422)

    def test_features_for_all_detections_adds_the_classifier_vector(self):
        data = self.process("constant", {"features_for_all_detections": True})
        for detection in data["detections"]:
            [embedding] = detection["embeddings"]
            self.assertEqual(embedding["algorithm"]["key"], algorithms.CONSTANT_CLASSIFIER.key)
            self.assertEqual(len(embedding["features"]), vectors.CLASSIFIER_VECTOR_LENGTH)
        self.assertIsNone(self.process("constant")["detections"][0]["embeddings"])

    def test_include_logits_false_drops_logits(self):
        with_logits = self.process("random-detection-random-species")
        self.assertTrue(all(c["logits"] for d in with_logits["detections"] for c in d["classifications"]))
        without = self.process("random-detection-random-species", {"include_logits": False})
        self.assertTrue(all(c["logits"] is None for d in without["detections"] for c in d["classifications"]))

    def test_keys_meant_for_antenna_are_ignored(self):
        self.process("constant", {"request_source_image_batch_size": 8, "reprocess_existing_detections": True})

    def test_feature_only_pipeline_echoes_the_boxes_it_is_sent(self):
        box = {"x1": 10.5, "y1": 20.0, "x2": 110.0, "y2": 220.25}
        data = self.process(
            "constant-feature-extractor-only",
            detections=[
                detection_request(box, crop_image_url="http://example.com/crop.jpg"),
                detection_request(None),
                detection_request({"x1": 5, "y1": 5, "x2": 5, "y2": 50}),
            ],
        )
        [detection] = data["detections"]
        self.assertEqual(detection["bbox"], box)
        self.assertEqual(detection["algorithm"], DETECTOR)
        self.assertEqual(detection["crop_image_url"], "http://example.com/crop.jpg")
        self.assertEqual(detection["classifications"], [])
        [embedding] = detection["embeddings"]
        self.assertEqual(embedding["algorithm"]["key"], EXTRACTOR_KEY)

    def test_feature_only_pipeline_detects_when_sent_no_detections(self):
        data = self.process("constant-feature-extractor-only", {"embedding_extractor": ""})
        [detection] = data["detections"]
        self.assertEqual(detection["algorithm"]["key"], algorithms.CONSTANT_DETECTOR.key)
        self.assertEqual(len(detection["embeddings"]), 1)

    def test_unknown_pipeline_is_rejected(self):
        self.process("no-such-pipeline", status=422)


class TestPipelineSelection(unittest.TestCase):
    def test_empty_setting_selects_all(self):
        self.assertEqual(select_pipelines(" "), ALL_PIPELINES)

    def test_named_pipelines_are_selected_in_order(self):
        selected = select_pipelines("constant-feature-extractor-only, constant")
        self.assertEqual([p.config.slug for p in selected], ["constant-feature-extractor-only", "constant"])

    def test_unknown_slug_raises(self):
        with self.assertRaises(ValueError):
            select_pipelines("constant,typo")
