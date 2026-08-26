"""Tests for the pydantic ``config_schema`` contract on ``BasePostProcessingTask``."""
import abc
import inspect

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

    def test_abstract_subclass_is_not_required_to_declare_contract(self):
        # An abstract intermediary (leaves an abstractmethod unimplemented) may defer
        # key/name/config_schema to its concrete subclasses without raising.
        class AbstractFilter(BasePostProcessingTask):
            @abc.abstractmethod
            def filter_step(self) -> None:
                ...

            def run(self) -> None:  # pragma: no cover - never instantiated
                pass

        self.assertTrue(inspect.isabstract(AbstractFilter))

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

    def test_occurrence_scope_is_accepted(self):
        # The discriminated scope: an occurrence id is a valid alternative to a
        # collection id (the per-occurrence / dev trigger).
        task = SmallSizeFilterTask(occurrence_id=7)
        config: SmallSizeFilterConfig = task.config  # type: ignore[assignment]
        self.assertEqual(config.occurrence_id, 7)
        self.assertIsNone(config.source_image_collection_id)

    def test_both_scopes_at_once_raises(self):
        # Exactly one scope must be set; supplying both is ambiguous.
        with pytest.raises(pydantic.ValidationError):
            SmallSizeFilterTask(source_image_collection_id=1, occurrence_id=7)

    def test_no_scope_raises(self):
        # Neither scope set — nothing identifies which detections to examine.
        with pytest.raises(pydantic.ValidationError):
            SmallSizeFilterTask(size_threshold=0.001)

    def test_invalid_config_raises_at_init(self):
        with pytest.raises(pydantic.ValidationError):
            SmallSizeFilterTask(source_image_collection_id=1, size_threshold=2.0)

    def test_unknown_keys_rejected(self):
        with pytest.raises(pydantic.ValidationError):
            SmallSizeFilterTask(source_image_collection_id=1, unknown_field="oops")
