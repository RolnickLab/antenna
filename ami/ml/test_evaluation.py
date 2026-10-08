"""
Scoring an algorithm against a fixed set of occurrences.

The comparison is between what a person said and what the algorithm predicted, both of
which are already in the database, so these tests build classifications and identifications
directly rather than running a pipeline.
"""

import datetime

from django.test import TestCase
from rest_framework.test import APIRequestFactory, APITestCase

from ami.main.models import (
    Classification,
    Detection,
    Identification,
    OccurrenceSet,
    Project,
    SourceImage,
    TaxaList,
    Taxon,
    TaxonRank,
    update_occurrence_determination,
)
from ami.ml import reporting
from ami.ml.models import Algorithm, AlgorithmCategoryMap, AlgorithmEvaluation, TaxonEvaluation
from ami.ml.models.pipeline import get_or_create_algorithm_and_category_map
from ami.tests.fixtures.ml import ALGORITHM_CHOICES
from ami.users.models import User


class TestAlgorithmEvaluation(TestCase):
    """
    Scoring an algorithm against a fixed set of verified occurrences, so two models can be
    compared on identical data.
    """

    def setUp(self):
        self.project = Project.objects.create(name="Evaluation Project")
        self.user = User.objects.create_user(email="evaluator@example.com", password="testpass123")
        self.taxa = [Taxon.objects.create(name=f"Evaluus {n}", rank=TaxonRank.SPECIES.name) for n in ("alpha", "beta")]
        self.outsider_taxon = Taxon.objects.create(name="Outsideus ignotus", rank=TaxonRank.SPECIES.name)

        self.algorithm = get_or_create_algorithm_and_category_map(ALGORITHM_CHOICES["random-species-classifier"])
        self.category_map = AlgorithmCategoryMap.objects.create(
            labels=[t.name for t in self.taxa],
            data=[{"index": i, "label": t.name} for i, t in enumerate(self.taxa)],
            version="eval-test",
        )
        self.algorithm.category_map = self.category_map
        self.algorithm.save()

        self.occurrence_set = OccurrenceSet.objects.create(name="Blind set")
        self.occurrence_set.projects.add(self.project)

    def _occurrence(self, truth, predicted=None, index=0):
        """One verified occurrence, optionally with a prediction from the algorithm."""
        image = SourceImage.objects.create(
            path=f"ev{index}-{truth.pk}-2024010100{index:02d}00.jpg", project=self.project
        )
        detection = Detection.objects.create(source_image=image, bbox=[0, 0, 10, 10])
        occurrence = detection.associate_new_occurrence()
        Identification.objects.create(occurrence=occurrence, taxon=truth, user=self.user)
        if predicted:
            Classification.objects.create(
                detection=detection,
                taxon=predicted,
                algorithm=self.algorithm,
                score=0.9,
                timestamp=datetime.datetime.now(),
                category_map=self.category_map,
            )
        self.occurrence_set.occurrences.add(occurrence)
        return occurrence

    def test_a_perfect_run_scores_one(self):
        from ami.ml import evaluation

        for i, taxon in enumerate(self.taxa):
            self._occurrence(truth=taxon, predicted=taxon, index=i)

        result = evaluation.score(self.occurrence_set, self.algorithm)
        self.assertEqual(result["micro_accuracy"], 1.0)
        self.assertEqual(result["occurrences_scored"], 2)

    def test_a_wrong_prediction_lowers_the_score(self):
        from ami.ml import evaluation

        self._occurrence(truth=self.taxa[0], predicted=self.taxa[0], index=0)
        self._occurrence(truth=self.taxa[1], predicted=self.taxa[0], index=1)

        result = evaluation.score(self.occurrence_set, self.algorithm)
        self.assertEqual(result["micro_accuracy"], 0.5)

    def _unverified_occurrence(self, predicted, index=0):
        """One occurrence nobody has identified, carrying only this algorithm's prediction."""
        image = SourceImage.objects.create(
            path=f"un{index}-{predicted.pk}-2024010200{index:02d}00.jpg", project=self.project
        )
        detection = Detection.objects.create(source_image=image, bbox=[0, 0, 10, 10])
        occurrence = detection.associate_new_occurrence()
        Classification.objects.create(
            detection=detection,
            taxon=predicted,
            algorithm=self.algorithm,
            score=0.9,
            timestamp=datetime.datetime.now(),
            category_map=self.category_map,
        )
        # What Pipeline.save_results does for every detection it classifies
        # (ami/ml/models/pipeline.py). Without it the fallback never runs and the
        # occurrence would be skipped for having no determination at all.
        update_occurrence_determination(occurrence)
        self.occurrence_set.occurrences.add(occurrence)
        return occurrence

    def test_an_occurrence_nobody_identified_is_not_scored(self):
        """
        Without an identification the determination is the algorithm's own prediction, so
        scoring it would compare the algorithm against itself and always agree.
        """
        from ami.ml import evaluation

        unverified = self._unverified_occurrence(predicted=self.taxa[0], index=0)
        self._occurrence(truth=self.taxa[1], predicted=self.taxa[0], index=1)

        unverified.refresh_from_db()
        self.assertEqual(unverified.determination, self.taxa[0], "determination should fall back to the prediction")

        result = evaluation.score(self.occurrence_set, self.algorithm)
        self.assertEqual(result["occurrences_scored"], 1, "only the identified occurrence counts")
        self.assertEqual(result["micro_accuracy"], 0.0, "the one real comparison is wrong")

    def test_a_withdrawn_identification_does_not_count_as_verification(self):
        """Withdrawing an identification takes the occurrence back out of the scored set."""
        from ami.ml import evaluation

        self._occurrence(truth=self.taxa[0], predicted=self.taxa[0], index=0)
        withdrawn = self._occurrence(truth=self.taxa[1], predicted=self.taxa[1], index=1)
        withdrawn.identifications.update(withdrawn=True)

        result = evaluation.score(self.occurrence_set, self.algorithm)
        self.assertEqual(result["occurrences_scored"], 1)

    def test_a_label_matching_an_alternate_name_is_still_scored(self):
        """
        A category map label is the name the model was trained under. Matching it as text
        against the stored name drops the species; matching by taxon does not.
        """
        from ami.ml import evaluation

        renamed = Taxon.objects.create(
            name="Evaluus gamma",
            rank=TaxonRank.SPECIES.name,
            search_names=["Evaluus gamma", "Evaluus gamma Smith, 1899"],
        )
        self.category_map.labels = [*self.category_map.labels, "Evaluus gamma Smith, 1899"]
        self.category_map.data = [{"index": i, "label": label} for i, label in enumerate(self.category_map.labels)]
        self.category_map.save()

        self.assertIn(renamed.pk, evaluation.predictable_taxon_ids(self.algorithm))

        self._occurrence(truth=renamed, predicted=renamed, index=5)
        result = evaluation.score(self.occurrence_set, self.algorithm)
        self.assertEqual(result["occurrences_scored"], 1, "the renamed species is answerable, not skipped")
        self.assertEqual(result["occurrences_skipped"], 0)

    def test_the_score_reports_what_it_was_measured_over(self):
        """An accuracy over a few species reads the same as one over all of them."""
        from ami.ml import evaluation

        self._occurrence(truth=self.taxa[0], predicted=self.taxa[0], index=0)
        self._occurrence(truth=self.outsider_taxon, predicted=self.taxa[0], index=1)

        result = evaluation.score(self.occurrence_set, self.algorithm)
        self.assertEqual(result["species_scored"], 1)
        self.assertEqual(result["species_in_set"], 2, "both identified species count toward the set")
        self.assertEqual(result["species_predictable"], 2, "the two taxa in the category map")

    def test_species_the_algorithm_cannot_predict_are_left_out(self):
        """Counting those wrong would punish a regional head for a question nobody asked it."""
        from ami.ml import evaluation

        self._occurrence(truth=self.taxa[0], predicted=self.taxa[0], index=0)
        self._occurrence(truth=self.outsider_taxon, predicted=self.taxa[0], index=1)

        result = evaluation.score(self.occurrence_set, self.algorithm)
        self.assertEqual(result["occurrences_scored"], 1)
        self.assertEqual(result["occurrences_skipped"], 1)
        self.assertEqual(result["micro_accuracy"], 1.0)

    def test_the_per_species_average_differs_from_the_plain_share(self):
        """Long-tailed data: one common species must not hide failure on a rare one."""
        from ami.ml import evaluation

        for i in range(4):
            self._occurrence(truth=self.taxa[0], predicted=self.taxa[0], index=i)
        self._occurrence(truth=self.taxa[1], predicted=self.taxa[0], index=9)

        result = evaluation.score(self.occurrence_set, self.algorithm)
        self.assertEqual(result["micro_accuracy"], 0.8)
        self.assertEqual(result["macro_accuracy"], 0.5)

    def test_an_algorithm_that_never_ran_says_so(self):
        """A missing step should read as a missing step, not an accuracy of zero."""
        from ami.ml import evaluation

        self._occurrence(truth=self.taxa[0], predicted=None, index=0)
        with self.assertRaises(evaluation.NothingToScore):
            evaluation.score(self.occurrence_set, self.algorithm)

    def test_results_are_stored_per_species(self):
        from ami.ml import evaluation

        self._occurrence(truth=self.taxa[0], predicted=self.taxa[0], index=0)
        self._occurrence(truth=self.taxa[1], predicted=self.taxa[0], index=1)

        result = evaluation.score(self.occurrence_set, self.algorithm)
        stored = evaluation.save_evaluation(self.occurrence_set, self.algorithm, result)

        self.assertEqual(stored.micro_accuracy, 0.5)
        self.assertEqual(stored.taxa.count(), 2)
        self.assertEqual(stored.taxa.get(taxon=self.taxa[0]).accuracy, 1.0)
        self.assertEqual(stored.taxa.get(taxon=self.taxa[1]).accuracy, 0.0)

    def test_scoring_again_replaces_the_earlier_result(self):
        """A second run over the same set is a correction, not a new fact."""
        from ami.ml import evaluation

        self._occurrence(truth=self.taxa[0], predicted=self.taxa[0], index=0)
        result = evaluation.score(self.occurrence_set, self.algorithm)
        evaluation.save_evaluation(self.occurrence_set, self.algorithm, result)
        evaluation.save_evaluation(self.occurrence_set, self.algorithm, result)

        self.assertEqual(
            AlgorithmEvaluation.objects.filter(algorithm=self.algorithm, occurrence_set=self.occurrence_set).count(),
            1,
        )

    def test_a_set_with_no_project_is_global(self):
        """One set can compare models across projects."""
        shared = OccurrenceSet.objects.create(name="Shared across projects")
        self.assertTrue(shared.is_global)
        self.assertFalse(self.occurrence_set.is_global)
        self.assertIn(shared, OccurrenceSet.objects.for_project(self.project))


class TestEvaluationsAreNotExposedAcrossProjects(TestCase):
    """
    An evaluation names the set it ran on and how the model scored. Sets belong to
    projects, so those names and numbers are project data.

    Scoping by project only helps when a project is named and when the caller may see it.
    Neither held: with no project the read was unfiltered, and a named project was loaded
    by id without checking the caller could see it, so a draft project's id worked.
    """

    def setUp(self):
        self.user = User.objects.create_user(email="outsider@example.com", password="testpass123")
        self.algorithm = Algorithm.objects.create(name="Shared model", key="shared-model")

        self.taxon = Taxon.objects.create(name="Exposus taxon", rank=TaxonRank.SPECIES.name)

        self.global_set = OccurrenceSet.objects.create(name="Platform-wide set")
        self.their_project = Project.objects.create(name="Someone Else's Project", draft=True)
        self.their_set = OccurrenceSet.objects.create(name="Their private set")
        self.their_set.projects.add(self.their_project)

        for occurrence_set in (self.global_set, self.their_set):
            evaluation = AlgorithmEvaluation.objects.create(
                algorithm=self.algorithm,
                occurrence_set=occurrence_set,
                micro_accuracy=0.9,
                macro_accuracy=0.9,
                occurrences_scored=10,
                species_scored=1,
            )
            TaxonEvaluation.objects.create(
                evaluation=evaluation, taxon=self.taxon, accuracy=0.9, occurrences_scored=10, correct=9
            )

    def _request_naming(self, project):
        """A DRF request, since get_active_project reads request.data."""
        from rest_framework.request import Request

        request = Request(APIRequestFactory().get("/", {"project_id": project.pk}))
        request.user = self.user
        return request

    def test_without_a_project_only_the_global_sets_are_shown(self):
        """No project named must mean the platform-wide sets, not every project's."""
        names = [row["occurrence_set"]["name"] for row in reporting.latest_evaluations(self.algorithm)]

        self.assertIn(self.global_set.name, names)
        self.assertNotIn(self.their_set.name, names)

    def test_a_taxon_without_a_project_shows_only_the_global_sets(self):
        names = [row["occurrence_set"]["name"] for row in reporting.performance_for_taxon(self.taxon)]

        self.assertIn(self.global_set.name, names)
        self.assertNotIn(self.their_set.name, names)

    def test_a_member_sees_their_own_project_s_scores_without_naming_it(self):
        """
        The algorithm detail route carries no project id. Scoping that read to the global
        sets alone hid every score a project had recorded, which is the whole evaluations
        table on the algorithm page. Falling back to what the user may see restores it
        without widening the read to other projects.
        """
        mine = Project.objects.create(name="My Project")
        mine.members.add(self.user)
        my_set = OccurrenceSet.objects.create(name="My project's set")
        my_set.projects.add(mine)
        AlgorithmEvaluation.objects.create(
            algorithm=self.algorithm,
            occurrence_set=my_set,
            micro_accuracy=0.7,
            macro_accuracy=0.7,
            occurrences_scored=5,
            species_scored=1,
        )

        names = [row["occurrence_set"]["name"] for row in reporting.latest_evaluations(self.algorithm, user=self.user)]

        self.assertIn(my_set.name, names, "a member's own project scores must show without a project id")
        self.assertIn(self.global_set.name, names)
        self.assertNotIn(self.their_set.name, names, "another project's draft set still stays hidden")

    def test_a_project_the_caller_cannot_see_is_not_used(self):
        """A draft project's id is loaded by the helper without a visibility check."""
        request = self._request_naming(self.their_project)

        project = reporting.project_for(request)

        self.assertIsNone(project)

    def test_a_project_the_caller_can_see_is_used(self):
        self.their_project.members.add(self.user)

        self.assertEqual(reporting.project_for(self._request_naming(self.their_project)), self.their_project)

    def test_no_request_means_no_project(self):
        """This serializer is nested in responses that do not carry a request."""
        self.assertIsNone(reporting.project_for(None))


class TestTaxaListQueryCount(APITestCase):
    """
    Guard against an N+1 on the taxa-lists page.

    best_model is a per-row lookup, which is the shape that silently turns a page of lists
    into one query each. A multi-row fixture is the only way to see it: with a single list
    an N+1 and a flat query look identical.
    """

    def setUp(self):
        self.project = Project.objects.create(name="Query Count Project")
        self.user = User.objects.create_user(email="qcount-lists@example.com", password="testpass123")
        self.project.members.add(self.user)
        self.client.force_authenticate(user=self.user)

        self.taxon = Taxon.objects.create(name="Countus communis", rank=TaxonRank.SPECIES.name)
        algorithm = Algorithm.objects.create(name="Scored model", key="scored-model")
        occurrence_set = OccurrenceSet.objects.create(name="Query count set")
        evaluation = AlgorithmEvaluation.objects.create(
            algorithm=algorithm,
            occurrence_set=occurrence_set,
            micro_accuracy=0.9,
            macro_accuracy=0.9,
            occurrences_scored=10,
            species_scored=1,
        )
        TaxonEvaluation.objects.create(
            evaluation=evaluation, taxon=self.taxon, accuracy=0.9, occurrences_scored=10, correct=9
        )
        self._add_list("First list")

    def _add_list(self, name: str) -> None:
        taxa_list = TaxaList.objects.create(name=name)
        taxa_list.taxa.set([self.taxon])
        taxa_list.projects.add(self.project)

    def _evaluation_queries(self) -> int:
        """How many times a page of lists asks the evaluation tables anything."""
        from django.core.cache import caches
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        url = f"/api/v2/taxa/lists/?project_id={self.project.pk}&limit=100"
        # A warm cachalot cache hides query-scaling regressions, so start cold.
        caches["default"].clear()
        with CaptureQueriesContext(connection) as ctx:
            response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        return len([q for q in ctx.captured_queries if "algorithmevaluation" in q["sql"].lower()])

    def test_the_endpoint_reports_the_best_model(self):
        """
        Guards the other half of the annotation: read from a field the viewset forgot to
        attach, best_model would quietly go null with the query count still flat.
        """
        response = self.client.get(f"/api/v2/taxa/lists/?project_id={self.project.pk}")
        best = response.json()["results"][0]["best_model"]

        self.assertIsNotNone(best, "best_model is null; the viewset is not annotating it")
        self.assertEqual(best["name"], "Scored model")
        self.assertAlmostEqual(best["accuracy_by_species"], 0.9)
        self.assertEqual(best["occurrence_set"], "Query count set")

    def test_best_model_does_not_query_once_per_taxa_list(self):
        one_list = self._evaluation_queries()

        for n in range(5):
            self._add_list(f"List {n}")

        six_lists = self._evaluation_queries()

        self.assertEqual(
            six_lists,
            one_list,
            f"Evaluation queries grew with the number of taxa lists: {one_list} -> {six_lists} "
            "(best_model is being looked up per row)",
        )


class TestPerformanceReporting(TestCase):
    """
    The numbers the model-performance screens read: the best model for a taxa list, and how
    each algorithm has done on one species.
    """

    def setUp(self):
        self.project = Project.objects.create(name="Reporting Project")
        self.user = User.objects.create_user(email="reporter@example.com", password="testpass123")
        self.common = Taxon.objects.create(name="Reportus communis", rank=TaxonRank.SPECIES.name)
        self.rare = Taxon.objects.create(name="Reportus rarus", rank=TaxonRank.SPECIES.name)
        self.taxa_list = TaxaList.objects.create(name="Reporting list")
        self.taxa_list.taxa.set([self.common, self.rare])
        self.taxa_list.projects.add(self.project)
        self.occurrence_set = OccurrenceSet.objects.create(name="Reporting set")

    def _algorithm(self, key: str) -> Algorithm:
        return Algorithm.objects.create(name=key, key=key)

    def _evaluation(self, algorithm: Algorithm, micro: float, macro: float, per_taxon: dict) -> AlgorithmEvaluation:
        evaluation = AlgorithmEvaluation.objects.create(
            algorithm=algorithm,
            occurrence_set=self.occurrence_set,
            micro_accuracy=micro,
            macro_accuracy=macro,
            occurrences_scored=sum(scored for _, scored in per_taxon.values()),
            species_scored=len(per_taxon),
        )
        for taxon, (correct, scored) in per_taxon.items():
            TaxonEvaluation.objects.create(
                evaluation=evaluation,
                taxon=taxon,
                accuracy=correct / scored,
                occurrences_scored=scored,
                correct=correct,
            )
        return evaluation

    def _other_project_evaluation(self):
        """An evaluation belonging to a different, private project, scoring the same taxa."""
        other = Project.objects.create(name="Someone Else's Project", draft=True)
        their_set = OccurrenceSet.objects.create(name="Their private blind set")
        their_set.projects.add(other)
        algorithm = self._algorithm("their-model")
        evaluation = AlgorithmEvaluation.objects.create(
            algorithm=algorithm,
            occurrence_set=their_set,
            micro_accuracy=0.99,
            macro_accuracy=0.99,
            occurrences_scored=50,
            species_scored=2,
        )
        for taxon in (self.common, self.rare):
            TaxonEvaluation.objects.create(
                evaluation=evaluation, taxon=taxon, accuracy=0.99, occurrences_scored=25, correct=24
            )
        return evaluation

    def test_a_species_does_not_show_another_project_s_evaluations(self):
        """
        Taxa are shared across projects, evaluation sets are not.

        Without scoping, a species page lists every evaluation that happened to score that
        taxon anywhere on the platform, exposing another project's set name and numbers.
        """
        self._other_project_evaluation()
        mine = self._evaluation(self._algorithm("my-model"), micro=0.5, macro=0.5, per_taxon={self.common: (5, 10)})

        rows = reporting.performance_for_taxon(self.common, project=self.project)

        self.assertEqual([r["algorithm"]["id"] for r in rows], [mine.algorithm_id])

    def test_a_taxa_list_s_best_model_ignores_another_project_s_evaluation(self):
        """Their model scores higher, but it was never scored on anything this project can see."""
        self._other_project_evaluation()
        mine = self._evaluation(self._algorithm("my-model"), micro=0.5, macro=0.5, per_taxon={self.common: (5, 10)})

        best = reporting.best_evaluation_for_taxa_list(self.taxa_list, project=self.project)

        self.assertEqual(best, mine)

    def test_an_algorithm_panel_shows_only_sets_this_project_can_see(self):
        theirs = self._other_project_evaluation()

        rows = reporting.latest_evaluations(theirs.algorithm, project=self.project)

        self.assertEqual(rows, [])

    def test_a_global_set_is_visible_to_every_project(self):
        """A set with no project is the platform-wide benchmark, so it must not be filtered out."""
        mine = self._evaluation(self._algorithm("my-model"), micro=0.5, macro=0.5, per_taxon={self.common: (5, 10)})

        rows = reporting.performance_for_taxon(self.common, project=self.project)

        # self.occurrence_set belongs to no project, so it is global.
        self.assertEqual([r["algorithm"]["id"] for r in rows], [mine.algorithm_id])

    def test_the_best_model_is_the_one_that_handles_the_rare_species(self):
        """Ranked on the per-species average, or a model that only knows the common one wins."""
        from ami.ml import reporting

        self._evaluation(self._algorithm("common-only"), micro=0.9, macro=0.5, per_taxon={self.common: (9, 10)})
        even = self._evaluation(
            self._algorithm("handles-both"),
            micro=0.8,
            macro=0.8,
            per_taxon={self.common: (8, 10), self.rare: (8, 10)},
        )

        self.assertEqual(reporting.best_evaluation_for_taxa_list(self.taxa_list), even)

    def test_a_list_nothing_has_been_scored_on_has_no_best_model(self):
        from ami.ml import reporting

        self.assertIsNone(reporting.best_evaluation_for_taxa_list(self.taxa_list))

    def test_a_species_lists_every_algorithm_scored_on_it(self):
        from ami.ml import reporting

        self._evaluation(self._algorithm("first"), micro=1.0, macro=1.0, per_taxon={self.rare: (2, 2)})
        self._evaluation(self._algorithm("second"), micro=0.5, macro=0.5, per_taxon={self.rare: (1, 2)})

        rows = reporting.performance_for_taxon(self.rare)
        self.assertEqual([row["algorithm"]["key"] for row in rows], ["first", "second"])
        self.assertEqual([row["accuracy"] for row in rows], [1.0, 0.5])
        self.assertEqual(rows[0]["occurrence_set"]["name"], self.occurrence_set.name)

    def test_a_species_nothing_has_been_scored_on_lists_nothing(self):
        from ami.ml import reporting

        self.assertEqual(reporting.performance_for_taxon(self.common), [])

    def test_an_algorithm_lists_its_own_scores(self):
        from ami.ml import reporting

        algorithm = self._algorithm("scored-twice")
        self._evaluation(algorithm, micro=1.0, macro=1.0, per_taxon={self.common: (2, 2)})
        other_set = OccurrenceSet.objects.create(name="Second set")
        AlgorithmEvaluation.objects.create(
            algorithm=algorithm,
            occurrence_set=other_set,
            micro_accuracy=0.5,
            macro_accuracy=0.5,
            occurrences_scored=2,
            species_scored=1,
        )

        rows = reporting.latest_evaluations(algorithm)
        self.assertEqual({row["occurrence_set"]["name"] for row in rows}, {"Reporting set", "Second set"})
        self.assertEqual(len(reporting.latest_evaluations(algorithm, limit=1)), 1)

    def test_the_algorithms_list_does_not_query_per_row(self):
        """Evaluations are prefetched: adding scored algorithms must not add queries."""
        from django.core.cache import caches
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        from ami.ml.models import Pipeline, ProcessingService, ProjectPipelineConfig

        service = ProcessingService.objects.create(name="Reporting service", endpoint_url="http://example.com")
        service.projects.add(self.project)
        pipeline = Pipeline.objects.create(name="Reporting pipeline", slug="reporting-pipeline")
        pipeline.projects.add(self.project)
        ProjectPipelineConfig.objects.update_or_create(
            project=self.project, pipeline=pipeline, defaults={"enabled": True}
        )

        self.client.force_login(self.user)
        url = f"/api/v2/ml/algorithms/?project_id={self.project.pk}"

        def query_count() -> int:
            # Cold cache on both runs, or a warm one hides the scaling.
            caches["default"].clear()
            with CaptureQueriesContext(connection) as ctx:
                res = self.client.get(url)
            self.assertEqual(res.status_code, 200)
            return len(ctx.captured_queries)

        for index in range(2):
            algorithm = self._algorithm(f"listed-{index}")
            pipeline.algorithms.add(algorithm)
            self._evaluation(algorithm, micro=1.0, macro=1.0, per_taxon={self.common: (1, 1)})
        two_algorithms = query_count()

        for index in range(2, 6):
            algorithm = self._algorithm(f"listed-{index}")
            pipeline.algorithms.add(algorithm)
            self._evaluation(algorithm, micro=1.0, macro=1.0, per_taxon={self.common: (1, 1)})
        six_algorithms = query_count()

        self.assertLessEqual(six_algorithms, two_algorithms)
