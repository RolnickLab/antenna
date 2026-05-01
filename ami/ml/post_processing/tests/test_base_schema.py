"""Tests for the pydantic ``config_schema`` contract on ``BasePostProcessingTask``."""
import pydantic
import pytest
from django.test import TestCase

from ami.ml.post_processing.base import BasePostProcessingTask
from ami.ml.post_processing.small_size_filter import SmallSizeFilterConfig, SmallSizeFilterTask


class TestConfigSchemaContract(TestCase):
    """``__init_subclass__`` enforces ``config_schema``; ``__init__`` validates against it."""

    def test_subclass_without_config_schema_raises(self):
        with pytest.raises(TypeError, match="config_schema"):

            class Missing(BasePostProcessingTask):
                key = "missing"
                name = "Missing schema"

                def run(self) -> None:
                    pass

    def test_valid_config_builds_basemodel_instance(self):
        task = SmallSizeFilterTask(source_image_collection_id=1, size_threshold=0.001)
        self.assertIsInstance(task.config, SmallSizeFilterConfig)
        config: SmallSizeFilterConfig = task.config  # type: ignore[assignment]
        self.assertEqual(config.size_threshold, 0.001)
        self.assertEqual(config.source_image_collection_id, 1)

    def test_default_value_applies_when_omitted(self):
        task = SmallSizeFilterTask(source_image_collection_id=1)
        config: SmallSizeFilterConfig = task.config  # type: ignore[assignment]
        self.assertEqual(config.size_threshold, 0.0008)

    def test_invalid_config_raises_at_init(self):
        with pytest.raises(pydantic.ValidationError):
            SmallSizeFilterTask(source_image_collection_id=1, size_threshold=2.0)

    def test_missing_required_field_raises(self):
        with pytest.raises(pydantic.ValidationError):
            SmallSizeFilterTask(size_threshold=0.001)

    def test_unknown_keys_rejected(self):
        with pytest.raises(pydantic.ValidationError):
            SmallSizeFilterTask(source_image_collection_id=1, unknown_field="oops")
