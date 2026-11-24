"""Domain tests for the class masking post-processing task.

Class masking re-scores a classifier's terminal predictions against a taxa list:
classes whose taxon is not in the list are down-weighted (removed at weight 0),
the softmax is renormalised, and a new terminal classification (linked back via
``applied_to``) records the result. These tests cover the masking maths (a hard
mask never lets an excluded class win; a soft mask lets a confident one through),
the provenance link, the persisted output algorithm, and both admin scopes
(collection / single occurrence) end to end through ``ClassMaskingTask.run()``.

Tests that pin a hard-mask outcome pass ``out_of_list_weight=0.0`` themselves, so
they do not depend on the default weight.
"""
import datetime
import io
import math
import pathlib
import uuid
from unittest import mock

from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.db.models import QuerySet
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from ami.main.models import (
    Classification,
    Detection,
    Occurrence,
    SourceImage,
    SourceImageCollection,
    TaxaList,
    Taxon,
    TaxonRank,
    group_images_into_events,
)
from ami.ml.models import Algorithm, AlgorithmCategoryMap, AlgorithmResult
from ami.ml.models.algorithm import AlgorithmTaskType
from ami.ml.post_processing.class_masking import (
    DEFAULT_OUT_OF_LIST_WEIGHT,
    ClassMaskingTask,
    _weight_token,
    make_classifications_filtered_by_taxa_list,
)
from ami.tests.fixtures.main import create_taxa, setup_test_project


def _softmax(logits: list[float]) -> list[float]:
    shifted = [x - max(logits) for x in logits]
    exp = [math.exp(x) for x in shifted]
    total = sum(exp)
    return [e / total for e in exp]


class TestPostProcessingClassMasking(TestCase):
    def setUp(self):
        self.project, self.deployment = setup_test_project()
        create_taxa(project=self.project)
        self._create_images_with_dimensions(deployment=self.deployment)
        group_images_into_events(deployment=self.deployment)

        self.collection = SourceImageCollection.objects.create(
            name="Test PostProcessing Collection",
            project=self.project,
            method="manual",
            kwargs={"image_ids": list(self.deployment.captures.values_list("pk", flat=True))},
        )
        self.collection.populate_sample()

        self.species_taxon = Taxon.objects.filter(rank=TaxonRank.SPECIES.name).first()
        self.genus_taxon = self.species_taxon.parent if self.species_taxon else None
        self.assertIsNotNone(self.species_taxon)
        self.assertIsNotNone(self.genus_taxon)
        self.algorithm = self._create_category_map_with_algorithm()
        self.species_taxa = list(self.project.taxa.filter(rank=TaxonRank.SPECIES.name).order_by("name")[:3])

    # ----- fixtures -------------------------------------------------------

    def _create_images_with_dimensions(self, deployment, num_images=5, width=640, height=480):
        base_time = datetime.datetime.now(datetime.timezone.utc)
        for i in range(num_images):
            path = pathlib.Path("test") / f"{uuid.uuid4().hex[:8]}_{i}.jpg"
            SourceImage.objects.create(
                deployment=deployment,
                project=deployment.project,
                timestamp=base_time + datetime.timedelta(minutes=i * 5),
                path=path,
                width=width,
                height=height,
            )
        deployment.save(update_calculated_fields=True, regroup_async=False)

    def _create_category_map_with_algorithm(self) -> Algorithm:
        species_taxa = list(self.project.taxa.filter(rank=TaxonRank.SPECIES.name).order_by("name")[:3])
        assert species_taxa, "No species taxa found in project; run create_taxa() first."
        data = [{"index": i, "label": taxon.name} for i, taxon in enumerate(species_taxa)]
        category_map = AlgorithmCategoryMap.objects.create(
            data=data,
            labels=[item["label"] for item in data],
            version="v1.0",
            description="Species-level category map for testing",
        )
        return Algorithm.objects.create(
            name="Test Species Classifier",
            task_type=AlgorithmTaskType.CLASSIFICATION.value,
            category_map=category_map,
        )

    def _create_classification_with_logits(self, detection, taxon, scores, logits) -> Classification:
        return Classification.objects.create(
            detection=detection,
            taxon=taxon,
            score=max(scores),
            scores=scores,
            logits=logits,
            terminal=True,
            timestamp=datetime.datetime.now(datetime.timezone.utc),
            algorithm=self.algorithm,
        )

    def _detection_with_occurrence(self) -> tuple[Detection, Occurrence]:
        det = Detection.objects.create(source_image=self.collection.images.first(), bbox=[0, 0, 200, 200])
        occ = Occurrence.objects.create(project=self.project, event=self.deployment.events.first())
        occ.detections.add(det)
        return det, occ

    # ----- make_classifications_filtered_by_taxa_list ---------------------

    def test_excluded_class_never_wins_even_with_highest_logit(self):
        """The hard-mask guarantee: at weight 0 a masked class cannot be selected, even
        if it had the single highest logit before masking."""
        # index 2 (excluded) has the highest logit, so it is the original top.
        logits = [2.0, 1.0, 5.0]
        scores = _softmax(logits)
        self.assertEqual(scores.index(max(scores)), 2)

        taxa_list = TaxaList.objects.create(name="Keep first two")
        taxa_list.taxa.set(self.species_taxa[:2])  # excludes species_taxa[2]

        det, _ = self._detection_with_occurrence()
        original = self._create_classification_with_logits(det, self.species_taxa[2], scores, logits)

        new_algorithm = Algorithm.objects.create(
            name="masked",
            key="masked_test",
            task_type=AlgorithmTaskType.CLASSIFICATION.value,
            category_map=self.algorithm.category_map,
        )
        metrics = make_classifications_filtered_by_taxa_list(
            classifications=Classification.objects.filter(pk=original.pk),
            taxa_list=taxa_list,
            algorithm=self.algorithm,
            new_algorithm=new_algorithm,
            out_of_list_weight=0.0,
        )

        original.refresh_from_db()
        self.assertFalse(original.terminal, "Source classification is demoted to non-terminal")
        new_clf = Classification.objects.get(detection=det, terminal=True)
        # Highest logit among the kept classes is index 0.
        self.assertEqual(new_clf.taxon, self.species_taxa[0])
        self.assertAlmostEqual(new_clf.scores[2], 0.0, places=10, msg="Masked class score is exactly zero")
        self.assertAlmostEqual(sum(new_clf.scores), 1.0, places=5)
        self.assertEqual(new_clf.applied_to, original, "Provenance links back to the source classification")
        self.assertEqual(metrics["classifications_masked"], 1)

    def test_single_allowed_class_gets_all_probability(self):
        logits = [2.0, 3.0, 4.0]
        taxa_list = TaxaList.objects.create(name="Keep one")
        taxa_list.taxa.set([self.species_taxa[0]])

        det, _ = self._detection_with_occurrence()
        self._create_classification_with_logits(det, self.species_taxa[2], _softmax(logits), logits)

        new_algorithm = Algorithm.objects.create(
            name="masked2",
            key="masked_test2",
            task_type=AlgorithmTaskType.CLASSIFICATION.value,
            category_map=self.algorithm.category_map,
        )
        make_classifications_filtered_by_taxa_list(
            classifications=Classification.objects.filter(detection=det, terminal=True),
            taxa_list=taxa_list,
            algorithm=self.algorithm,
            new_algorithm=new_algorithm,
            out_of_list_weight=0.0,
        )
        new_clf = Classification.objects.get(detection=det, terminal=True)
        self.assertAlmostEqual(new_clf.scores[0], 1.0, places=5)
        self.assertAlmostEqual(new_clf.scores[1], 0.0, places=10)
        self.assertAlmostEqual(new_clf.scores[2], 0.0, places=10)

    def test_no_change_when_all_classes_in_list(self):
        logits = [3.0, 1.0, 0.5]
        taxa_list = TaxaList.objects.create(name="Keep all")
        taxa_list.taxa.set(self.species_taxa)

        det, _ = self._detection_with_occurrence()
        original = self._create_classification_with_logits(det, self.species_taxa[0], _softmax(logits), logits)

        new_algorithm = Algorithm.objects.create(
            name="masked3",
            key="masked_test3",
            task_type=AlgorithmTaskType.CLASSIFICATION.value,
            category_map=self.algorithm.category_map,
        )
        make_classifications_filtered_by_taxa_list(
            classifications=Classification.objects.filter(pk=original.pk),
            taxa_list=taxa_list,
            algorithm=self.algorithm,
            new_algorithm=new_algorithm,
        )
        original.refresh_from_db()
        self.assertTrue(original.terminal, "Nothing masked, so the source stays terminal")
        self.assertEqual(Classification.objects.filter(detection=det).count(), 1, "No new classification created")

    def test_all_classes_excluded_raises(self):
        # A taxa list sharing nothing with the category map leaves no class to keep.
        taxa_list = TaxaList.objects.create(name="Unrelated")
        taxa_list.taxa.set([self.genus_taxon])  # genus name is not a category-map label

        det, _ = self._detection_with_occurrence()
        logits = [2.0, 1.0, 5.0]
        self._create_classification_with_logits(det, self.species_taxa[2], _softmax(logits), logits)

        new_algorithm = Algorithm.objects.create(
            name="masked4",
            key="masked_test4",
            task_type=AlgorithmTaskType.CLASSIFICATION.value,
            category_map=self.algorithm.category_map,
        )
        with self.assertRaises(ValueError):
            make_classifications_filtered_by_taxa_list(
                classifications=Classification.objects.filter(detection=det, terminal=True),
                taxa_list=taxa_list,
                algorithm=self.algorithm,
                new_algorithm=new_algorithm,
            )

    # ----- ClassMaskingTask.run() end to end ------------------------------

    def test_task_run_collection_scope_persists_masking_algorithm(self):
        logits = [0.5, 3.0, 3.5]  # excluded index 2 is top; index 1 is the in-list winner
        taxa_list = TaxaList.objects.create(name="Regional list")
        taxa_list.taxa.set(self.species_taxa[:2])

        det, occ = self._detection_with_occurrence()
        original = self._create_classification_with_logits(det, self.species_taxa[2], _softmax(logits), logits)

        ClassMaskingTask(
            source_image_collection_id=self.collection.pk,
            taxa_list_id=taxa_list.pk,
            algorithm_id=self.algorithm.pk,
            out_of_list_weight=0.0,
        ).run()

        # The hard mask's per-(source algorithm, taxa list, reweight mode) masking
        # algorithm exists and kept its category map (the bug being guarded: it used
        # to be set in memory only). Default reweight=True → the "reweighted" mode.
        masking_algo = Algorithm.objects.get(
            key=f"{self.algorithm.key}_filtered_by_taxa_list_{taxa_list.pk}_reweighted"
        )
        self.assertIsNotNone(masking_algo.category_map_id)
        self.assertEqual(masking_algo.category_map_id, self.algorithm.category_map_id)

        new_clf = Classification.objects.get(detection=det, terminal=True, algorithm=masking_algo)
        self.assertEqual(new_clf.taxon, self.species_taxa[1])
        self.assertEqual(new_clf.applied_to, original)
        occ.refresh_from_db()
        self.assertEqual(occ.determination, self.species_taxa[1], "Occurrence determination follows the masked result")

    def test_task_run_records_the_job_on_new_classifications_only(self):
        from ami.jobs.models import Job

        logits = [0.5, 3.0, 3.5]
        taxa_list = TaxaList.objects.create(name="Regional list")
        taxa_list.taxa.set(self.species_taxa[:2])
        det, _ = self._detection_with_occurrence()
        original = self._create_classification_with_logits(det, self.species_taxa[2], _softmax(logits), logits)
        job = Job.objects.create(project=self.project, name="Class masking job test", job_type_key="post_processing")
        job.progress.add_stage("Post Processing", key="post_processing")
        job.save()

        ClassMaskingTask(
            job=job,
            source_image_collection_id=self.collection.pk,
            taxa_list_id=taxa_list.pk,
            algorithm_id=self.algorithm.pk,
        ).run()

        new_clf = Classification.objects.get(detection=det, terminal=True, applied_to=original)
        self.assertEqual(new_clf.job_id, job.pk)
        original.refresh_from_db()
        self.assertIsNone(original.job_id, "The source classification keeps the job it had")

    def test_rerun_does_not_duplicate_masked_classifications(self):
        """Re-running the same mask must not create a second masked classification for
        a source already re-scored, even if that source became terminal again in between.

        Idempotency is keyed on the ``applied_to`` lineage — a source is masked at most
        once per masking algorithm — not on the terminal flag. This makes it safe to
        finish a partially completed run (e.g. one the health-check reaper revoked) or
        to re-run after a re-classification / dedup pass re-terminalized a source.
        """
        logits = [0.5, 3.0, 3.5]  # excluded index 2 is top; index 1 is the in-list winner
        taxa_list = TaxaList.objects.create(name="Idempotency list")
        taxa_list.taxa.set(self.species_taxa[:2])

        det, _ = self._detection_with_occurrence()
        original = self._create_classification_with_logits(det, self.species_taxa[2], _softmax(logits), logits)

        def run():
            ClassMaskingTask(
                source_image_collection_id=self.collection.pk,
                taxa_list_id=taxa_list.pk,
                algorithm_id=self.algorithm.pk,
                out_of_list_weight=0.0,
            ).run()

        run()
        masking_algo = Algorithm.objects.get(
            key=f"{self.algorithm.key}_filtered_by_taxa_list_{taxa_list.pk}_reweighted"
        )
        self.assertEqual(
            Classification.objects.filter(algorithm=masking_algo, applied_to=original).count(),
            1,
            "First run masks the source exactly once",
        )

        # Simulate the source becoming terminal again (a dedup or re-classification pass)
        # while its masked child still exists. The terminal filter alone would re-select
        # it; the applied_to guard must still skip it.
        original.refresh_from_db()
        original.terminal = True
        original.save(update_fields=["terminal"])

        run()
        self.assertEqual(
            Classification.objects.filter(algorithm=masking_algo, applied_to=original).count(),
            1,
            "Re-run must not create a duplicate masked classification for an already-masked source",
        )

    def test_reweight_modes_get_distinct_masking_algorithms(self):
        """The reweight mode is part of a hard mask's algorithm identity.

        reweight=True and reweight=False persist different score semantics
        (renormalised vs original absolute), so they must resolve to different
        Algorithm rows — otherwise a masked classification's
        ``applied_to.algorithm`` could not tell which mode produced it. Both keys
        derive from the same (source algorithm, taxa list); only the mode suffix
        differs.
        """
        logits = [0.5, 3.0, 3.5]
        taxa_list = TaxaList.objects.create(name="Reweight identity list")
        taxa_list.taxa.set(self.species_taxa[:2])

        det_t, _ = self._detection_with_occurrence()
        self._create_classification_with_logits(det_t, self.species_taxa[2], _softmax(logits), logits)
        ClassMaskingTask(
            source_image_collection_id=self.collection.pk,
            taxa_list_id=taxa_list.pk,
            algorithm_id=self.algorithm.pk,
            reweight=True,
            out_of_list_weight=0.0,
        ).run()

        det_f, _ = self._detection_with_occurrence()
        self._create_classification_with_logits(det_f, self.species_taxa[2], _softmax(logits), logits)
        ClassMaskingTask(
            source_image_collection_id=self.collection.pk,
            taxa_list_id=taxa_list.pk,
            algorithm_id=self.algorithm.pk,
            reweight=False,
            out_of_list_weight=0.0,
        ).run()

        base = f"{self.algorithm.key}_filtered_by_taxa_list_{taxa_list.pk}"
        reweighted = Algorithm.objects.get(key=f"{base}_reweighted")
        absolute = Algorithm.objects.get(key=f"{base}_absolute")
        self.assertNotEqual(reweighted.pk, absolute.pk, "Each reweight mode gets its own masking algorithm")

        # Each detection's masked classification points at the algorithm for its mode.
        self.assertTrue(Classification.objects.filter(detection=det_t, terminal=True, algorithm=reweighted).exists())
        self.assertTrue(Classification.objects.filter(detection=det_f, terminal=True, algorithm=absolute).exists())

    def test_task_run_occurrence_scope(self):
        logits = [2.0, 1.0, 5.0]
        taxa_list = TaxaList.objects.create(name="Occ scope list")
        taxa_list.taxa.set(self.species_taxa[:2])

        det, occ = self._detection_with_occurrence()
        self._create_classification_with_logits(det, self.species_taxa[2], _softmax(logits), logits)

        ClassMaskingTask(
            occurrence_id=occ.pk,
            taxa_list_id=taxa_list.pk,
            algorithm_id=self.algorithm.pk,
            out_of_list_weight=0.0,
        ).run()

        new_clf = Classification.objects.filter(detection=det, terminal=True).exclude(algorithm=self.algorithm).first()
        self.assertIsNotNone(new_clf)
        self.assertEqual(new_clf.taxon, self.species_taxa[0])

    # ----- algorithm results -----------------------------------------------

    def _masking_fixture(self, name: str = "History list") -> tuple[TaxaList, Detection, Occurrence]:
        """One occurrence whose top class (index 2) the taxa list excludes, so masking re-scores it."""
        logits = [2.0, 1.0, 5.0]
        taxa_list = TaxaList.objects.create(name=name)
        taxa_list.taxa.set(self.species_taxa[:2])
        det, occ = self._detection_with_occurrence()
        self._create_classification_with_logits(det, self.species_taxa[2], _softmax(logits), logits)
        occ.save()
        return taxa_list, det, occ

    def test_a_rescored_occurrence_gets_one_result_linked_to_the_classification_it_created(self):
        taxa_list, det, occ = self._masking_fixture()

        # The second run finds nothing left to mask, so the first run's result stays the only one.
        for _ in range(2):
            ClassMaskingTask(
                occurrence_id=occ.pk,
                taxa_list_id=taxa_list.pk,
                algorithm_id=self.algorithm.pk,
                out_of_list_weight=0.0,
            ).run()

        result = AlgorithmResult.objects.get(occurrence=occ, kind="class_masking")
        self.assertIn(result.kind, {model.kind for model in ClassMaskingTask.result_models})
        self.assertEqual(result.project_id, self.project.pk)
        self.assertTrue(result.algorithm.key.startswith(f"{self.algorithm.key}_filtered_by_taxa_list_{taxa_list.pk}"))
        # Index 2 held e^5 / (e^2 + e^1 + e^5) of the probability and was excluded; index 0 was second.
        scores = _softmax([2.0, 1.0, 5.0])
        self.assertAlmostEqual(result.value, scores[2])
        self.assertAlmostEqual(result.data.pop("excluded_probability"), scores[2])
        self.assertEqual(
            result.data,
            {
                "new_winner_original_rank": 2,
                # A hard mask leaves no probability outside the list, so the winner is always in it.
                "excluded_probability_after": 0.0,
                "winner_in_list": True,
                "determination_before_id": self.species_taxa[2].pk,
                "determination_after_id": self.species_taxa[0].pk,
                "extra": {},
            },
        )
        masked = result.classifications.get()
        self.assertEqual((masked.taxon, masked.terminal), (self.species_taxa[0], True))
        # The top prediction before masking is the classification the masked one replaced.
        self.assertEqual(masked.applied_to.taxon, self.species_taxa[2])
        self.assertAlmostEqual(masked.applied_to.score, scores[2])
        self.assertEqual(masked.applied_to.taxon, self.species_taxa[2])

    def test_an_occurrence_masking_does_not_change_gets_no_result(self):
        logits = [2.0, 1.0, 5.0]
        taxa_list = TaxaList.objects.create(name="Keeps everything")
        taxa_list.taxa.set(self.species_taxa)
        det, occ = self._detection_with_occurrence()
        self._create_classification_with_logits(det, self.species_taxa[2], _softmax(logits), logits)

        ClassMaskingTask(occurrence_id=occ.pk, taxa_list_id=taxa_list.pk, algorithm_id=self.algorithm.pk).run()

        self.assertFalse(AlgorithmResult.objects.filter(occurrence=occ).exists())

    def test_an_occurrence_spanning_batches_gets_one_result_covering_every_batch(self):
        taxa_list, det1, occ = self._masking_fixture()
        det2 = Detection.objects.create(source_image=self.collection.images.first(), bbox=[0, 0, 100, 100])
        occ.detections.add(det2)
        logits = [2.0, 1.0, 5.0]
        self._create_classification_with_logits(det2, self.species_taxa[2], _softmax(logits), logits)
        new_algorithm = Algorithm.objects.create(
            name="masked_span",
            key="masked_span_test",
            task_type=AlgorithmTaskType.CLASSIFICATION.value,
            category_map=self.algorithm.category_map,
        )

        make_classifications_filtered_by_taxa_list(
            classifications=Classification.objects.filter(detection__in=[det1, det2]),
            taxa_list=taxa_list,
            algorithm=self.algorithm,
            new_algorithm=new_algorithm,
            batch_size=1,
            out_of_list_weight=0.0,
        )

        result = AlgorithmResult.objects.get(occurrence=occ)
        self.assertEqual(result.data["determination_after_id"], self.species_taxa[0].pk)
        self.assertEqual(
            sorted(result.classifications.values_list("detection_id", flat=True)), sorted([det1.pk, det2.pk])
        )

    def test_an_occurrence_without_a_project_is_still_rescored_but_gets_no_result(self):
        """A missing project must not fail a run after it has changed data; the result is skipped with a warning."""
        taxa_list, det, occ = self._masking_fixture()
        Occurrence.objects.filter(pk=occ.pk).update(project=None)

        with self.assertLogs("ami.ml.models.algorithm_result", level="WARNING") as logs:
            ClassMaskingTask(
                occurrence_id=occ.pk,
                taxa_list_id=taxa_list.pk,
                algorithm_id=self.algorithm.pk,
                out_of_list_weight=0.0,
            ).run()

        self.assertIn(f"Occurrence #{occ.pk}", logs.output[0])
        occ.refresh_from_db()
        self.assertEqual(occ.determination, self.species_taxa[0])
        self.assertFalse(AlgorithmResult.objects.filter(occurrence=occ).exists())
        self.assertIsNone(Classification.objects.get(applied_to__detection=det).algorithm_result)

    # ----- batched commit + heartbeat -------------------------------------

    def test_batched_commit_flushes_multiple_times(self):
        """With batch_size=2 and 5 classifications, on_batch fires at i=2, 4, 5 — more than once.

        Verifies that all classifications are correctly masked across flush boundaries
        (correctness preserved) and that the on_batch callback receives a call per batch
        (heartbeat wiring works)."""
        taxa_list = TaxaList.objects.create(name="Batch flush test")
        taxa_list.taxa.set(self.species_taxa[:1])  # keep only index 0; indices 1 and 2 excluded

        new_algorithm = Algorithm.objects.create(
            name="masked_batch",
            key="masked_batch_test",
            task_type=AlgorithmTaskType.CLASSIFICATION.value,
            category_map=self.algorithm.category_map,
        )

        # Create 5 detections, each with a classification whose top logit is index 2
        # (excluded), so every one should be masked and re-assigned to index 0.
        logits = [2.0, 1.0, 5.0]
        pks = []
        for _ in range(5):
            det, _ = self._detection_with_occurrence()
            clf = self._create_classification_with_logits(det, self.species_taxa[2], _softmax(logits), logits)
            pks.append(clf.pk)

        batch_calls: list[dict] = []
        metrics = make_classifications_filtered_by_taxa_list(
            classifications=Classification.objects.filter(pk__in=pks),
            taxa_list=taxa_list,
            algorithm=self.algorithm,
            new_algorithm=new_algorithm,
            batch_size=2,
            on_batch=batch_calls.append,
        )

        self.assertGreater(len(batch_calls), 1, "on_batch must fire more than once with batch_size=2 over 5 items")
        # i=2 and i=4 fire on the batch boundary; i=5 fires on the total boundary.
        self.assertEqual(len(batch_calls), 3)
        self.assertEqual(metrics["classifications_masked"], 5, "All 5 classifications must be masked across batches")
        self.assertEqual(
            Classification.objects.filter(algorithm=new_algorithm, terminal=True).count(),
            5,
            "A new terminal classification must exist for every masked row",
        )

    # ----- changed-only occurrence count ----------------------------------

    def test_occurrences_updated_counts_only_changed_determinations(self):
        """``occurrences_updated`` counts only occurrences whose determination changed,
        not every occurrence whose detection was touched.

        occ1: original winner is index 2 (excluded) — masking flips determination to index 0.
        occ2: original winner is index 0 (kept) — masking reassigns scores but determination stays index 0.
        Only occ1 should count."""
        taxa_list = TaxaList.objects.create(name="Changed-only count test")
        taxa_list.taxa.set(self.species_taxa[:2])  # excludes species_taxa[2] (index 2)

        new_algorithm = Algorithm.objects.create(
            name="masked_changed",
            key="masked_changed_test",
            task_type=AlgorithmTaskType.CLASSIFICATION.value,
            category_map=self.algorithm.category_map,
        )

        # occ1: index 2 has the highest logit, so masking forces the winner to index 0.
        logits_changes = [2.0, 1.0, 5.0]
        det1, occ1 = self._detection_with_occurrence()
        clf1 = self._create_classification_with_logits(
            det1, self.species_taxa[2], _softmax(logits_changes), logits_changes
        )
        # Persist the pre-masking determination so the loaded instance has it set.
        occ1.save(update_determination=True)  # determination = species_taxa[2]

        # occ2: index 0 has the highest logit, so after masking it remains the winner.
        # Masking still changes the scores (index 2 drops to 0, softmax shifts), so the
        # classification IS demoted — but occ2's determination stays species_taxa[0].
        logits_stays = [5.0, 1.0, 3.0]
        det2, occ2 = self._detection_with_occurrence()
        clf2 = self._create_classification_with_logits(
            det2, self.species_taxa[0], _softmax(logits_stays), logits_stays
        )
        occ2.save(update_determination=True)  # determination = species_taxa[0]

        metrics = make_classifications_filtered_by_taxa_list(
            classifications=Classification.objects.filter(pk__in=[clf1.pk, clf2.pk]),
            taxa_list=taxa_list,
            algorithm=self.algorithm,
            new_algorithm=new_algorithm,
            out_of_list_weight=0.0,
        )

        self.assertEqual(metrics["classifications_masked"], 2, "Both classifications are modified by masking")
        self.assertEqual(
            metrics["occurrences_updated"],
            1,
            "Only the occurrence whose determination changed (occ1) counts",
        )

    # ----- reweight toggle ------------------------------------------------

    def test_reweight_false_winner_identical_scores_differ(self):
        """For a hard mask, reweight=False gives the same winning taxon as reweight=True,
        but the stored score equals the winner's original absolute probability (not
        renormalised) and the kept-class scores do not sum to 1.

        logits = [2, 1, 5]: index 2 is excluded, so index 0 wins in both modes.
        reweight=True:  new_scores renormalised — sums to 1, score = renormalised p(index 0).
        reweight=False: new_scores = original with index 2 zeroed — sums < 1, score = original p(index 0)."""
        logits = [2.0, 1.0, 5.0]
        scores = _softmax(logits)
        taxa_list = TaxaList.objects.create(name="Reweight compare")
        taxa_list.taxa.set(self.species_taxa[:2])  # excludes index 2

        # --- reweight=True (default) ---
        det_t, _ = self._detection_with_occurrence()
        clf_t = self._create_classification_with_logits(det_t, self.species_taxa[2], scores, logits)
        new_alg_true = Algorithm.objects.create(
            name="masked_rw_true",
            key="masked_rw_true_test",
            task_type=AlgorithmTaskType.CLASSIFICATION.value,
            category_map=self.algorithm.category_map,
        )
        make_classifications_filtered_by_taxa_list(
            classifications=Classification.objects.filter(pk=clf_t.pk),
            taxa_list=taxa_list,
            algorithm=self.algorithm,
            new_algorithm=new_alg_true,
            reweight=True,
            out_of_list_weight=0.0,
        )

        # --- reweight=False ---
        det_f, _ = self._detection_with_occurrence()
        clf_f = self._create_classification_with_logits(det_f, self.species_taxa[2], scores, logits)
        new_alg_false = Algorithm.objects.create(
            name="masked_rw_false",
            key="masked_rw_false_test",
            task_type=AlgorithmTaskType.CLASSIFICATION.value,
            category_map=self.algorithm.category_map,
        )
        make_classifications_filtered_by_taxa_list(
            classifications=Classification.objects.filter(pk=clf_f.pk),
            taxa_list=taxa_list,
            algorithm=self.algorithm,
            new_algorithm=new_alg_false,
            reweight=False,
            out_of_list_weight=0.0,
        )

        new_clf_t = Classification.objects.get(detection=det_t, terminal=True)
        new_clf_f = Classification.objects.get(detection=det_f, terminal=True)

        # Winner is the same in both modes.
        self.assertEqual(new_clf_t.taxon, self.species_taxa[0])
        self.assertEqual(new_clf_f.taxon, self.species_taxa[0], "Winner is identical with reweight=False")

        # Excluded class is zeroed in both modes.
        self.assertAlmostEqual(new_clf_t.scores[2], 0.0, places=10)
        self.assertAlmostEqual(new_clf_f.scores[2], 0.0, places=10)

        # reweight=True: kept-class scores are renormalised and sum to 1.
        self.assertAlmostEqual(sum(new_clf_t.scores), 1.0, places=5)

        # reweight=False: kept classes retain original absolute values; sum is < 1.
        self.assertAlmostEqual(
            new_clf_f.scores[0], scores[0], places=6, msg="Kept class retains original score with reweight=False"
        )
        self.assertAlmostEqual(new_clf_f.scores[1], scores[1], places=6)
        self.assertNotAlmostEqual(
            sum(new_clf_f.scores), 1.0, places=2, msg="Scores must not sum to 1 with reweight=False"
        )

        # Stored confidence: reweight=False uses the original pre-mask probability.
        self.assertAlmostEqual(new_clf_f.score, scores[0], places=6)
        self.assertNotAlmostEqual(new_clf_t.score, scores[0], places=2)

    # ----- soft masking (out-of-list weight above 0) ------------------------

    def test_soft_mask_equals_adding_the_log_weight_to_out_of_list_logits(self):
        """Down-weighting a class by ``w`` is the same as adding ``ln(w)`` to its logit
        before the softmax, so the stored scores are a proper distribution in which the
        out-of-list class keeps some probability."""
        logits = [2.0, 1.0, 5.0]
        weight = 0.1
        taxa_list, pks = self._make_scope(1, "Logit shift list")

        make_classifications_filtered_by_taxa_list(
            classifications=Classification.objects.filter(pk__in=pks),
            taxa_list=taxa_list,
            algorithm=self.algorithm,
            new_algorithm=self._masking_algorithm("masked_logit_shift"),
            out_of_list_weight=weight,
        )

        new_clf = Classification.objects.get(applied_to_id=pks[0])
        expected = _softmax([logits[0], logits[1], logits[2] + math.log(weight)])
        for stored, wanted in zip(new_clf.scores, expected, strict=True):
            self.assertAlmostEqual(stored, wanted, places=9)
        self.assertAlmostEqual(sum(new_clf.scores), 1.0, places=9)
        self.assertGreater(new_clf.scores[2], 0.0, "A soft mask leaves the out-of-list class some probability")

    def test_a_confident_out_of_list_class_still_wins_and_the_result_says_so(self):
        """At weight 0.1 an out-of-list class wins when it is more than 10 times as likely
        as the best class in the list. The result records that the winner is outside the
        list, and how much probability sat outside the list before and after."""
        taxa_list, det, occ = self._masking_fixture("Soft winner list")
        occ.refresh_from_db()
        self.assertEqual(occ.determination, self.species_taxa[2])

        ClassMaskingTask(
            occurrence_id=occ.pk,
            taxa_list_id=taxa_list.pk,
            algorithm_id=self.algorithm.pk,
            out_of_list_weight=0.1,
        ).run()

        scores = _softmax([2.0, 1.0, 5.0])
        new_clf = Classification.objects.get(detection=det, terminal=True)
        self.assertEqual(new_clf.taxon, self.species_taxa[2])
        self.assertTrue(new_clf.algorithm.key.endswith(f"_filtered_by_taxa_list_{taxa_list.pk}_weight_0p1"))
        occ.refresh_from_db()
        self.assertEqual(occ.determination, self.species_taxa[2], "The determination is unchanged")

        result = AlgorithmResult.objects.get(occurrence=occ, kind="class_masking")
        self.assertIs(result.data["winner_in_list"], False)
        self.assertEqual(result.data["new_winner_original_rank"], 1)
        # The probability outside the list is the classifier's own, whatever the weight.
        self.assertAlmostEqual(result.data["excluded_probability"], scores[2])
        self.assertAlmostEqual(result.value, scores[2])
        self.assertAlmostEqual(result.data["excluded_probability_after"], new_clf.scores[2])
        self.assertAlmostEqual(result.data["excluded_probability_after"], 0.5949, places=4)
        self.assertEqual(result.data["determination_after_id"], self.species_taxa[2].pk)

    def test_the_default_weight_is_a_soft_mask(self):
        """A task configured without a weight down-weights out-of-list classes by the
        default; it does not remove them."""
        logits = [2.0, 1.0, 5.0]
        taxa_list, det, occ = self._masking_fixture("Default weight list")

        ClassMaskingTask(occurrence_id=occ.pk, taxa_list_id=taxa_list.pk, algorithm_id=self.algorithm.pk).run()

        self.assertGreater(DEFAULT_OUT_OF_LIST_WEIGHT, 0)
        expected = _softmax([logits[0], logits[1], logits[2] + math.log(DEFAULT_OUT_OF_LIST_WEIGHT)])
        expected_winner = expected.index(max(expected))
        new_clf = Classification.objects.get(detection=det, terminal=True)
        for stored, wanted in zip(new_clf.scores, expected, strict=True):
            self.assertAlmostEqual(stored, wanted, places=9)
        self.assertGreater(new_clf.scores[2], 0.0)
        self.assertEqual(new_clf.taxon, self.species_taxa[expected_winner])
        self.assertTrue(new_clf.algorithm.key.endswith(f"_weight_{_weight_token(DEFAULT_OUT_OF_LIST_WEIGHT)}"))
        result = AlgorithmResult.objects.get(occurrence=occ, kind="class_masking")
        self.assertIs(result.data["winner_in_list"], expected_winner != 2)

    def test_a_class_with_no_taxon_is_removed_at_any_weight(self):
        """A class whose label matches no taxon cannot become a determination, so it gets
        no probability even when out-of-list classes are only down-weighted."""
        labels = [self.species_taxa[0].name, self.species_taxa[1].name, "A label that matches no taxon"]
        category_map = AlgorithmCategoryMap.objects.create(
            data=[{"index": i, "label": label} for i, label in enumerate(labels)],
            labels=labels,
            version="v1.0",
        )
        classifier = Algorithm.objects.create(
            name="Classifier with an unmatched class",
            task_type=AlgorithmTaskType.CLASSIFICATION.value,
            category_map=category_map,
        )
        taxa_list = TaxaList.objects.create(name="Keep the first species")
        taxa_list.taxa.set(self.species_taxa[:1])

        # The unmatched class (index 2) is by far the most likely; the out-of-list species
        # (index 1) beats the in-list one even at half weight.
        logits = [1.0, 2.0, 6.0]
        det, _ = self._detection_with_occurrence()
        source = Classification.objects.create(
            detection=det,
            taxon=None,
            score=max(_softmax(logits)),
            scores=_softmax(logits),
            logits=logits,
            terminal=True,
            timestamp=datetime.datetime.now(datetime.timezone.utc),
            algorithm=classifier,
        )

        make_classifications_filtered_by_taxa_list(
            classifications=Classification.objects.filter(pk=source.pk),
            taxa_list=taxa_list,
            algorithm=classifier,
            new_algorithm=Algorithm.objects.create(
                name="masked_unmatched",
                key="masked_unmatched",
                task_type=AlgorithmTaskType.CLASSIFICATION.value,
                category_map=category_map,
            ),
            out_of_list_weight=0.5,
        )

        new_clf = Classification.objects.get(applied_to=source)
        self.assertEqual(new_clf.scores[2], 0.0)
        self.assertIsNotNone(new_clf.taxon)
        self.assertEqual(new_clf.taxon, self.species_taxa[1])

    def test_each_weight_gets_its_own_masking_algorithm(self):
        """The weight changes which species can be named, so it is part of the masking
        algorithm's identity. A hard mask keeps the key it has always had."""
        taxa_list = TaxaList.objects.create(name="Weight identity list")
        taxa_list.taxa.set(self.species_taxa[:2])
        task = ClassMaskingTask(occurrence_id=1, taxa_list_id=taxa_list.pk, algorithm_id=self.algorithm.pk)

        def get(weight: float) -> Algorithm:
            return task._get_or_create_masking_algorithm(
                self.algorithm, taxa_list, reweight=True, out_of_list_weight=weight
            )

        base = f"{self.algorithm.key}_filtered_by_taxa_list_{taxa_list.pk}"
        algorithms = {weight: get(weight) for weight in (0.0, 0.01, 0.1)}
        self.assertEqual(
            {weight: algorithm.key for weight, algorithm in algorithms.items()},
            {0.0: f"{base}_reweighted", 0.01: f"{base}_weight_0p01", 0.1: f"{base}_weight_0p1"},
        )
        self.assertEqual(len({algorithm.pk for algorithm in algorithms.values()}), 3)
        self.assertEqual(get(0.01).pk, algorithms[0.01].pk, "The same weight reuses its algorithm")
        # The key is a slug, so the weight is written without a dot.
        algorithms[0.01].full_clean()

    def test_a_row_whose_kept_classes_all_underflow_is_skipped(self):
        """When every class the list keeps has a probability too small to represent,
        there is nothing to renormalise: the row is left alone with a warning."""
        logits = [0.0, 0.0, 800.0]
        taxa_list = TaxaList.objects.create(name="Underflow list")
        taxa_list.taxa.set(self.species_taxa[:2])
        det, _ = self._detection_with_occurrence()
        source = self._create_classification_with_logits(det, self.species_taxa[2], _softmax(logits), logits)

        with self.assertLogs("ami.ml.post_processing.class_masking", level="WARNING") as logs:
            metrics = make_classifications_filtered_by_taxa_list(
                classifications=Classification.objects.filter(pk=source.pk),
                taxa_list=taxa_list,
                algorithm=self.algorithm,
                new_algorithm=self._masking_algorithm("masked_underflow"),
                out_of_list_weight=0.0,
            )

        self.assertTrue(any(f"Classification {source.pk}" in line for line in logs.output))
        self.assertEqual(metrics["classifications_masked"], 0)
        source.refresh_from_db()
        self.assertTrue(source.terminal)
        self.assertFalse(Classification.objects.filter(applied_to=source).exists())

    def test_a_weight_the_maths_cannot_use_is_rejected(self):
        """The weight must be in [0, 1), and scores that are not renormalised need a hard
        mask. The config schema reports this to users; the function guards direct callers."""
        taxa_list, pks = self._make_scope(1, "Weight guard list")
        for index, kwargs in enumerate(
            ({"out_of_list_weight": -0.1}, {"out_of_list_weight": 1.0}, {"out_of_list_weight": 0.1, "reweight": False})
        ):
            with self.subTest(**kwargs), self.assertRaises(ValueError):
                make_classifications_filtered_by_taxa_list(
                    classifications=Classification.objects.filter(pk__in=pks),
                    taxa_list=taxa_list,
                    algorithm=self.algorithm,
                    new_algorithm=self._masking_algorithm(f"masked_weight_guard_{index}"),
                    **kwargs,
                )

    def test_an_empty_scope_warns_that_rescored_rows_are_not_rescored_again(self):
        """A second run at another weight finds nothing, because the first run demoted its
        sources. The log says so instead of reporting a silent zero."""
        taxa_list, det, occ = self._masking_fixture("Second weight list")
        ClassMaskingTask(
            occurrence_id=occ.pk, taxa_list_id=taxa_list.pk, algorithm_id=self.algorithm.pk, out_of_list_weight=0.0
        ).run()

        with self.assertLogs("ami.post_processing.class_masking", level="WARNING") as logs:
            ClassMaskingTask(
                occurrence_id=occ.pk, taxa_list_id=taxa_list.pk, algorithm_id=self.algorithm.pk, out_of_list_weight=0.1
            ).run()

        self.assertTrue(any("not re-scored again" in line for line in logs.output))
        self.assertEqual(Classification.objects.filter(detection=det, terminal=True).count(), 1)

    # ----- run_class_masking management command -----------------------------

    def test_command_passes_the_weight_to_the_task(self):
        taxa_list, pks = self._make_scope(1, "Command weight list")

        call_command(
            "run_class_masking",
            collection_id=self.collection.pk,
            taxa_list_id=taxa_list.pk,
            algorithm_id=self.algorithm.pk,
            out_of_list_weight=0.0,
            stdout=io.StringIO(),
        )

        # Weight 0 is the hard mask, which keeps its own algorithm key.
        masking_algo = Algorithm.objects.get(
            key=f"{self.algorithm.key}_filtered_by_taxa_list_{taxa_list.pk}_reweighted"
        )
        self.assertTrue(Classification.objects.filter(applied_to_id=pks[0], algorithm=masking_algo).exists())

    def test_command_rejects_an_invalid_weight_before_doing_anything(self):
        taxa_list, pks = self._make_scope(1, "Command invalid weight list")

        with self.assertRaises(CommandError):
            call_command(
                "run_class_masking",
                collection_id=self.collection.pk,
                taxa_list_id=taxa_list.pk,
                algorithm_id=self.algorithm.pk,
                out_of_list_weight=2.0,
                stdout=io.StringIO(),
            )

        self.assertFalse(Classification.objects.filter(applied_to_id=pks[0]).exists())

    def test_command_dry_run_reports_the_weight_and_writes_nothing(self):
        taxa_list, pks = self._make_scope(1, "Command dry run list")
        algorithms_before = Algorithm.objects.count()
        out = io.StringIO()

        call_command(
            "run_class_masking",
            collection_id=self.collection.pk,
            taxa_list_id=taxa_list.pk,
            algorithm_id=self.algorithm.pk,
            dry_run=True,
            stdout=out,
        )

        self.assertIn(f"Out-of-list weight: {DEFAULT_OUT_OF_LIST_WEIGHT:g}", out.getvalue())
        self.assertEqual(Algorithm.objects.count(), algorithms_before, "A dry run creates no Algorithm row")
        self.assertFalse(Classification.objects.filter(applied_to_id=pks[0]).exists())

    # ----- scope query shape ----------------------------------------------

    def test_collection_scope_returns_each_classification_once(self):
        """A capture in several collections still contributes one row per
        classification, which is why the scope needs no de-duplication."""
        capture = self.collection.images.first()
        other_collection = SourceImageCollection.objects.create(
            name="Second collection containing the same capture",
            project=self.project,
            method="manual",
            kwargs={"image_ids": [capture.pk]},
        )
        other_collection.images.add(capture)

        detection = Detection.objects.create(source_image=capture, bbox=[0, 0, 200, 200])
        occurrence = Occurrence.objects.create(project=self.project, event=self.deployment.events.first())
        occurrence.detections.add(detection)
        logits = [2.0, 1.0, 5.0]
        classification = self._create_classification_with_logits(
            detection, self.species_taxa[2], _softmax(logits), logits
        )

        taxa_list = TaxaList.objects.create(name="Scope shape list")
        taxa_list.taxa.set(self.species_taxa[:2])
        task = ClassMaskingTask(
            source_image_collection_id=self.collection.pk,
            taxa_list_id=taxa_list.pk,
            algorithm_id=self.algorithm.pk,
        )
        masking_algorithm = task._get_or_create_masking_algorithm(
            self.algorithm,
            taxa_list,
            reweight=task.config.reweight,
            out_of_list_weight=task.config.out_of_list_weight,
        )
        scoped, _ = task._scoped_classifications(task.config, self.algorithm, masking_algorithm)

        self.assertEqual(list(scoped.filter(pk=classification.pk)), [classification])
        self.assertEqual(
            scoped.filter(pk=classification.pk).count(),
            1,
            "A capture in two collections must not yield the classification twice",
        )

    def test_scope_query_does_not_deduplicate_rows(self):
        """Neither scope de-duplicates rows.

        De-duplication is invisible in the output but very costly here, so the
        query shape is the only thing that can guard it; the test above covers the
        results being equivalent. See #1376.
        """
        taxa_list = TaxaList.objects.create(name="Query shape list")
        taxa_list.taxa.set(self.species_taxa[:2])
        occurrence = Occurrence.objects.create(project=self.project, event=self.deployment.events.first())

        for kwargs in (
            {"source_image_collection_id": self.collection.pk},
            {"occurrence_id": occurrence.pk},
        ):
            with self.subTest(**kwargs):
                task = ClassMaskingTask(taxa_list_id=taxa_list.pk, algorithm_id=self.algorithm.pk, **kwargs)
                masking_algorithm = task._get_or_create_masking_algorithm(
                    self.algorithm,
                    taxa_list,
                    reweight=task.config.reweight,
                    out_of_list_weight=task.config.out_of_list_weight,
                )
                scoped, _ = task._scoped_classifications(task.config, self.algorithm, masking_algorithm)
                self.assertFalse(scoped.query.distinct)

    def test_scope_size_is_reported_before_the_first_batch(self):
        """The scope size reaches the job before any row is processed, so a large
        run reports what it found rather than sitting at zero while it starts."""
        taxa_list = TaxaList.objects.create(name="Setup callback list")
        taxa_list.taxa.set(self.species_taxa[:2])

        det, _ = self._detection_with_occurrence()
        logits = [2.0, 1.0, 5.0]
        self._create_classification_with_logits(det, self.species_taxa[2], _softmax(logits), logits)

        new_algorithm = Algorithm.objects.create(
            name="masked_setup",
            key="masked_setup_test",
            task_type=AlgorithmTaskType.CLASSIFICATION.value,
            category_map=self.algorithm.category_map,
        )

        events: list[tuple[str, int]] = []
        make_classifications_filtered_by_taxa_list(
            classifications=Classification.objects.filter(detection=det, terminal=True),
            taxa_list=taxa_list,
            algorithm=self.algorithm,
            new_algorithm=new_algorithm,
            on_setup=lambda total: events.append(("setup", total)),
            on_batch=lambda m: events.append(("batch", m["classifications_checked"])),
        )

        self.assertEqual(events[0], ("setup", 1), "Scope size is reported once, before the first batch")
        self.assertEqual([name for name, _ in events], ["setup", "batch"])

    # ----- scope fetch shape ----------------------------------------------

    def _make_scope(self, n: int, taxa_list_name: str) -> tuple[TaxaList, list[int]]:
        """Build ``n`` maskable classifications and a taxa list that masks their winner."""
        taxa_list = TaxaList.objects.create(name=taxa_list_name)
        taxa_list.taxa.set(self.species_taxa[:2])
        logits = [2.0, 1.0, 5.0]  # index 2 wins and is excluded, so every row is masked
        pks = []
        for _ in range(n):
            det, _ = self._detection_with_occurrence()
            pks.append(self._create_classification_with_logits(det, self.species_taxa[2], _softmax(logits), logits).pk)
        return taxa_list, pks

    def _masking_algorithm(self, name: str) -> Algorithm:
        return Algorithm.objects.create(
            name=name,
            key=name,
            task_type=AlgorithmTaskType.CLASSIFICATION.value,
            category_map=self.algorithm.category_map,
        )

    def test_scope_is_read_one_batch_per_query(self):
        """The scope is read by one query per batch, not through ``.iterator()``.

        The query cache turns ``.iterator()`` into one read of the whole scope, so a large
        run reports no progress until every row is loaded and is cancelled as stalled.
        Reading each batch with its own query keeps the first progress report one batch
        away. See #1404.
        """
        taxa_list, pks = self._make_scope(5, "Bounded batch list")
        scope = Classification.objects.filter(pk__in=pks, terminal=True)

        scope_pks = set(pks)
        batch_sizes: list[int] = []
        original_fetch_all = QuerySet._fetch_all

        def _record(self_qs):
            already_cached = self_qs._result_cache is not None
            original_fetch_all(self_qs)
            if already_cached:
                return
            rows = [r for r in self_qs._result_cache if isinstance(r, Classification) and r.pk in scope_pks]
            if rows:
                batch_sizes.append(len(rows))

        with mock.patch.object(QuerySet, "_fetch_all", _record):
            make_classifications_filtered_by_taxa_list(
                classifications=scope,
                taxa_list=taxa_list,
                algorithm=self.algorithm,
                new_algorithm=self._masking_algorithm("masked_batched"),
                batch_size=2,
            )

        self.assertGreaterEqual(
            len(batch_sizes),
            3,
            f"5 rows at batch_size=2 should reach the loop in at least 3 queries, got {batch_sizes}",
        )
        self.assertLessEqual(max(batch_sizes), 2, f"A single query returned {max(batch_sizes)} scope rows")

    def test_masked_row_does_not_copy_the_source_logits(self):
        """A masked row stores no logits; they stay on the source row it was applied to.

        A full copy per masked row doubles the size of every run for no new information.
        """
        taxa_list, pks = self._make_scope(1, "No logits copy list")
        source = Classification.objects.get(pk=pks[0])
        make_classifications_filtered_by_taxa_list(
            classifications=Classification.objects.filter(pk__in=pks, terminal=True),
            taxa_list=taxa_list,
            algorithm=self.algorithm,
            new_algorithm=self._masking_algorithm("masked_no_logits"),
        )
        masked = Classification.objects.get(applied_to=source)
        self.assertIsNone(masked.logits)
        self.assertIsNotNone(masked.scores)
        self.assertEqual(masked.applied_to.logits, source.logits)

    def test_query_cache_is_restored_when_a_batch_read_fails(self):
        """A failed batch read must not leave the query cache off for the rest of the worker thread."""
        from cachalot.api import LOCAL_STORAGE

        taxa_list, pks = self._make_scope(2, "Failing read list")
        self.addCleanup(setattr, LOCAL_STORAGE, "cachalot_enabled", getattr(LOCAL_STORAGE, "cachalot_enabled", True))
        LOCAL_STORAGE.cachalot_enabled = True

        original_fetch_all = QuerySet._fetch_all

        def _fail_on_scope_rows(self_qs):
            if self_qs.model is Classification and "scores" in self_qs.query.deferred_loading[0]:
                raise RuntimeError("batch read failed")
            original_fetch_all(self_qs)

        with mock.patch.object(QuerySet, "_fetch_all", _fail_on_scope_rows):
            with self.assertRaises(RuntimeError):
                make_classifications_filtered_by_taxa_list(
                    classifications=Classification.objects.filter(pk__in=pks, terminal=True),
                    taxa_list=taxa_list,
                    algorithm=self.algorithm,
                    new_algorithm=self._masking_algorithm("masked_failing_read"),
                )
        self.assertTrue(LOCAL_STORAGE.cachalot_enabled)

    def test_scope_does_not_fetch_the_unused_scores_column(self):
        """``scores`` is never read while masking, and it is as large as ``logits``
        (~140 kB per row for a 29,176-class algorithm), so fetching it doubles what
        every batch transfers and parses for nothing."""
        taxa_list, pks = self._make_scope(2, "Deferred scores list")
        scope = Classification.objects.filter(pk__in=pks, terminal=True)

        # Record how each scope row arrived the first time it was read, which is the
        # batch read. Later reads of the same row come from occurrence.save()
        # recomputing a determination, which legitimately selects every column.
        scope_pks = set(pks)
        deferred_on_arrival: dict[int, set[str]] = {}
        original_fetch_all = QuerySet._fetch_all

        def _record(self_qs):
            already_cached = self_qs._result_cache is not None
            original_fetch_all(self_qs)
            if already_cached:
                return
            for row in self_qs._result_cache:
                if isinstance(row, Classification) and row.pk in scope_pks:
                    deferred_on_arrival.setdefault(row.pk, row.get_deferred_fields())

        with mock.patch.object(QuerySet, "_fetch_all", _record):
            make_classifications_filtered_by_taxa_list(
                classifications=scope,
                taxa_list=taxa_list,
                algorithm=self.algorithm,
                new_algorithm=self._masking_algorithm("masked_deferred"),
                batch_size=2,
            )

        self.assertEqual(len(deferred_on_arrival), 2, "Both scope rows should have been read")
        self.assertTrue(
            all("scores" in deferred for deferred in deferred_on_arrival.values()),
            "Masking fetched the scores column, which it never reads",
        )

    def test_detection_is_not_queried_once_per_row(self):
        """``classification.detection`` and ``detection.occurrence`` are read for every
        masked row, so the task's scope brings both with each batch instead of costing a
        query per row. The per-occurrence queries that ``occurrence.save()`` issues during
        the flush are a separate cost and are not covered here."""
        taxa_list, pks = self._make_scope(4, "Select related list")
        task = ClassMaskingTask(
            source_image_collection_id=self.collection.pk,
            taxa_list_id=taxa_list.pk,
            algorithm_id=self.algorithm.pk,
        )
        masking_algorithm = task._get_or_create_masking_algorithm(
            self.algorithm,
            taxa_list,
            reweight=task.config.reweight,
            out_of_list_weight=task.config.out_of_list_weight,
        )
        scoped, _ = task._scoped_classifications(task.config, self.algorithm, masking_algorithm)

        with CaptureQueriesContext(connection) as ctx:
            make_classifications_filtered_by_taxa_list(
                classifications=scoped.filter(pk__in=pks),
                taxa_list=taxa_list,
                algorithm=self.algorithm,
                new_algorithm=masking_algorithm,
                batch_size=4,
            )

        # A lazy foreign-key load selects the whole row by id. The flush's narrower
        # per-occurrence reads (e.g. of ``determination_id``) start differently.
        per_row_lookups = [
            q["sql"]
            for q in ctx.captured_queries
            if any(
                q["sql"].startswith(f'SELECT "{table}"."id", ') and f'WHERE "{table}"."id" = ' in q["sql"]
                for table in ("main_detection", "main_occurrence")
            )
        ]
        self.assertEqual(
            per_row_lookups,
            [],
            f"{len(per_row_lookups)} per-row detection/occurrence lookups; expected both to come with the batch",
        )

    def test_non_positive_batch_size_is_rejected(self):
        """A batch size of zero or less would skip the loop and report every row as
        checked while masking none, so it is refused up front."""
        taxa_list, pks = self._make_scope(1, "Batch size guard list")
        for batch_size in (0, -1):
            with self.subTest(batch_size=batch_size), self.assertRaises(ValueError):
                make_classifications_filtered_by_taxa_list(
                    classifications=Classification.objects.filter(pk__in=pks),
                    taxa_list=taxa_list,
                    algorithm=self.algorithm,
                    new_algorithm=self._masking_algorithm(f"masked_guard_{abs(batch_size)}"),
                    batch_size=batch_size,
                )
