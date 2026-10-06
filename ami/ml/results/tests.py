from django.test import SimpleTestCase

from ami.ml.post_processing.registry import POSTPROCESSING_TASKS
from ami.ml.results import schemas


class ResultKindRegistryTest(SimpleTestCase):
    """Each registered kind publishes its data schema and declares which fields reference other records."""

    def test_every_kind_has_a_closed_json_schema(self):
        for kind in schemas.result_kinds():
            with self.subTest(kind):
                schema = schemas.data_json_schema(kind)
                self.assertEqual(schema["type"], "object")
                self.assertFalse(schema.get("additionalProperties", True))
                self.assertIn("extra", schema["properties"])
                # A nested model would emit #/definitions refs, which do not resolve inside OpenAPI.
                self.assertNotIn("definitions", schema)

    def test_every_result_model_a_task_declares_is_a_registered_kind(self):
        for key, task in POSTPROCESSING_TASKS.items():
            for model in task.result_models:
                with self.subTest(task=key, model=model.__name__):
                    self.assertIs(schemas.ALGORITHM_RESULT_DATA_SCHEMAS.get(model.kind), model)

    def test_each_kind_is_registered_under_its_models_kind(self):
        for kind, model in schemas.ALGORITHM_RESULT_DATA_SCHEMAS.items():
            with self.subTest(kind):
                self.assertEqual(model.kind, kind)

    def test_reference_fields_come_from_field_metadata(self):
        class Probe(schemas.AlgorithmResultData):
            merged_into_id: int | None = schemas.reference("occurrence")

        schemas.ALGORITHM_RESULT_DATA_SCHEMAS["probe"] = Probe
        try:
            self.assertEqual(schemas.reference_fields("probe"), {"merged_into_id": "occurrence"})
            self.assertEqual(schemas.reference_fields("class_masking"), {})
        finally:
            del schemas.ALGORITHM_RESULT_DATA_SCHEMAS["probe"]
