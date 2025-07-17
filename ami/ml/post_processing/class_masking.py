import logging

from ami.main.models import Classification, Occurrence, SourceImageCollection, TaxaList
from ami.ml.models import Algorithm, AlgorithmCategoryMap

logger = logging.getLogger(__name__)


def make_classifications_filtered_by_taxa_list(
    collection: SourceImageCollection,
    taxa_list: TaxaList,
    algorithm: Algorithm,
    params: dict,
    task_logger: logging.Logger = logger,
    job=None,
):
    task_logger.info(f"Recalculating classifications based on a taxa list. Params: {params}")

    taxa_in_list = taxa_list.taxa.all()

    # Make new AlgorithmCategoryMap with the taxa in the list
    # @TODO

    classifications = Classification.objects.filter(
        detection__source_image__collections=collection,
        terminal=True,
        # algorithm__task_type="classification",
        algorithm=algorithm,
        scores__isnull=False,
    ).distinct()

    occurrences_to_update: set[Occurrence] = set()
    logger.info(f"Found {len(classifications)} terminal classifications")

    first_classification = classifications.first()
    assert first_classification is not None, "No terminal classifications found in the collection."
    first_algorithm: Algorithm = first_classification.algorithm
    assert first_algorithm is not None, "No algorithm found for the terminal classifications."
    category_map: AlgorithmCategoryMap = first_algorithm.category_map

    # Consider moving this to a method on the Classification model

    category_map_with_taxa = category_map.with_taxa()
    # Filter the category map to only include taxa that are in the taxa list
    # included_category_map_with_taxa = [
    #     category for category in category_map_with_taxa if category["taxon"] in taxa_in_list
    # ]
    excluded_category_map_with_taxa = [
        category for category in category_map_with_taxa if category["taxon"] not in taxa_in_list
    ]
    # included_category_indices = [int(category["index"]) for category in category_map_with_taxa]
    excluded_category_indices = [int(category["index"]) for category in excluded_category_map_with_taxa]

    # Log number of categories in the category map, num included, and num excluded, num classifications to update

    logger.info(
        f"Category map has {len(category_map_with_taxa)} categories, "
        f"{len(excluded_category_map_with_taxa)} categories excluded, "
        f"{len(classifications)} classifications to check"
    )

    classifications_to_update = []

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

        scores_np = np.array(scores)
        logits_np = np.array(logits)

        scores_np[excluded_category_indices] = 0.0
        logits_np[excluded_category_indices] = 0.0

        scores = scores_np.tolist()
        logits = logits_np.tolist()

        # check if needs updating
        if classification.scores == scores and classification.logits == logits:
            logger.debug(f"Classification {classification.pk} does not need updating")
            continue

        classification.scores = scores
        classification.logits = logits
        classifications_to_update.append(classification)

        logger.info(f"New totals: {sum(scores)} scores, {sum(logits)} logits")

    # Bulk save the classifications
    Classification.objects.bulk_update(
        classifications_to_update,
        fields=["scores", "logits"],
    )

    logger.info(f"Updated {len(classifications_to_update)} classifications")

    # Update the occurrence determinations
    for occurrence in occurrences_to_update:
        occurrence.save(update_determination=True)
