import logging

import numpy as np
from django.db import transaction
from django.db.models import QuerySet
from django.utils import timezone

from ami.main.models import Classification, Occurrence, SourceImageCollection, TaxaList
from ami.ml.models.algorithm import Algorithm, AlgorithmCategoryMap, AlgorithmTaskType
from ami.ml.post_processing.base import BasePostProcessingTask

logger = logging.getLogger(__name__)


def update_single_occurrence(
    occurrence: Occurrence,
    algorithm: Algorithm,
    taxa_list: TaxaList,
    task_logger: logging.Logger = logger,
):
    task_logger.info(f"Recalculating classifications for occurrence {occurrence.pk}.")

    # Get the classifications for the occurrence in the collection
    classifications = Classification.objects.filter(
        detection__occurrence=occurrence,
        terminal=True,
        algorithm=algorithm,
        scores__isnull=False,
        logits__isnull=False,
    ).distinct()

    # Make a new Algorithm for the filtered classifications
    new_algorithm, _ = Algorithm.objects.get_or_create(
        name=f"{algorithm.name} (filtered by taxa list {taxa_list.name})",
        key=f"{algorithm.key}_filtered_by_taxa_list_{taxa_list.pk}",
        defaults={
            "description": f"Classification algorithm {algorithm.name} filtered by taxa list {taxa_list.name}",
            "task_type": AlgorithmTaskType.CLASSIFICATION.value,
            "category_map": algorithm.category_map,
        },
    )

    make_classifications_filtered_by_taxa_list(
        classifications=classifications,
        taxa_list=taxa_list,
        algorithm=algorithm,
        new_algorithm=new_algorithm,
    )


def update_occurrences_in_collection(
    collection: SourceImageCollection,
    taxa_list: TaxaList,
    algorithm: Algorithm,
    params: dict,
    new_algorithm: Algorithm,
    task_logger: logging.Logger = logger,
    job=None,
):
    task_logger.info(f"Recalculating classifications based on a taxa list. Params: {params}")

    classifications = Classification.objects.filter(
        detection__source_image__collections=collection,
        terminal=True,
        algorithm=algorithm,
        scores__isnull=False,
        logits__isnull=False,
    ).distinct()

    make_classifications_filtered_by_taxa_list(
        classifications=classifications,
        taxa_list=taxa_list,
        algorithm=algorithm,
        new_algorithm=new_algorithm,
    )


def make_classifications_filtered_by_taxa_list(
    classifications: QuerySet[Classification],
    taxa_list: TaxaList,
    algorithm: Algorithm,
    new_algorithm: Algorithm,
):
    taxa_in_list = set(taxa_list.taxa.all())

    occurrences_to_update: set[Occurrence] = set()
    classification_count = classifications.count()
    logger.info(f"Found {classification_count} terminal classifications with scores to update.")

    if classification_count == 0:
        raise ValueError("No terminal classifications with scores found to update.")

    if not algorithm.category_map:
        raise ValueError(f"Algorithm {algorithm} does not have a category map.")
    category_map: AlgorithmCategoryMap = algorithm.category_map

    # @TODO find a more efficient way to get the category map with taxa. This is slow!
    logger.info(f"Retrieving category map with Taxa instances for algorithm {algorithm}")
    category_map_with_taxa = category_map.with_taxa()
    excluded_category_map_with_taxa = [
        category for category in category_map_with_taxa if category["taxon"] not in taxa_in_list
    ]

    excluded_category_indices = [
        int(category["index"]) for category in excluded_category_map_with_taxa  # type: ignore
    ]

    # Log number of categories in the category map, num included, and num excluded, num classifications to update
    logger.info(
        f"Category map has {len(category_map_with_taxa)} categories, "
        f"{len(excluded_category_map_with_taxa)} categories excluded, "
        f"{classification_count} classifications to check"
    )

    classifications_to_add = []
    classifications_to_update = []

    timestamp = timezone.now()
    for classification in classifications:
        scores, logits = classification.scores, classification.logits

        # Assert that all scores & logits are lists of numbers
        if not isinstance(scores, list) or not all(isinstance(score, (int, float)) for score in scores):
            raise ValueError(f"Scores for classification {classification.pk} are not a list of numbers: {scores}")
        if not isinstance(logits, list) or not all(isinstance(logit, (int, float)) for logit in logits):
            raise ValueError(f"Logits for classification {classification.pk} are not a list of numbers: {logits}")

        logger.debug(f"Processing classification {classification.pk} with {len(scores)} scores")
        logger.info(f"Previous totals: {sum(scores)} scores, {sum(logits)} logits")

        logits_np = np.array(logits)

        # Mask excluded logits with -100 (effectively zero probability after softmax)
        # @TODO consider using -np.inf for mathematically exact masking
        logits_np[excluded_category_indices] = -100

        logits: list[float] = logits_np.tolist()

        # Recalculate the softmax scores based on the filtered logits
        scores_np: np.ndarray = np.exp(logits_np - np.max(logits_np))  # Subtract max for numerical stability
        scores_np /= np.sum(scores_np)  # Normalize to get probabilities

        scores: list = scores_np.tolist()  # Convert back to list

        logger.info(f"New totals: {sum(scores)} scores, {sum(logits)} logits")

        # Get the taxon with the highest score  using the index of the max score
        top_index = scores.index(max(scores))
        top_taxon = category_map_with_taxa[top_index]["taxon"]
        logger.debug(f"Top taxon: {category_map_with_taxa[top_index]}, index: {top_index}")

        # check if needs updating
        if classification.scores == scores and classification.logits == logits:
            logger.debug(f"Classification {classification.pk} does not need updating")
            continue

        # Consider the existing classification as an intermediate classification
        classification.terminal = False
        classification.updated_at = timestamp

        # Recalculate the top taxon and score
        new_classification = Classification(
            taxon=top_taxon,
            algorithm=new_algorithm,
            score=max(scores),
            scores=scores,
            logits=logits,
            detection=classification.detection,
            timestamp=classification.timestamp,
            terminal=True,
            category_map=new_algorithm.category_map,
            created_at=timestamp,
            updated_at=timestamp,
        )
        if new_classification.taxon is None:
            raise ValueError(
                f"Unable to determine top taxon after class masking for classification {classification.pk}. "
                "No allowed classes found in taxa list."
            )

        classifications_to_update.append(classification)
        classifications_to_add.append(new_classification)

        assert new_classification.detection is not None
        assert new_classification.detection.occurrence is not None
        occurrences_to_update.add(new_classification.detection.occurrence)

        logger.info(
            f"Adding new classification for Taxon {top_taxon} to occurrence {new_classification.detection.occurrence}"
        )

    # Bulk update/create in a single transaction for atomicity
    with transaction.atomic():
        if classifications_to_update:
            logger.info(f"Bulk updating {len(classifications_to_update)} existing classifications")
            Classification.objects.bulk_update(classifications_to_update, ["terminal", "updated_at"])
            logger.info(f"Updated {len(classifications_to_update)} existing classifications")

        if classifications_to_add:
            logger.info(f"Bulk creating {len(classifications_to_add)} new classifications")
            Classification.objects.bulk_create(classifications_to_add)
            logger.info(f"Added {len(classifications_to_add)} new classifications")

        # Update the occurrence determinations
        logger.info(f"Updating the determinations for {len(occurrences_to_update)} occurrences")
        for occurrence in occurrences_to_update:
            occurrence.save(update_determination=True)
        logger.info(f"Updated determinations for {len(occurrences_to_update)} occurrences")


class ClassMaskingTask(BasePostProcessingTask):
    key = "class_masking"
    name = "Class masking"

    def run(self) -> None:
        """Apply class masking on a source image collection using a taxa list."""
        job = self.job
        self.logger.info(f"=== Starting {self.name} ===")

        collection_id = self.config.get("collection_id")
        taxa_list_id = self.config.get("taxa_list_id")
        algorithm_id = self.config.get("algorithm_id")

        # Validate config parameters
        if not all([collection_id, taxa_list_id, algorithm_id]):
            self.logger.error("Missing required configuration: collection_id, taxa_list_id, algorithm_id")
            return

        try:
            collection = SourceImageCollection.objects.get(pk=collection_id)
            taxa_list = TaxaList.objects.get(pk=taxa_list_id)
            algorithm = Algorithm.objects.get(pk=algorithm_id)
        except Exception as e:
            self.logger.exception(f"Failed to load objects: {e}")
            return

        self.logger.info(f"Applying class masking on collection {collection_id} using taxa list {taxa_list_id}")

        # @TODO temporary, do we need a new algorithm for each class mask?
        self.algorithm.category_map = algorithm.category_map  # Ensure the algorithm has its category map loaded

        update_occurrences_in_collection(
            collection=collection,
            taxa_list=taxa_list,
            algorithm=algorithm,
            params=self.config,
            task_logger=self.logger,
            job=job,
            new_algorithm=self.algorithm,
        )

        self.logger.info("Class masking completed successfully.")
        self.logger.info(f"=== Completed {self.name} ===")
