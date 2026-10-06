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

from django.db.models import Exists, OuterRef, Q, QuerySet

from ami.main.models import Classification, Identification, Occurrence, OccurrenceSet, Taxon
from ami.ml.models.algorithm import Algorithm

logger = logging.getLogger(__name__)


class NothingToScore(Exception):
    """The set holds no occurrence this algorithm was asked about."""


def predictable_taxon_ids(algorithm: Algorithm) -> set[int]:
    """
    The taxa this algorithm can answer with, as ids.

    Resolved to taxa rather than compared as strings. A category map label is the name the
    model was trained under, which is not always the name the taxon is stored under here,
    so comparing the two as text silently drops every species whose spelling or authorship
    differs and makes the model look like it was never asked about them.

    The lookup matches AlgorithmCategoryMap.with_taxa so the two cannot disagree about
    which label means which taxon: by name, or by any name the taxon is also known as.
    """
    if not algorithm.category_map:
        return set()
    labels = [str(label) for label in (algorithm.category_map.labels or [])]
    if not labels:
        return set()
    return set(
        Taxon.objects.filter(
            Q(name__in=labels) | Q(search_names__overlap=labels),
            active=True,
        ).values_list("pk", flat=True)
    )


def occurrences_to_score(occurrence_set: OccurrenceSet, algorithm: Algorithm) -> QuerySet[Occurrence]:
    """
    Occurrences in the set that a person has identified.

    The filter is on the identification rather than on determination being set, because
    update_occurrence_determination falls back to the top prediction when nobody has
    identified an occurrence. Filtering on determination alone therefore scores an
    algorithm against its own guess, which reads as perfect accuracy.

    Truth is still read off determination: for an identified occurrence that is the
    identification's taxon, and it is how the rest of the platform counts a verification
    (see verified_taxon_counts).
    """
    return (
        occurrence_set.occurrences.filter(
            Exists(Identification.objects.filter(occurrence=OuterRef("pk"), withdrawn=False)),
            determination__isnull=False,
        )
        .select_related("determination")
        .order_by("pk")
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
    answerable = predictable_taxon_ids(algorithm)
    if not answerable:
        raise NothingToScore(
            f"Algorithm '{algorithm.key}' has no category map whose labels match a taxon here, "
            "so there is no way to know which species it was asked about."
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
        if truth.pk not in answerable:
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
    # The denominators an accuracy has to be read against. A head that answers for 749
    # species can score 1.00 on the six of them this set happens to contain, and without
    # these two numbers nothing on the page says so.
    species_in_set = len({occurrence.determination_id for occurrence in occurrences})
    return {
        "micro_accuracy": correct / scored,
        "macro_accuracy": sum(accuracies) / len(accuracies),
        "occurrences_scored": scored,
        "occurrences_skipped": skipped,
        "species_scored": len(per_taxon),
        "species_in_set": species_in_set,
        "species_predictable": len(answerable),
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
