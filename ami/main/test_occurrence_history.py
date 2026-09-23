"""An occurrence's history: algorithm results and reviews, and the endpoint that reads them."""

from django.test import TestCase

from ami.main.models import Occurrence, OccurrenceHistoryRecord
from ami.tests.fixtures.main import setup_test_project


class OccurrenceHistoryPayloadTestCase(TestCase):
    """A history payload always fits the schema for its kind and subtype, however it is written."""

    def setUp(self) -> None:
        self.project, self.deployment = setup_test_project(reuse=False)
        self.occurrence = Occurrence.objects.create(project=self.project, deployment=self.deployment)

    def _size_filter(self, payload: dict) -> OccurrenceHistoryRecord:
        return OccurrenceHistoryRecord.build(
            occurrence_id=self.occurrence.pk,
            kind=OccurrenceHistoryRecord.Kind.ALGORITHM_RESULT,
            subtype="size_filter",
            payload=payload,
        )

    def test_a_valid_payload_is_stored_as_given(self):
        record = self._size_filter({"size_threshold": 0.001, "detection_ids": [3, 4]})
        record.save()
        record.refresh_from_db()
        self.assertEqual(record.payload["detection_ids"], [3, 4])
        self.assertIsNone(record.payload["taxon_after_id"])

    def test_a_payload_that_does_not_fit_its_schema_is_refused(self):
        for label, payload in (
            ("missing field", {"size_threshold": 0.001}),
            ("wrong type", {"size_threshold": "small", "detection_ids": []}),
            ("unknown field", {"size_threshold": 0.001, "detection_ids": [], "note": "x"}),
        ):
            with self.subTest(label), self.assertRaises(ValueError):
                self._size_filter(payload)

    def test_save_validates_too_and_an_unknown_subtype_is_refused(self):
        record = OccurrenceHistoryRecord(
            occurrence=self.occurrence,
            kind=OccurrenceHistoryRecord.Kind.ALGORITHM_RESULT,
            subtype="size_filter",
            payload={"size_threshold": 0.001},
            timestamp=self.occurrence.created_at,
        )
        with self.assertRaises(ValueError):
            record.save()
        record.subtype = "not_a_subtype"
        record.payload = {}
        with self.assertRaises(ValueError):
            record.save()
        self.assertFalse(OccurrenceHistoryRecord.objects.exists())
