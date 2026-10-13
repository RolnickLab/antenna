"""Keep the template processing services' schemas in step with Antenna's contract in ami/ml/schemas.py.

The templates in processing_services/ run in their own containers, so they keep their own copies of the
schemas, which drift silently. These tests read the copies as source (nothing is imported) and compare
field names with Antenna's models of the same name.
"""

import ast
import pathlib
import tempfile

from django.test import SimpleTestCase

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
ANTENNA_SCHEMAS = REPO_ROOT / "ami" / "ml" / "schemas.py"
TEMPLATE_SCHEMAS = [
    REPO_ROOT / "processing_services" / "minimal" / "api" / "schemas.py",
    REPO_ROOT / "processing_services" / "minimal" / "worker" / "schemas.py",
    REPO_ROOT / "processing_services" / "example" / "api" / "schemas.py",
]

# A service sends these to Antenna: every field it sends must be one Antenna reads.
SENT_BY_SERVICES = {
    "AlgorithmCategoryMapResponse",
    "AlgorithmConfigResponse",
    "AlgorithmReference",
    "AsyncPipelineRegistrationRequest",
    "BoundingBox",
    "ClassificationResponse",
    "DetectionResponse",
    "PipelineConfigResponse",
    "PipelineResultsError",
    "PipelineResultsResponse",
    "PipelineStage",
    "PipelineStageParam",
    "PipelineTaskResult",
    "ProcessingServiceInfoResponse",
    "SourceImageResponse",
}
# Antenna sends these to a service: the service must accept every field Antenna sends.
SENT_BY_ANTENNA = {"DetectionRequest", "PipelineProcessingTask", "PipelineRequest", "SourceImageRequest"}


def model_fields(path: pathlib.Path) -> dict[str, set[str]]:
    """Annotated class attributes of each top-level class in a module, by class name."""
    fields = {}
    for node in ast.parse(path.read_text()).body:
        if isinstance(node, ast.ClassDef):
            fields[node.name] = {
                statement.target.id
                for statement in node.body
                if isinstance(statement, ast.AnnAssign)
                and isinstance(statement.target, ast.Name)
                and not statement.target.id.startswith("_")
            }
    return fields


class TestTemplateSchemasMatchAntenna(SimpleTestCase):
    def setUp(self):
        self.antenna = model_fields(ANTENNA_SCHEMAS)

    def test_every_compared_model_exists_in_antenna(self):
        self.assertLessEqual(SENT_BY_SERVICES | SENT_BY_ANTENNA, set(self.antenna))

    def test_templates_send_only_fields_antenna_reads(self):
        for path in TEMPLATE_SCHEMAS:
            for name, fields in model_fields(path).items():
                if name in SENT_BY_SERVICES:
                    with self.subTest(template=str(path.relative_to(REPO_ROOT)), model=name):
                        self.assertLessEqual(fields, self.antenna[name])

    def test_templates_accept_every_field_antenna_sends(self):
        for path in TEMPLATE_SCHEMAS:
            for name, fields in model_fields(path).items():
                if name in SENT_BY_ANTENNA:
                    with self.subTest(template=str(path.relative_to(REPO_ROOT)), model=name):
                        self.assertLessEqual(self.antenna[name], fields)

    def test_an_unknown_field_in_a_template_model_is_detected(self):
        source = "class DetectionResponse(Base):\n    bbox: int\n    not_in_antenna: str\n    _private: int\n"
        with tempfile.NamedTemporaryFile("w", suffix=".py") as template:
            template.write(source)
            template.flush()
            fields = model_fields(pathlib.Path(template.name))["DetectionResponse"]
        self.assertEqual(fields, {"bbox", "not_in_antenna"})
        self.assertFalse(fields <= self.antenna["DetectionResponse"])
