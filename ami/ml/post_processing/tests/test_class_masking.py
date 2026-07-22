"""Domain tests for the class masking post-processing task.

Class masking re-scores a classifier's terminal predictions against a taxa list:
classes whose taxon is not in the list are masked, the softmax is renormalised
over the rest, and a new terminal classification (linked back via ``applied_to``)
records the masked result. These tests cover the masking maths (including that an
excluded class can never win even when it had the highest logit), the provenance
link, the persisted output algorithm, and both admin scopes (collection / single
occurrence) end to end through ``ClassMaskingTask.run()``.
"""
import datetime
import math
import pathlib
import uuid

from django.test import TestCase

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
from ami.ml.models import Algorithm, AlgorithmCategoryMap
from ami.ml.models.algorithm import AlgorithmTaskType
from ami.ml.post_processing.class_masking import ClassMaskingTask, make_classifications_filtered_by_taxa_list
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
        """The core guarantee: a masked class cannot be selected, even if it had
        the single highest logit before masking."""
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
        ).run()

        # The per-(source algorithm, taxa list, reweight mode) masking algorithm
        # exists and kept its category map (the bug being guarded: it used to be
        # set in memory only). Default reweight=True → the "reweighted" mode.
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

    def test_reweight_modes_get_distinct_masking_algorithms(self):
        """The reweight mode is part of the masking algorithm's identity.

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
        ).run()

        det_f, _ = self._detection_with_occurrence()
        self._create_classification_with_logits(det_f, self.species_taxa[2], _softmax(logits), logits)
        ClassMaskingTask(
            source_image_collection_id=self.collection.pk,
            taxa_list_id=taxa_list.pk,
            algorithm_id=self.algorithm.pk,
            reweight=False,
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
        ).run()

        new_clf = Classification.objects.filter(detection=det, terminal=True).exclude(algorithm=self.algorithm).first()
        self.assertIsNotNone(new_clf)
        self.assertEqual(new_clf.taxon, self.species_taxa[0])

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
        )

        self.assertEqual(metrics["classifications_masked"], 2, "Both classifications are modified by masking")
        self.assertEqual(
            metrics["occurrences_updated"],
            1,
            "Only the occurrence whose determination changed (occ1) counts",
        )

    # ----- reweight toggle ------------------------------------------------

    def test_reweight_false_winner_identical_scores_differ(self):
        """With reweight=False the winning taxon is identical to reweight=True, but the
        stored score equals the winner's original absolute probability (not renormalised)
        and the kept-class scores do not sum to 1.

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
        scoped, _ = task._scoped_classifications(task.config, self.algorithm)

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
                scoped, _ = task._scoped_classifications(task.config, self.algorithm)
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
