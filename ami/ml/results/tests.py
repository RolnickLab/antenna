from django.test import SimpleTestCase, TestCase

from ami.main.models import Occurrence
from ami.ml.models import Algorithm, AlgorithmResult
from ami.ml.post_processing.registry import POSTPROCESSING_TASKS
from ami.ml.results import schemas
from ami.ml.results.schemas import SizeFilterResultData
from ami.tests.fixtures.main import setup_test_project

SIZE_FILTER = SizeFilterResultData.kind


class ResultKindRegistryTest(SimpleTestCase):
    """Each registered kind is keyed by its model's kind, and tasks declare only registered kinds."""

    def test_every_result_model_a_task_declares_is_a_registered_kind(self):
        for key, task in POSTPROCESSING_TASKS.items():
            for model in task.result_models:
                with self.subTest(task=key, model=model.__name__):
                    self.assertIs(schemas.ALGORITHM_RESULT_DATA_SCHEMAS.get(model.kind), model)

    def test_each_kind_is_registered_under_its_models_kind(self):
        for kind, model in schemas.ALGORITHM_RESULT_DATA_SCHEMAS.items():
            with self.subTest(kind):
                self.assertEqual(model.kind, kind)


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

    def test_merging_moves_every_result_to_the_kept_occurrence(self):
        other_algorithm = Algorithm.objects.create(name="Second size filter", key="size-filter-merge-test")
        absorbed = [Occurrence.objects.create(project=self.project, deployment=self.deployment) for _ in range(3)]

        def record(occurrence, algorithm, size):
            return AlgorithmResult.objects.record(
                occurrence=occurrence, algorithm=algorithm, kind=SIZE_FILTER, data={"relative_size": size}
            )

        kept_own = record(self.occurrence, self.algorithm, 0.01)
        moved_results = [
            record(absorbed[0], self.algorithm, 0.02),
            record(absorbed[0], self.algorithm, 0.03),
            record(absorbed[1], other_algorithm, 0.04),
            record(absorbed[2], other_algorithm, 0.05),
        ]

        moved = AlgorithmResult.objects.move_to_occurrence(self.occurrence, [o.pk for o in absorbed])

        self.assertEqual(moved, 4)
        self.assertEqual(
            set(AlgorithmResult.objects.filter(occurrence=self.occurrence).values_list("pk", flat=True)),
            {kept_own.pk, *(r.pk for r in moved_results)},
        )

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

    def test_results_cannot_be_moved_from_an_occurrence_of_another_project(self):
        other_project, other_deployment = setup_test_project(reuse=False)
        absorbed = Occurrence.objects.create(project=other_project, deployment=other_deployment)
        result = AlgorithmResult.objects.record(
            occurrence=absorbed, algorithm=self.algorithm, kind=SIZE_FILTER, data={"relative_size": 0.01}
        )
        with self.assertRaises(ValueError):
            AlgorithmResult.objects.move_to_occurrence(self.occurrence, [absorbed.pk])
        result.refresh_from_db()
        self.assertEqual((result.occurrence_id, result.project_id), (absorbed.pk, other_project.pk))
