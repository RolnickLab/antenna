from django.test import TestCase

from ami.main.models import Occurrence
from ami.ml.models import Algorithm, AlgorithmResult
from ami.ml.post_processing.small_size_filter import SizeFilterResultData
from ami.tests.fixtures.main import setup_test_project

SIZE_FILTER = SizeFilterResultData.kind


class AlgorithmResultTestCase(TestCase):
    """A result's data fits its kind, its value follows its data, and its project is its occurrence's."""

    @classmethod
    def setUpTestData(cls) -> None:
        cls.project, cls.deployment = setup_test_project(reuse=False)
        cls.occurrence = Occurrence.objects.create(project=cls.project, deployment=cls.deployment)
        cls.algorithm = Algorithm.objects.create(name="Size filter", key="size-filter-result-test")

    def _size_filter(self, data: dict | None, **fields) -> AlgorithmResult:
        fields.setdefault("occurrence", self.occurrence)
        return AlgorithmResult(algorithm=self.algorithm, kind=SIZE_FILTER, data=data, **fields)

    def test_data_that_does_not_fit_its_kind_is_refused_on_every_write_path(self):
        for label, data in (
            ("missing field", {}),
            ("wrong type", {"relative_size": "small"}),
            ("unknown field", {"relative_size": 0.001, "note": "x"}),
            ("extra that is not JSON", {"relative_size": 0.001, "extra": {"when": object()}}),
        ):
            with self.subTest(label):
                with self.assertRaises(ValueError):
                    self._size_filter(data).save()
                with self.assertRaises(ValueError):
                    AlgorithmResult.objects.record_many([self._size_filter(data)])
        with self.assertRaises(ValueError):
            AlgorithmResult.objects.record(
                occurrence=self.occurrence, algorithm=self.algorithm, kind="unregistered", data={}
            )
        self.assertFalse(AlgorithmResult.objects.exists())

        result = AlgorithmResult.objects.record(
            occurrence=self.occurrence,
            algorithm=self.algorithm,
            kind=SIZE_FILTER,
            value=0.001,
            data={"relative_size": 0.001, "extra": {"service": "size-filter 1.2"}},
        )
        self.assertEqual(result.value, 0.001)
        self.assertEqual(result.data["extra"], {"service": "size-filter 1.2"})
        result.data["relative_size"] = "small"
        with self.assertRaises(ValueError):
            AlgorithmResult.objects.bulk_update([result], ["data"])

    def test_each_run_adds_a_result_beside_the_earlier_ones(self):
        first = AlgorithmResult.objects.record(
            occurrence=self.occurrence,
            algorithm=self.algorithm,
            kind=SIZE_FILTER,
            data={"relative_size": 0.01},
        )
        other_occurrence = Occurrence.objects.create(project=self.project, deployment=self.deployment)
        second, untouched = AlgorithmResult.objects.record_many(
            [
                self._size_filter({"relative_size": 0.02}),
                self._size_filter({"relative_size": 0.02}, occurrence=other_occurrence),
            ]
        )
        self.assertEqual(set(self.occurrence.algorithm_results.values_list("pk", flat=True)), {first.pk, second.pk})
        self.assertEqual(list(other_occurrence.algorithm_results.values_list("pk", flat=True)), [untouched.pk])

    def test_project_comes_from_the_occurrence_and_a_result_without_one_is_skipped(self):
        result = self._size_filter({"relative_size": 0.01})
        result.save()
        self.assertEqual(result.project_id, self.project.pk)

        orphan = Occurrence.objects.create(project=None, deployment=self.deployment)
        with self.assertLogs("ami.ml.models.algorithm_result", level="WARNING"):
            written = AlgorithmResult.objects.record_many(
                [
                    self._size_filter({"relative_size": 0.02}),
                    self._size_filter({"relative_size": 0.03}, occurrence=orphan),
                ]
            )
        # The occurrence with a project still gets its result; the other is skipped, not fatal.
        self.assertEqual([r.occurrence_id for r in written], [self.occurrence.pk])
        with self.assertRaises(ValueError):
            self._size_filter({"relative_size": 0.03}, occurrence=orphan).save()

    def test_value_is_the_figure_the_kind_names_on_every_write_path(self):
        saved = self._size_filter({"relative_size": 0.004}, value=0.9)
        saved.save()
        [created] = AlgorithmResult.objects.bulk_create(
            [self._size_filter({"relative_size": 0.005}, value=None, project=self.project)]
        )
        created.data = {"relative_size": 0.006}
        AlgorithmResult.objects.bulk_update([created], ["data"])
        created.refresh_from_db()
        self.assertEqual((saved.value, created.value), (0.004, 0.006))
