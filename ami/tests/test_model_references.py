import pydantic
from django.test import TestCase

from ami.base.model_references import (
    ModelRef,
    model_reference,
    reference_types,
    resolve_model_references,
    unmapped_reference_types,
)
from ami.main.models import TaxaList
from ami.ml.models import Algorithm
from ami.tests.fixtures.queries import no_query_cache


class ReferenceTestCase(TestCase):
    """Record ids stored in JSON become {type, id, name}; a deleted row keeps its id with no name."""

    def test_resolves_each_type_in_one_query_and_marks_missing_rows(self):
        taxa_list = TaxaList.objects.create(name="Kept species")
        algorithm = Algorithm.objects.create(name="Classifier", key="ref-test-classifier")
        wanted = [("taxa_list", taxa_list.pk), ("algorithm", algorithm.pk), ("taxa_list", 999999)]
        with no_query_cache(), self.assertNumQueries(2):
            refs = resolve_model_references(wanted)
        self.assertEqual(refs[("taxa_list", taxa_list.pk)], ModelRef("taxa_list", taxa_list.pk, "Kept species"))
        self.assertEqual(refs[("algorithm", algorithm.pk)].name, "Classifier")
        self.assertEqual(refs[("taxa_list", 999999)], ModelRef("taxa_list", 999999, None))

    def test_types_come_from_the_models_that_declare_them(self):
        self.assertTrue({"algorithm", "capture_set", "occurrence", "taxa_list"} <= set(reference_types()))
        self.assertIs(reference_types()["taxa_list"][0], TaxaList)

    def test_a_schema_naming_a_type_no_model_declares_is_reported(self):
        """Resolving such a field would fail at request time, so a test over real schemas keeps this empty."""

        class Probe(pydantic.BaseModel):
            merged_into_id: int | None = model_reference("not_a_type")

        self.assertEqual(unmapped_reference_types([Probe]), {"not_a_type"})
