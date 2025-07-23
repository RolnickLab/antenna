import logging

from django.db.models import QuerySet
from django.utils import timezone

from ami.main.models import Classification, Occurrence, SourceImageCollection, TaxaList
from ami.ml.models import Algorithm, AlgorithmCategoryMap

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
    ).distinct()

    make_classifications_filtered_by_taxa_list(
        classifications=classifications,
        taxa_list=taxa_list,
        algorithm=algorithm,
    )


def update_occurrences_in_collection(
    collection: SourceImageCollection,
    taxa_list: TaxaList,
    algorithm: Algorithm,
    params: dict,
    task_logger: logging.Logger = logger,
    job=None,
):
    task_logger.info(f"Recalculating classifications based on a taxa list. Params: {params}")

    # Make new AlgorithmCategoryMap with the taxa in the list
    # @TODO

    classifications = Classification.objects.filter(
        detection__source_image__collections=collection,
        terminal=True,
        # algorithm__task_type="classification",
        algorithm=algorithm,
        scores__isnull=False,
    ).distinct()

    make_classifications_filtered_by_taxa_list(
        classifications=classifications,
        taxa_list=taxa_list,
        algorithm=algorithm,
    )


def make_classifications_filtered_by_taxa_list(
    classifications: QuerySet[Classification],
    taxa_list: TaxaList,
    algorithm: Algorithm,
):
    taxa_in_list = taxa_list.taxa.all()

    occurrences_to_update: set[Occurrence] = set()
    logger.info(f"Found {len(classifications)} terminal classifications with scores to update.")

    if not classifications:
        raise ValueError("No terminal classifications with scores found to update.")

    if not algorithm.category_map:
        raise ValueError(f"Algorithm {algorithm} does not have a category map.")
    category_map: AlgorithmCategoryMap = algorithm.category_map

    # Consider moving this to a method on the Classification model

    # @TODO find a more efficient way to get the category map with taxa. This is slow!
    logger.info(f"Retrieving category map with Taxa instances for algorithm {algorithm}")
    category_map_with_taxa = category_map.with_taxa()
    # Filter the category map to only include taxa that are in the taxa list
    # included_category_map_with_taxa = [
    #     category for category in category_map_with_taxa if category["taxon"] in taxa_in_list
    # ]
    excluded_category_map_with_taxa = [
        category for category in category_map_with_taxa if category["taxon"] not in taxa_in_list
    ]

    # included_category_indices = [int(category["index"]) for category in category_map_with_taxa]
    excluded_category_indices = [
        int(category["index"]) for category in excluded_category_map_with_taxa  # type: ignore
    ]

    # Log number of categories in the category map, num included, and num excluded, num classifications to update
    logger.info(
        f"Category map has {len(category_map_with_taxa)} categories, "
        f"{len(excluded_category_map_with_taxa)} categories excluded, "
        f"{len(classifications)} classifications to check"
    )

    classifications_to_add = []

    for classification in classifications:
        scores, logits = classification.scores, classification.logits
        # Set scores and logits to zero if they are not in the filtered category indices

        import numpy as np

        # Assert that all scores & logits are lists of numbers
        if not isinstance(scores, list) or not all(isinstance(score, (int, float)) for score in scores):
            raise ValueError(f"Scores for classification {classification.pk} are not a list of numbers: {scores}")
        if not isinstance(logits, list) or not all(isinstance(logit, (int, float)) for logit in logits):
            raise ValueError(f"Logits for classification {classification.pk} are not a list of numbers: {logits}")

        logger.debug(f"Processing classification {classification.pk} with {len(scores)} scores")
        logger.info(f"Previous totals: {sum(scores)} scores, {sum(logits)} logits")

        # scores_np_filtered = np.array(scores)
        logits_np = np.array(logits)

        # scores_np_filtered[excluded_category_indices] = 0.0

        # @TODO can we use np.NAN instead of 0.0? zero will NOT calculate correctly in softmax.
        # @TODO delete the excluded categories from the scores and logits instead of setting to 0.0
        # logits_np[excluded_category_indices] = 0.0
        # logits_np[excluded_category_indices] = np.nan
        logits_np[excluded_category_indices] = -100

        logits: list[float] = logits_np.tolist()

        from numpy import exp
        from numpy import sum as np_sum

        # @TODO add test to see if this is correct, or needed!
        # Recalculate the softmax scores based on the filtered logits
        scores_np: np.ndarray = exp(logits_np - np.max(logits_np))  # Subtract max for numerical stability
        scores_np /= np_sum(scores_np)  # Normalize to get probabilities

        scores: list = scores_np.tolist()  # Convert back to list

        logger.info(f"New totals: {sum(scores)} scores, {sum(logits)} logits")

        # Get the taxon with the highest score  using the index of the max score
        top_index = scores.index(max(scores))
        top_taxon = category_map_with_taxa[top_index]["taxon"]

        # check if needs updating
        if classification.scores == scores and classification.logits == logits:
            logger.debug(f"Classification {classification.pk} does not need updating")
            continue

        # Recalculate the top taxon and score
        new_classification = Classification(
            taxon=top_taxon,
            algorithm=classification.algorithm,
            score=max(scores),
            scores=scores,
            logits=logits,
            detection=classification.detection,
            timestamp=classification.timestamp,
            terminal=True,
            category_map=None,  # @TODO need a new category map with the filtered taxa
            created_at=timezone.now(),
            updated_at=timezone.now(),
        )

        classifications_to_add.append(new_classification)

        assert new_classification.detection is not None
        assert new_classification.detection.occurrence is not None
        occurrences_to_update.add(new_classification.detection.occurrence)

        logging.info(
            f"Adding new classification for Taxon {top_taxon} to occurrence {new_classification.detection.occurrence}"
        )

    # Bulk create the new classifications
    logger.info(f"Bulk creating {len(classifications_to_add)} new classifications")
    Classification.objects.bulk_create(classifications_to_add)
    logger.info(f"Added {len(classifications_to_add)} new classifications")

    # Update the occurrence determinations
    logger.info(f"Updating the determinations for {len(occurrences_to_update)} occurrences")
    for occurrence in occurrences_to_update:
        occurrence.save(update_determination=True)
    logger.info(f"Updated determinations for {len(occurrences_to_update)} occurrences")
