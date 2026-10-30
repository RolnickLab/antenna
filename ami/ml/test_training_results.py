"""
What a retrain records about the occurrences it learned from.

Each verified occurrence in scope gets a ``classifier_training`` result saying whether it was
trained on, held out, or left out and why; the train and test splits are saved as occurrence
sets the registered version points at.
"""

from django.urls import reverse
from rest_framework.test import APIClient

from ami.jobs.models import Job, TrainClassifierJob
from ami.main.models import OccurrenceSet, TaxaList, Taxon, TaxonRank
from ami.ml.models import Algorithm, AlgorithmResult
from ami.ml.results.schemas import result_data_models
from ami.ml.test_training import TrainingSetFixture
from ami.ml.training import build_training_dataset, make_callback_token, split_for
from ami.ml.training.results import ClassifierTrainingResultData

KIND = ClassifierTrainingResultData.kind


class TrainingResultsFixture(TrainingSetFixture):
    def setUp(self) -> None:
        super().setUp()
        self.trained = [self.make_occurrence(self.taxa[i % 2]) for i in range(8)]
        self.job = Job.objects.create(
            project=self.project,
            name="Retrain",
            job_type_key=TrainClassifierJob.key,
            params={"algorithm_key": self.algorithm.key},
        )

    def build(self, **kwargs) -> dict:
        # Half held out: a handful of rows at the usual fifth can land entirely on one side.
        options = {"min_per_species": 1, "test_fraction": 0.5, **kwargs}
        return build_training_dataset(project=self.project, algorithm=self.algorithm, job=self.job, **options)

    def record(self, **kwargs) -> dict:
        dataset = self.build(**kwargs)
        TrainClassifierJob.record_training_set(job=self.job, algorithm=self.algorithm, dataset=dataset)
        self.job.save()
        return dataset

    def results(self) -> dict[int, AlgorithmResult]:
        return {r.occurrence_id: r for r in AlgorithmResult.objects.filter(job=self.job, kind=KIND)}


class TestTheKindIsRegistered(TrainingResultsFixture):
    def test_a_job_type_can_declare_a_result_kind(self):
        self.assertIs(result_data_models()[KIND], ClassifierTrainingResultData)


class TestEachOccurrenceIsRecorded(TrainingResultsFixture):
    def test_trained_and_held_out_occurrences_carry_their_split_and_label(self):
        self.record()

        results = self.results()
        self.assertEqual(set(results), {o.pk for o in self.trained})
        for occurrence in self.trained:
            data = results[occurrence.pk].data
            split = split_for(occurrence.pk, test_fraction=0.5)
            self.assertEqual(data["split"], split)
            self.assertEqual(data["used_for_training"], split == "train")
            self.assertFalse(data["rejected"])
            self.assertEqual(data["determination_before_id"], occurrence.determination_id)
            self.assertIsNone(results[occurrence.pk].value)
            self.assertEqual(results[occurrence.pk].algorithm_id, self.algorithm.pk)

    def test_occurrences_left_out_say_why(self):
        rare = Taxon.objects.create(name="Trainus rarus", rank=TaxonRank.SPECIES.name)
        too_few = self.make_occurrence(rare)
        no_vector = self.make_occurrence(self.taxa[0], with_vector=False)

        self.record(min_per_species=2)

        results = self.results()
        self.assertEqual(results[too_few.pk].data["reject_reason"], "below_min_per_species")
        self.assertEqual(results[no_vector.pk].data["reject_reason"], "no_embedding")
        for left_out in (too_few, no_vector):
            self.assertTrue(results[left_out.pk].data["rejected"])
            self.assertIsNone(results[left_out.pk].data["split"])
            self.assertFalse(results[left_out.pk].data["used_for_training"])

    def test_a_species_outside_the_taxa_list_is_left_out_for_that_reason(self):
        outsider = Taxon.objects.create(name="Trainus extraneus", rank=TaxonRank.SPECIES.name)
        stray = self.make_occurrence(outsider)
        taxa_list = TaxaList.objects.create(name="Kept species")
        taxa_list.taxa.set(self.taxa)

        self.record(taxa_list=taxa_list)

        self.assertEqual(self.results()[stray.pk].data["reject_reason"], "not_in_taxa_list")

    def test_a_rerun_of_the_job_replaces_its_own_records(self):
        self.record()
        self.record()

        self.assertEqual(AlgorithmResult.objects.filter(job=self.job, kind=KIND).count(), len(self.trained))
        self.assertEqual(OccurrenceSet.objects.filter(name__startswith=f"Job #{self.job.pk} ").count(), 2)


class TestTheSplitsAreSavedAsSets(TrainingResultsFixture):
    def test_the_train_and_test_sets_hold_exactly_their_split(self):
        self.record()

        sets = self.job.result["occurrence_sets"]
        for split in ("train", "test"):
            occurrence_set = OccurrenceSet.objects.get(pk=sets[split]["id"])
            expected = {o.pk for o in self.trained if split_for(o.pk, test_fraction=0.5) == split}
            self.assertEqual(set(occurrence_set.occurrences.values_list("pk", flat=True)), expected)
            self.assertEqual(occurrence_set.project, self.project)

    def test_a_held_out_set_can_be_trained_against_again(self):
        """The test set is a normal set: a later run in the project can name it."""
        self.record()
        test_set_id = self.job.result["occurrence_sets"]["test"]["id"]
        job = Job.objects.create(
            project=self.project,
            name="Again",
            job_type_key=TrainClassifierJob.key,
            params={"algorithm_key": self.algorithm.key, "occurrence_set_id": test_set_id},
        )

        self.assertEqual(TrainClassifierJob.target_occurrence_set(job).pk, test_set_id)


class TestTheResultFillsInTheRecords(TrainingResultsFixture):
    def _post(self, **result_overrides):
        dataset = self.job_dataset
        result = {
            "promote": True,
            "labels": [t.name for t in self.taxa],
            "rows": {"kept": dataset["metadata"].rows},
            "candidate_metrics": {"top1": 0.8},
            "trained_at": "2026-10-08T23:00:00",
            **result_overrides,
        }
        return APIClient().post(
            reverse("api:job-training-result", args=[self.job.pk]),
            {"result": result, "dataset": dataset["metadata"].dict()},
            format="json",
            HTTP_AUTHORIZATION=f"Token {make_callback_token(self.job)}",
        )

    def setUp(self) -> None:
        super().setUp()
        self.no_vector = self.make_occurrence(self.taxa[0], with_vector=False)
        self.job_dataset = self.record()

    def test_per_species_accuracy_becomes_each_results_value(self):
        alpha, beta = self.taxa

        response = self._post(species_train_accuracy={alpha.name: 0.75, beta.name: 1.0})

        self.assertEqual(response.status_code, 200, response.data)
        results = self.results()
        for occurrence in self.trained:
            expected = 0.75 if occurrence.determination_id == alpha.pk else 1.0
            self.assertEqual(results[occurrence.pk].value, expected)
            self.assertEqual(results[occurrence.pk].data["species_train_accuracy"], expected)
        # Left out of training, so the head's accuracy on its species says nothing about it.
        self.assertIsNone(results[self.no_vector.pk].value)

    def test_without_per_species_accuracy_the_value_stays_empty(self):
        response = self._post()

        self.assertEqual(response.status_code, 200, response.data)
        self.assertTrue(all(r.value is None for r in self.results().values()))

    def test_the_new_version_points_at_its_train_and_test_sets(self):
        sets = self.job.result["occurrence_sets"]

        response = self._post()

        version = Algorithm.objects.get(key=response.data["algorithm"])
        info = version.training_info
        self.assertEqual(info.train_occurrence_set_id, sets["train"]["id"])
        self.assertEqual(info.test_occurrence_set_id, sets["test"]["id"])
        self.assertEqual(info.test_occurrence_set_name, sets["test"]["name"])
        self.job.refresh_from_db()
        self.assertEqual(self.job.result["occurrence_sets"], sets)
