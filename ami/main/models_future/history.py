"""An occurrence's history: what algorithms and people did to it, newest first.

What a post-processing run decided about an occurrence is an ``AlgorithmResult``. Identifications
and predictions keep their own tables, and ``occurrence_timeline`` merges all three into one list
for the history endpoint.
"""

from __future__ import annotations

import dataclasses
import datetime
import typing

from django.db.models import Q

from ami.main.models import Classification, Identification, Occurrence, TaxaList, Taxon, User
from ami.ml.models import Algorithm, AlgorithmResult

if typing.TYPE_CHECKING:
    from ami.jobs.models import Job


@dataclasses.dataclass
class TimelineEntry:
    """One entry of the merged history, in the shape ``OccurrenceHistoryEntrySerializer`` reads."""

    type: str
    id: int
    timestamp: datetime.datetime
    subtype: str | None = None
    user: User | None = None
    algorithm: Algorithm | None = None
    job: Job | None = None
    taxon: Taxon | None = None
    taxon_before: Taxon | None = None
    score: float | None = None
    payload: dict = dataclasses.field(default_factory=dict)
    comment: str = ""
    withdrawn: bool = False
    is_current: bool | None = None
    # For a result: the classifications the run created, best score first.
    classifications: list[Classification] = dataclasses.field(default_factory=list)
    # For a class masking result: the source classifier's top taxon before masking, the species
    # list and the classifier, the latter two from the job's settings.
    original_taxon: Taxon | None = None
    taxa_list: TaxaList | None = None
    source_algorithm: Algorithm | None = None


def occurrence_timeline(occurrence: Occurrence) -> list[TimelineEntry]:
    """Results, identifications and predictions of one occurrence, merged newest first.

    A result comes with the classifications its run created, so the history shows the run and
    what it changed as one entry; those classifications are not listed again as predictions.
    Every other algorithm contributes one prediction, its best. A prediction names the result
    that superseded it when a result's classification re-scored it, or when a result's
    classification on the same detection outranks it as a terminal prediction. The query count
    does not grow with the entries.
    """
    results = list(
        AlgorithmResult.objects.filter(occurrence=occurrence)
        .select_related("algorithm", "job")
        .order_by("-timestamp", "-pk")
    )
    settings = {result.pk: _job_settings(result.job) for result in results}
    taxa = _by_id(
        Taxon,
        {
            result.data.get(key)
            for result in results
            for key in ("determination_before_id", "determination_after_id", "original_taxon_id")
        },
    )
    taxa_lists = _by_id(TaxaList, {config.get("taxa_list_id") for config in settings.values()})
    source_algorithms = _by_id(Algorithm, {config.get("algorithm_id") for config in settings.values()})
    created_by_result = _classifications_created_by(results, occurrence)
    created_ids = {c.pk for created in created_by_result.values() for c in created}
    rescored_by = {
        c.applied_to_id: result_id
        for result_id, created in created_by_result.items()
        for c in created
        if c.applied_to_id is not None
    }
    # Only a classification that re-scored nothing (the size filter's) supersedes by detection; a
    # re-scored one names its original through applied_to, so other classifiers stay unmarked.
    outranked_by = {
        c.detection_id: result_id
        for result_id, created in created_by_result.items()
        for c in created
        if c.applied_to_id is None
    }

    def superseded_by(prediction: Classification) -> int | None:
        if prediction.pk in rescored_by:
            return rescored_by[prediction.pk]
        if prediction.terminal:
            return outranked_by.get(prediction.detection_id)
        return None

    entries = [
        TimelineEntry(
            type="algorithm_result",
            id=result.pk,
            timestamp=result.timestamp,
            subtype=result.kind,
            algorithm=result.algorithm,
            job=result.job,
            taxon=taxa.get(result.data.get("determination_after_id")),
            taxon_before=taxa.get(result.data.get("determination_before_id")),
            score=result.value,
            payload=result.data,
            is_current=result.is_current,
            classifications=created_by_result.get(result.pk, []),
            original_taxon=taxa.get(result.data.get("original_taxon_id")),
            taxa_list=taxa_lists.get(settings[result.pk].get("taxa_list_id")),
            source_algorithm=source_algorithms.get(settings[result.pk].get("algorithm_id")),
        )
        for result in results
    ]

    identifications = Identification.objects.filter(occurrence=occurrence).select_related("user", "taxon")
    entries.extend(
        TimelineEntry(
            type="identification",
            id=identification.pk,
            timestamp=identification.created_at,
            user=identification.user,
            taxon=identification.taxon,
            comment=identification.comment or "",
            withdrawn=identification.withdrawn,
            payload={
                "comment": identification.comment,
                "withdrawn": identification.withdrawn,
                "agreed_with_identification_id": identification.agreed_with_identification_id,
                "agreed_with_prediction_id": identification.agreed_with_prediction_id,
            },
        )
        for identification in identifications
    )

    entries.extend(
        TimelineEntry(
            type="prediction",
            id=prediction.pk,
            timestamp=prediction.created_at,
            algorithm=prediction.algorithm,
            taxon=prediction.taxon,
            score=prediction.score,
            payload={
                "detection_id": prediction.detection_id,
                "terminal": prediction.terminal,
                "applied_to_id": prediction.applied_to_id,
                "superseded_by_result_id": superseded_by(prediction),
            },
        )
        for prediction in _one_prediction_per_algorithm(occurrence)
        if prediction.pk not in created_ids
    )

    entries.sort(key=lambda entry: (entry.timestamp, entry.id), reverse=True)
    return entries


def _job_settings(job: Job | None) -> dict:
    """The settings a post-processing job ran with, or an empty dict for any other job."""
    config = (job.params or {}).get("config") if job is not None else None
    return config if isinstance(config, dict) else {}


def _by_id(model, ids: set) -> dict:
    ids.discard(None)
    return {row.pk: row for row in model.objects.filter(pk__in=ids)} if ids else {}


def _classifications_created_by(
    results: list[AlgorithmResult], occurrence: Occurrence
) -> dict[int, list[Classification]]:
    """The classifications each result's run created on the occurrence, keyed by result id.

    A classification names its result directly through ``algorithm_result``. One written by a
    run before that link existed is matched through its job instead; when that job left more
    than one result on the occurrence, the latest takes it.
    """
    if not results:
        return {}
    result_by_job = {}
    for result in reversed(results):
        if result.job_id is not None:
            result_by_job[result.job_id] = result.pk
    created = (
        Classification.objects.filter(detection__occurrence=occurrence)
        .filter(
            Q(algorithm_result_id__in=[result.pk for result in results])
            | Q(algorithm_result__isnull=True, job_id__in=list(result_by_job))
        )
        .select_related("taxon", "algorithm")
        # The score arrays can hold tens of thousands of values per row and are not shown here.
        .defer("scores", "logits")
        .order_by("-score", "-pk")
    )
    by_result: dict[int, list[Classification]] = {}
    for classification in created:
        result_id = classification.algorithm_result_id or result_by_job[classification.job_id]
        by_result.setdefault(result_id, []).append(classification)
    return by_result


def _one_prediction_per_algorithm(occurrence: Occurrence) -> list[Classification]:
    """The best prediction of each algorithm: highest score, then terminal, then latest.

    ``Occurrence.predictions()`` keeps every classification tied for an algorithm's top
    score, which would show the same prediction once per detection.
    """

    def rank(prediction: Classification) -> tuple:
        score = prediction.score if prediction.score is not None else float("-inf")
        return (score, prediction.terminal, prediction.created_at, prediction.pk)

    best: dict[int | None, Classification] = {}
    for prediction in occurrence.predictions().defer("scores", "logits"):
        current = best.get(prediction.algorithm_id)
        if current is None or rank(prediction) > rank(current):
            best[prediction.algorithm_id] = prediction
    return list(best.values())
