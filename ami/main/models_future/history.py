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
from ami.main.models_future.references import Ref, is_record_id, resolve_references
from ami.ml.models import Algorithm, AlgorithmResult
from ami.ml.post_processing.registry import get_postprocessing_task
from ami.ml.results.schemas import field_references, field_titles

if typing.TYPE_CHECKING:
    from ami.jobs.models import Job

# A job's progress and logs can be large JSON documents, and the history shows neither.
JOB_FIELDS_NOT_SHOWN = ("job__progress", "job__logs")


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
    determination_before: Taxon | None = None
    determination_after: Taxon | None = None
    classifications: list[CreatedClassification] = dataclasses.field(default_factory=list)
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
        .defer(*JOB_FIELDS_NOT_SHOWN)
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
    """Fill each entry's job settings, resolving every record id the settings name at once."""
    settings = {id(entry): _job_settings(entry.job) for entry in entries if entry.job is not None}
    wanted = [(ref_type, value) for specs in settings.values() for _, _, value, ref_type in specs if ref_type]
    resolved = resolve_references(wanted) if wanted else {}
    for entry in entries:
        if entry.job is not None:
            entry.job_settings = [
                JobSetting(key, label, value, resolved[(ref_type, value)] if ref_type else None)
                for key, label, value, ref_type in settings[id(entry)]
            ]


def job_config(job: Job | None) -> dict | None:
    """The settings a post-processing job ran with, or None for any other job or malformed params."""
    params = job.params if job is not None else None
    config = params.get("config") if isinstance(params, dict) else None
    return config if isinstance(config, dict) else None


def _job_settings(job: Job) -> list[tuple[str, str, typing.Any, str | None]]:
    """``(key, label, value, reference type)`` per setting, labelled, typed and ordered by the task's config schema.

    The stored config's key order is not kept (Postgres orders a JSON object's keys), so settings follow the
    schema and any key it does not declare comes after. A job whose task is not registered shows its
    settings by key, naming no records.
    """
    config = job_config(job) or {}
    task_key = job.params.get("task") if config else None
    task = get_postprocessing_task(task_key) if isinstance(task_key, str) else None
    titles = field_titles(task.config_schema) if task else {}
    references = field_references(task.config_schema) if task else {}
    keys = [key for key in titles if key in config] + [key for key in config if key not in titles]
    return [
        (key, titles.get(key) or key, config[key], references.get(key) if is_record_id(config[key]) else None)
        for key in keys
    ]


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
    for prediction in occurrence.predictions().select_related("job").defer("scores", "logits", *JOB_FIELDS_NOT_SHOWN):
        current = best.get(prediction.algorithm_id)
        if current is None or rank(prediction) > rank(current):
            best[prediction.algorithm_id] = prediction
    return list(best.values())
