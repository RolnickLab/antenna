"""
Score an algorithm against a fixed set of occurrences people have verified.

The comparison is between what a person said and what the algorithm predicted, both of
which are already in the database. No images are opened and no model runs: an algorithm
that has processed the set can be scored in a single pass over its classifications.

An algorithm is only asked about species it can actually predict. Its category map is the
list of answers available to it, so an occurrence of anything else is left out rather than
counted wrong — otherwise a regional head looks bad for not knowing a species nobody
trained it on.
"""

import collections
import logging
import typing

from django.db.models import QuerySet

from ami.main.models import Classification, Occurrence
from ami.ml.models.algorithm import Algorithm
from ami.ml.models.evaluation import OccurrenceSet

logger = logging.getLogger(__name__)


class NothingToScore(Exception):
    """The set holds no occurrence this algorithm was asked about."""


def predictable_taxa(algorithm: Algorithm) -> set[str]:
    """The species names this algorithm can answer with."""
    if not algorithm.category_map:
        return set()
    return {str(label) for label in (algorithm.category_map.labels or [])}


def occurrences_to_score(occurrence_set: OccurrenceSet, algorithm: Algorithm) -> QuerySet[Occurrence]:
    """Occurrences in the set that carry a human determination."""
    return (
        occurrence_set.occurrences.filter(determination__isnull=False).select_related("determination").order_by("pk")
    )


def predictions_for(occurrence_ids: list[int], algorithm: Algorithm) -> dict[int, int]:
    """
    This algorithm's latest prediction per occurrence, as occurrence id to taxon id.

    One query rather than one per occurrence: an evaluation set runs to thousands of rows.
    Ordered by score so the strongest classification on a detection wins.
    """
    rows = (
        Classification.objects.filter(
            algorithm=algorithm,
            detection__occurrence_id__in=occurrence_ids,
            taxon__isnull=False,
        )
        .order_by("detection__occurrence_id", "-score")
        .values_list("detection__occurrence_id", "taxon_id")
    )
    best: dict[int, int] = {}
    for occurrence_id, taxon_id in rows:
        best.setdefault(occurrence_id, taxon_id)
    return best


def score(occurrence_set: OccurrenceSet, algorithm: Algorithm) -> dict[str, typing.Any]:
    """
    Compare an algorithm's predictions against what people verified.

    Returns overall accuracy, a per-species breakdown, and how much of the set was left
    out. Raises NothingToScore when the algorithm has never run on the set, so that reads
    as a missing step rather than an accuracy of zero.
    """
    answerable = predictable_taxa(algorithm)
    if not answerable:
        raise NothingToScore(
            f"Algorithm '{algorithm.key}' has no category map, so there is no way to know "
            "which species it was asked about."
        )

    occurrences = list(occurrences_to_score(occurrence_set, algorithm))
    if not occurrences:
        raise NothingToScore(f"'{occurrence_set.name}' holds no verified occurrence to score.")

    predictions = predictions_for([o.pk for o in occurrences], algorithm)
    if not predictions:
        raise NothingToScore(
            f"Algorithm '{algorithm.key}' has not classified anything in '{occurrence_set.name}'. "
            "Run it over the set first, then evaluate."
        )

    per_taxon: dict[int, dict[str, typing.Any]] = collections.defaultdict(
        lambda: {"scored": 0, "correct": 0, "taxon": None}
    )
    scored = 0
    correct = 0
    skipped = 0

    for occurrence in occurrences:
        truth = occurrence.determination
        if truth.name not in answerable:
            skipped += 1
            continue
        predicted = predictions.get(occurrence.pk)
        if predicted is None:
            skipped += 1
            continue

        bucket = per_taxon[truth.pk]
        bucket["taxon"] = truth
        bucket["scored"] += 1
        scored += 1
        if predicted == truth.pk:
            bucket["correct"] += 1
            correct += 1

    if not scored:
        raise NothingToScore(f"None of the species in '{occurrence_set.name}' are ones '{algorithm.key}' can predict.")

    accuracies = [b["correct"] / b["scored"] for b in per_taxon.values() if b["scored"]]
    return {
        "micro_accuracy": correct / scored,
        "macro_accuracy": sum(accuracies) / len(accuracies),
        "occurrences_scored": scored,
        "occurrences_skipped": skipped,
        "species_scored": len(per_taxon),
        "per_taxon": [
            {
                "taxon": bucket["taxon"],
                "accuracy": bucket["correct"] / bucket["scored"],
                "occurrences_scored": bucket["scored"],
                "correct": bucket["correct"],
            }
            for bucket in per_taxon.values()
            if bucket["scored"]
        ],
    }


def save_evaluation(occurrence_set: OccurrenceSet, algorithm: Algorithm, result: dict, job=None):
    """
    Store a score, replacing any earlier one for the same algorithm and set.

    Replaced rather than appended: the pair is unique, and a second run over the same set
    is a correction, not a new fact.
    """
    from ami.ml.models.evaluation import AlgorithmEvaluation, TaxonEvaluation

    evaluation, _ = AlgorithmEvaluation.objects.update_or_create(
        algorithm=algorithm,
        occurrence_set=occurrence_set,
        defaults={
            "job": job,
            "micro_accuracy": result["micro_accuracy"],
            "macro_accuracy": result["macro_accuracy"],
            "occurrences_scored": result["occurrences_scored"],
            "occurrences_skipped": result["occurrences_skipped"],
            "species_scored": result["species_scored"],
        },
    )
    evaluation.taxa.all().delete()
    TaxonEvaluation.objects.bulk_create(
        [
            TaxonEvaluation(
                evaluation=evaluation,
                taxon=row["taxon"],
                accuracy=row["accuracy"],
                occurrences_scored=row["occurrences_scored"],
                correct=row["correct"],
            )
            for row in result["per_taxon"]
        ],
        batch_size=500,
    )
    logger.info(
        f"Scored {algorithm.key} on '{occurrence_set.name}': "
        f"{result['micro_accuracy']:.3f} over {result['occurrences_scored']} occurrences"
    )
    return evaluation
