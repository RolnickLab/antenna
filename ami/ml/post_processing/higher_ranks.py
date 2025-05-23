import logging

from django.utils.timezone import now

from ami.main.models import Classification, Occurrence, SourceImageCollection

logger = logging.getLogger(__name__)


def make_higher_rank_classifications(
    collection: SourceImageCollection, params: dict, task_logger: logging.Logger = logger, job=None
):

    task_logger.info(f"Calculating scores for higher ranks with params: {params}")

    classifications = Classification.objects.filter(
        detection__source_image__collections=collection,
        terminal=True,
        algorithm__task_type="classification",
        scores__isnull=False,
    ).distinct()

    occurrences_to_update: set[Occurrence] = set()
    logger.info(f"Found {len(classifications)} terminal classifications")

    for classification in classifications:
        logger.info(f"Creating higher rank classification for {classification.pk}")
        taxa_and_scores = classification.genus_scores_by_splitting_names()
        # unzip the list of tuples into two lists
        taxa, scores = zip(*taxa_and_scores)
        higher_rank_classification = Classification.objects.create(
            taxon=taxa[0],
            algorithm=classification.algorithm,
            score=scores[0],
            scores=scores,
            detection=classification.detection,
            timestamp=classification.timestamp,
            terminal=False,
            # category_map=classification.category_map, @TODO create new category map
            created_at=now(),
            updated_at=now(),
        )
        logger.debug(f"Created higher rank classification {higher_rank_classification.pk}")
        if classification.detection and classification.detection.occurrence:
            occurrences_to_update.add(classification.detection.occurrence)

    # Update the occurrence determinations
    for occurrence in occurrences_to_update:
        occurrence.save(update_determination=True)
