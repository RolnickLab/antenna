"""
Tests for the global moth classifier using a tiny stand-in model and a four-class labels file,
so nothing is downloaded and the tests run in about a second.
"""

import json
import os
import pathlib
import tempfile
import unittest
from unittest import mock

import PIL.Image
import torch

from . import global_moth_classifier
from .algorithms import SAVED_MODELS
from .global_moth_classifier import GlobalMothClassifier, get_model_url
from .schemas import AlgorithmReference, BoundingBox, ClassificationResponse, Detection, DetectionResponse, SourceImage

LABELS = {"Moth a": 0, "Moth b": 1, "Moth c": 2, "Moth d": 3}


class TinyClassifier(GlobalMothClassifier):
    """The real classifier with the ResNet replaced by a single linear layer on 8x8 images."""

    input_size = 8

    def get_model(self) -> torch.nn.Module:
        torch.manual_seed(0)
        model = torch.nn.Sequential(torch.nn.Flatten(), torch.nn.Linear(3 * 8 * 8, self.num_classes))
        return model.to(self.device).eval()


def make_detection(detection_id: str, color: tuple[int, int, int] | None) -> Detection:
    detection = Detection(
        id=detection_id,
        url="https://example.org/source.jpg",
        source_image=SourceImage(id="1", url="https://example.org/source.jpg"),
        bbox=BoundingBox(x1=0, y1=0, x2=8, y2=8),
        algorithm=AlgorithmReference(name="Detector", key="detector"),
    )
    if color is not None:
        detection._pil = PIL.Image.new("RGB", (16, 16), color)
    return detection


class TestGlobalMothClassifier(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.labels_path = pathlib.Path(tmp.name) / "labels.json"
        self.labels_path.write_text(json.dumps(LABELS))
        self.addCleanup(SAVED_MODELS.clear)
        self.addCleanup(global_moth_classifier._CATEGORY_MAPS.clear)

    def make_classifier(self) -> TinyClassifier:
        classifier = TinyClassifier(weights_path=None, labels_path=str(self.labels_path), device="cpu")
        classifier.compile()
        return classifier

    def expected_logits(self, classifier: TinyClassifier, color: tuple[int, int, int]) -> list[float]:
        image = PIL.Image.new("RGB", (16, 16), color)
        with torch.no_grad():
            return classifier.model(classifier.transforms(image).unsqueeze(0))[0].tolist()

    def test_category_map_is_built_from_the_labels_file(self):
        classifier = TinyClassifier(weights_path=None, labels_path=str(self.labels_path))
        category_map = classifier.algorithm_config_response.category_map

        self.assertEqual(category_map.labels, ["Moth a", "Moth b", "Moth c", "Moth d"])
        self.assertEqual([row["index"] for row in category_map.data], [0, 1, 2, 3])
        self.assertEqual(category_map.data[2]["label"], "Moth c")

    def test_class_count_comes_from_the_labels_file(self):
        self.assertEqual(self.make_classifier().num_classes, len(LABELS))

    def test_labels_with_gaps_are_rejected(self):
        self.labels_path.write_text(json.dumps({"Moth a": 0, "Moth b": 5}))
        classifier = TinyClassifier(weights_path=None, labels_path=str(self.labels_path))
        with self.assertRaises(ValueError):
            classifier.compile()

    def test_returns_all_logits_and_the_argmax_label_without_scores(self):
        classifier = self.make_classifier()
        color = (200, 30, 90)

        (result,) = classifier.run([make_detection("a", color)])
        classification = result.classifications[0]

        expected = self.expected_logits(classifier, color)
        self.assertEqual(len(classification.logits), len(LABELS))
        for actual, wanted in zip(classification.logits, expected, strict=True):
            self.assertAlmostEqual(actual, wanted, places=3)
        self.assertEqual(classification.classification, list(LABELS)[expected.index(max(expected))])
        self.assertEqual(classification.scores, [])
        self.assertIsNone(classification.labels)

    def test_detection_without_an_image_does_not_shift_the_other_predictions(self):
        classifier = self.make_classifier()
        colors = {"a": (250, 0, 0), "c": (0, 0, 250)}
        detections = [make_detection("a", colors["a"]), make_detection("b", None), make_detection("c", colors["c"])]

        results = classifier.run(detections)

        self.assertEqual([r.id for r in results], ["a", "c"])
        for result in results:
            expected = self.expected_logits(classifier, colors[result.id])
            for actual, wanted in zip(result.classifications[0].logits, expected, strict=True):
                self.assertAlmostEqual(actual, wanted, places=3)

    def test_no_detections_returns_nothing(self):
        self.assertEqual(self.make_classifier().run([]), [])

    def test_running_before_compile_raises(self):
        classifier = TinyClassifier(weights_path=None, labels_path=str(self.labels_path))
        with self.assertRaises(RuntimeError):
            classifier.run([make_detection("a", (1, 2, 3))])

    def test_loaded_model_is_shared_between_instances(self):
        first = self.make_classifier()
        second = self.make_classifier()
        self.assertIs(first.model, second.model)

    def test_model_base_url_can_be_overridden(self):
        with mock.patch.dict(os.environ, {"MODEL_BASE_URL": "https://mirror.example.org/models/"}):
            self.assertEqual(get_model_url("moths/a.pth"), "https://mirror.example.org/models/moths/a.pth")
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("MODEL_BASE_URL", None)
            self.assertTrue(get_model_url("moths/a.pth").startswith(global_moth_classifier.DEFAULT_MODEL_BASE_URL))


class TestResponseSchemas(unittest.TestCase):
    def test_logits_only_classification_and_detection_without_bbox_are_valid(self):
        algorithm = AlgorithmReference(name="Classifier", key="classifier")
        classification = ClassificationResponse(
            classification="Moth a", logits=[0.5, -1.0], algorithm=algorithm, timestamp="2026-01-01T00:00:00"
        )
        detection = DetectionResponse(
            source_image_id="1", algorithm=algorithm, timestamp="2026-01-01T00:00:00", classifications=[classification]
        )

        self.assertIsNone(detection.bbox)
        self.assertEqual(detection.classifications[0].scores, [])


if __name__ == "__main__":
    unittest.main()
