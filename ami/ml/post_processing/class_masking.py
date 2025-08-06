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

    update_occurrences_in_collection(
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

    update_occurrences_in_collection(
        classifications=classifications,
        taxa_list=taxa_list,
        algorithm=algorithm,
    )
