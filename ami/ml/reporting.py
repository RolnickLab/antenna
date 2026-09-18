"""
The numbers the model-performance views read.

Each of these answers one question a screen asks, in a single query. They are kept apart
from the models so a view can ask for them without pulling in the training machinery, and
so the same number means the same thing everywhere it is shown.
"""

import typing

from ami.main.models import TaxaList, Taxon
from ami.ml.models.algorithm import Algorithm
from ami.ml.models.evaluation import AlgorithmEvaluation, TaxonEvaluation

DEFAULT_EVALUATION_LIMIT = 5


def best_evaluation_for_taxa_list(taxa_list: TaxaList) -> AlgorithmEvaluation | None:
    """
    The algorithm that scores highest on the species in this list.

    Ranked on the per-species average rather than the plain share: trap data is long-tailed,
    so a model that only handles the common species would otherwise look like the best one.
    """
    # No .distinct(): the join repeats an evaluation once per species it scored in the list,
    # which cannot change which row sorts first.
    return (
        AlgorithmEvaluation.objects.filter(taxa__taxon__lists=taxa_list)
        .select_related("algorithm", "occurrence_set")
        .order_by("-macro_accuracy", "-micro_accuracy")
        .first()
    )


def performance_for_taxon(taxon: Taxon) -> list[dict[str, typing.Any]]:
    """
    How each algorithm has done on one species.

    The breakdown the taxon page shows: one row per algorithm that has been scored on a set
    containing this species.
    """
    rows = (
        TaxonEvaluation.objects.filter(taxon=taxon)
        .select_related("evaluation__algorithm", "evaluation__occurrence_set")
        .order_by("-accuracy")
    )
    return [
        {
            "algorithm": {
                "id": row.evaluation.algorithm_id,
                "name": row.evaluation.algorithm.name,
                "key": row.evaluation.algorithm.key,
                "version": row.evaluation.algorithm.version,
            },
            "occurrence_set": {
                "id": row.evaluation.occurrence_set_id,
                "name": row.evaluation.occurrence_set.name,
            },
            "accuracy": row.accuracy,
            "occurrences_scored": row.occurrences_scored,
            "correct": row.correct,
            "overall_accuracy": row.evaluation.micro_accuracy,
            "overall_accuracy_by_species": row.evaluation.macro_accuracy,
        }
        for row in rows
    ]


def latest_evaluations(algorithm: Algorithm, limit: int = DEFAULT_EVALUATION_LIMIT) -> list[dict[str, typing.Any]]:
    """
    What this algorithm has scored, most recent first. Shown on its details panel.

    Read through the related manager without filtering or reordering, so a list view that
    prefetched the evaluations is served from that cache instead of one query per row.
    """
    rows = sorted(algorithm.evaluations.all(), key=lambda row: row.created_at, reverse=True)[:limit]
    return [
        {
            "id": row.pk,
            "occurrence_set": {"id": row.occurrence_set_id, "name": row.occurrence_set.name},
            "accuracy": row.micro_accuracy,
            "accuracy_by_species": row.macro_accuracy,
            "occurrences_scored": row.occurrences_scored,
            "occurrences_skipped": row.occurrences_skipped,
            "species_scored": row.species_scored,
            "created_at": row.created_at,
        }
        for row in rows
    ]
