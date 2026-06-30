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

        # The per-(source algorithm, taxa list) masking algorithm exists and kept
        # its category map (the bug being guarded: it used to be set in memory only).
        masking_algo = Algorithm.objects.get(key=f"{self.algorithm.key}_filtered_by_taxa_list_{taxa_list.pk}")
        self.assertIsNotNone(masking_algo.category_map_id)
        self.assertEqual(masking_algo.category_map_id, self.algorithm.category_map_id)

        new_clf = Classification.objects.get(detection=det, terminal=True, algorithm=masking_algo)
        self.assertEqual(new_clf.taxon, self.species_taxa[1])
        self.assertEqual(new_clf.applied_to, original)
        occ.refresh_from_db()
        self.assertEqual(occ.determination, self.species_taxa[1], "Occurrence determination follows the masked result")

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
