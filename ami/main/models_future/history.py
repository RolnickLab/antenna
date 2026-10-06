"""An occurrence's history: what algorithms and people did to it, newest first.

``occurrence_timeline`` merges an occurrence's algorithm results, identifications and predictions
into one list of ``OccurrenceTimelineEntry`` for the history endpoint. What a post-processing run
decided about an occurrence is an ``AlgorithmResult``; identifications and predictions keep their
own tables.
"""

from __future__ import annotations

import dataclasses
import datetime
import typing

from ami.main.models import Classification, Identification, Occurrence, Taxon, User
from ami.main.models_future.references import Ref, job_setting_references, resolve_references
from ami.ml.models import Algorithm, AlgorithmResult
from ami.ml.post_processing.registry import config_setting_labels
from ami.ml.results.schemas import reference_fields, result_kinds

if typing.TYPE_CHECKING:
    from ami.jobs.models import Job


@dataclasses.dataclass
class JobSetting:
    """One setting a job ran with: its label from the task's config schema, and the record it names, if any."""

    key: str
    label: str
    value: typing.Any
    ref: Ref | None = None


@dataclasses.dataclass
class CreatedClassification:
    """A classification a run created, with the one it replaced (through applied_to), if that still exists."""

    classification: Classification
    replaced: Classification | None


@dataclasses.dataclass
class OccurrenceTimelineEntry:
    """One entry of an occurrence's merged history. Sections below say which fields each type fills."""

    # --- Every entry
    type: str  # "algorithm_result" | "identification" | "prediction"
    id: int
    timestamp: datetime.datetime
    user: User | None = None  # identification
    algorithm: Algorithm | None = None  # result, prediction
    job: Job | None = None  # result, prediction
    job_settings: list[JobSetting] = dataclasses.field(default_factory=list)  # empty without a job
    taxon: Taxon | None = None  # identification, prediction
    score: float | None = None  # prediction
    # --- Algorithm result
    kind: str | None = None
    value: float | None = None  # the kind's headline figure, not a confidence
    data: dict = dataclasses.field(default_factory=dict)  # validated per kind
    data_references: dict[str, Ref] = dataclasses.field(default_factory=dict)  # data field -> Ref
    determination_before: Taxon | None = None
    determination_after: Taxon | None = None
    classifications: list[CreatedClassification] = dataclasses.field(default_factory=list)
    is_current: bool | None = None
    # --- Identification and prediction
    details: dict = dataclasses.field(default_factory=dict)


def occurrence_timeline(occurrence: Occurrence) -> list[OccurrenceTimelineEntry]:
    """Results, identifications and predictions of one occurrence, merged newest first.

    A result comes with the classifications its run created, so the history shows the run and
    what it changed as one entry; those classifications are not listed again as predictions.
    Every other algorithm contributes one prediction, its best. A prediction names the result
    that superseded it when a result's classification re-scored it, or when a result's
    classification on the same detection outranks it as a terminal prediction. Ids the entries
    show are resolved to references with one query per type. The query count does not grow
    with the entries.
    """
    results = list(
        AlgorithmResult.objects.filter(occurrence=occurrence)
        .select_related("algorithm", "job")
        .order_by("-timestamp", "-pk")
    )
    taxa = _by_id(
        Taxon,
        {result.data.get(key) for result in results for key in ("determination_before_id", "determination_after_id")},
    )
    created_by_result = _classifications_created_by(results, occurrence)
    created_ids = {c.classification.pk for created in created_by_result.values() for c in created}
    rescored_by = {
        c.classification.applied_to_id: result_id
        for result_id, created in created_by_result.items()
        for c in created
        if c.classification.applied_to_id is not None
    }
    # Only a classification that re-scored nothing (the size filter's) supersedes by detection; a
    # re-scored one names its original through applied_to, so other classifiers stay unmarked.
    outranked_by = {
        c.classification.detection_id: result_id
        for result_id, created in created_by_result.items()
        for c in created
        if c.classification.applied_to_id is None
    }

    def superseded_by(prediction: Classification) -> int | None:
        if prediction.pk in rescored_by:
            return rescored_by[prediction.pk]
        if prediction.terminal:
            return outranked_by.get(prediction.detection_id)
        return None

    entries = [
        OccurrenceTimelineEntry(
            type="algorithm_result",
            id=result.pk,
            timestamp=result.timestamp,
            algorithm=result.algorithm,
            job=result.job,
            value=result.value,
            kind=result.kind,
            data=result.data,
            determination_before=taxa.get(result.data.get("determination_before_id")),
            determination_after=taxa.get(result.data.get("determination_after_id")),
            classifications=created_by_result.get(result.pk, []),
            is_current=result.is_current,
        )
        for result in results
    ]

    identifications = Identification.objects.filter(occurrence=occurrence).select_related("user", "taxon")
    entries.extend(
        OccurrenceTimelineEntry(
            type="identification",
            id=identification.pk,
            timestamp=identification.created_at,
            user=identification.user,
            taxon=identification.taxon,
            details={
                "comment": identification.comment or "",
                "withdrawn": identification.withdrawn,
                "agreed_with_identification_id": identification.agreed_with_identification_id,
                "agreed_with_prediction_id": identification.agreed_with_prediction_id,
            },
        )
        for identification in identifications
    )

    entries.extend(
        OccurrenceTimelineEntry(
            type="prediction",
            id=prediction.pk,
            timestamp=prediction.created_at,
            algorithm=prediction.algorithm,
            job=prediction.job,
            taxon=prediction.taxon,
            score=prediction.score,
            details={
                "detection_id": prediction.detection_id,
                "terminal": prediction.terminal,
                "applied_to_id": prediction.applied_to_id,
                "superseded_by_result_id": superseded_by(prediction),
            },
        )
        for prediction in _one_prediction_per_algorithm(occurrence)
        if prediction.pk not in created_ids
    )

    _fill_job_settings_and_references(entries)
    entries.sort(key=lambda entry: (entry.timestamp, entry.id), reverse=True)
    return entries


def _fill_job_settings_and_references(entries: list[OccurrenceTimelineEntry]) -> None:
    """Fill each entry's job settings and data references, resolving every id the entries name at once."""
    configs = {id(entry): _job_settings(entry.job) for entry in entries if entry.job is not None}
    job_refs = {key: job_setting_references(config) for key, config in configs.items()}
    # A stored kind may no longer be registered (renamed, or written by another branch); it names no references.
    kinds = set(result_kinds())
    data_refs = {
        id(entry): [
            (field, ref_type, entry.data[field])
            for field, ref_type in (reference_fields(entry.kind) if entry.kind in kinds else {}).items()
            if isinstance(entry.data.get(field), int)
        ]
        for entry in entries
        if entry.type == "algorithm_result"
    }
    wanted = [(ref_type, ref_id) for refs in (*job_refs.values(), *data_refs.values()) for _, ref_type, ref_id in refs]
    resolved = resolve_references(wanted) if wanted else {}
    for entry in entries:
        if entry.job is not None:
            labels = config_setting_labels((entry.job.params or {}).get("task"))
            refs = {key: resolved[(t, i)] for key, t, i in job_refs[id(entry)]}
            entry.job_settings = [
                JobSetting(key, labels.get(key, key), value, refs.get(key))
                for key, value in configs[id(entry)].items()
            ]
        entry.data_references = {field: resolved[(t, i)] for field, t, i in data_refs.get(id(entry), [])}


def _job_settings(job: Job | None) -> dict:
    """The settings a post-processing job ran with, or an empty dict for any other job."""
    config = (job.params or {}).get("config") if job is not None else None
    return config if isinstance(config, dict) else {}


def _by_id(model, ids: set) -> dict:
    ids.discard(None)
    return {row.pk: row for row in model.objects.filter(pk__in=ids)} if ids else {}


def _classifications_created_by(
    results: list[AlgorithmResult], occurrence: Occurrence
) -> dict[int, list[CreatedClassification]]:
    """The classifications each result's run created on the occurrence, keyed by result id.

    A classification names its result through ``algorithm_result``. Each comes with the
    classification it replaced, read in one more query.
    """
    if not results:
        return {}
    created = list(
        Classification.objects.filter(
            detection__occurrence=occurrence, algorithm_result_id__in=[result.pk for result in results]
        )
        .select_related("taxon", "algorithm")
        # The score arrays can hold tens of thousands of values per row and are not shown here.
        .defer("scores", "logits")
        .order_by("-score", "-pk")
    )
    # A separate query, not select_related("applied_to"): .defer() does not reach a self-join,
    # so the replaced rows' score arrays would load.
    replaced_ids = {c.applied_to_id for c in created if c.applied_to_id is not None}
    replaced = (
        {
            c.pk: c
            for c in Classification.objects.filter(pk__in=replaced_ids)
            .select_related("taxon")
            .only("pk", "score", "taxon", "taxon__name", "taxon__rank")
        }
        if replaced_ids
        else {}
    )
    by_result: dict[int, list[CreatedClassification]] = {}
    for classification in created:
        by_result.setdefault(classification.algorithm_result_id, []).append(
            CreatedClassification(classification, replaced.get(classification.applied_to_id))
        )
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
    for prediction in occurrence.predictions().select_related("job").defer("scores", "logits"):
        current = best.get(prediction.algorithm_id)
        if current is None or rank(prediction) > rank(current):
            best[prediction.algorithm_id] = prediction
    return list(best.values())
