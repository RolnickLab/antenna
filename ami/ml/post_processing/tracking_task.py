import collections
import dataclasses
import logging
import math
import typing
from collections.abc import Iterable, Iterator, Sequence

import numpy as np
import pydantic
from django.db import transaction
from django.db.models import Count
from django.utils import timezone

from ami.main.models import (
    Classification,
    Detection,
    Event,
    Identification,
    Occurrence,
    SourceImage,
    SourceImageCollection,
    update_calculated_fields_for_sessions_and_stations,
)
from ami.main.models_future.track_stats import refresh_track_stats_for_ids
from ami.main.models_future.tracks import clear_grouping_verification
from ami.ml.models import Algorithm
from ami.ml.post_processing.base import BasePostProcessingTask


class TrackingConfig(pydantic.BaseModel):
    """Scope and tunables for a tracking run.

    Scope: exactly one of ``source_image_collection_id`` or ``event_ids`` says
    which sessions to track. A capture set is the bulk path; an explicit event
    list is what the Events admin page sends.
    """

    source_image_collection_id: int | None = None
    event_ids: list[int] = []

    # Maximum matching cost between two detections in consecutive captures. The cost
    # sums (1 - cosine similarity of embeddings), (1 - IoU), (1 - box area ratio) and
    # (centre distance / image diagonal), so a lower threshold links only detections
    # that barely moved and look alike.
    # WARNING: the default is calibrated against synthetic features in tests. Tune it
    # per dataset, and raise it when running without embeddings (see require_features).
    cost_threshold: float = 0.2

    # When True, a pair of detections is only considered if both carry a feature
    # embedding. When False, pairs without embeddings are still matched on geometry
    # alone (the appearance term is dropped, which makes matching more permissive) —
    # this is what lets tracking run on data processed before embeddings were stored.
    require_features: bool = True

    skip_if_human_identifications: bool = True
    require_completely_processed_session: bool = False

    # v1 only operates on fresh data: every detection has its own auto-created
    # occurrence (1:1) and no chain links exist yet. Re-tracking previously-tracked
    # data is a v2 concern (see #1272 for the incremental append/prepend plan).
    require_fresh_event: bool = True

    # Which feature extractor's embeddings to compare. Left unset, the task infers it
    # when exactly one algorithm produced embeddings for the event.
    feature_extraction_algorithm_id: int | None = None

    # Weight of each cost term. At 1.0 each the cost is the plain sum described above.
    appearance_weight: float = pydantic.Field(1.0, ge=0)
    iou_weight: float = pydantic.Field(1.0, ge=0)
    size_weight: float = pydantic.Field(1.0, ge=0)
    distance_weight: float = pydantic.Field(1.0, ge=0)

    # Species gate: two detections whose top labels both score at least species_gate_min_score
    # and name unrelated taxa (neither is an ancestor of the other) are either never linked
    # ("forbid") or have species_gate_penalty added to their cost ("penalty").
    species_gate: typing.Literal["off", "penalty", "forbid"] = "off"
    species_gate_min_score: float = pydantic.Field(0.5, ge=0, le=1)
    species_gate_penalty: float = pydantic.Field(1.0, ge=0)

    # Activity scaling: the more detections a pair of captures holds, the more the distance
    # term weighs, so a crowded sheet tolerates less movement. "log" multiplies it by
    # log(1 + n) / log(1 + activity_reference_count) when that exceeds 1; "steps" uses the
    # multiplier of the highest [count, multiplier] step in activity_steps that n reaches.
    activity_scaling: typing.Literal["off", "log", "steps"] = "off"
    activity_reference_count: int = pydantic.Field(5, ge=1)
    activity_steps: list[tuple[int, float]] = []

    # Stationary-first pass: pairs whose centre moved at most stationary_max_shift (share of
    # the image diagonal), overlap by at least stationary_min_iou and cost less than
    # stationary_cost_threshold are linked before any other pair, so a moving insect cannot
    # take the place of one sitting still. With stationary_allow_missing_features, such a
    # pair is linked on geometry alone even when require_features would skip it.
    stationary_first: bool = False
    stationary_max_shift: float = pydantic.Field(0.01, ge=0)
    stationary_min_iou: float = pydantic.Field(0.7, ge=0, le=1)
    stationary_cost_threshold: float = pydantic.Field(0.2, ge=0)
    stationary_allow_missing_features: bool = False

    @pydantic.validator("activity_steps")
    def _steps_ascend(cls, steps: list[tuple[int, float]]) -> list[tuple[int, float]]:
        counts = [count for count, _ in steps]
        if counts != sorted(set(counts)):
            raise ValueError("activity_steps counts must be strictly increasing")
        if any(count < 0 or multiplier <= 0 for count, multiplier in steps):
            raise ValueError("activity_steps need counts >= 0 and multipliers > 0")
        return steps

    @pydantic.root_validator(skip_on_failure=True)
    def _exactly_one_scope(cls, values: dict) -> dict:
        scopes = [values.get("source_image_collection_id"), values.get("event_ids") or None]
        if sum(s is not None for s in scopes) != 1:
            raise ValueError("Provide exactly one of source_image_collection_id or event_ids")
        if values.get("activity_scaling") == "steps" and not values.get("activity_steps"):
            raise ValueError("activity_scaling 'steps' needs activity_steps")
        return values

    def link_options(self) -> "LinkOptions":
        """The settings that decide which pairs link, apart from the threshold and feature requirement."""
        values = {field.name: getattr(self, field.name) for field in dataclasses.fields(LinkOptions)}
        values["activity_steps"] = tuple(tuple(step) for step in self.activity_steps)
        return LinkOptions(**values)

    class Config:
        extra = "forbid"


def cosine_similarity(v1: Iterable[float], v2: Iterable[float]) -> float:
    a = np.array(v1)
    b = np.array(v2)
    sim = np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))
    return float(np.clip(sim, 0.0, 1.0))


def iou(bb1, bb2) -> float:
    xA = max(bb1[0], bb2[0])
    yA = max(bb1[1], bb2[1])
    xB = min(bb1[2], bb2[2])
    yB = min(bb1[3], bb2[3])
    inter = max(0, xB - xA + 1) * max(0, yB - yA + 1)
    area1 = (bb1[2] - bb1[0] + 1) * (bb1[3] - bb1[1] + 1)
    area2 = (bb2[2] - bb2[0] + 1) * (bb2[3] - bb2[1] + 1)
    union = area1 + area2 - inter
    return inter / union if union > 0 else 0.0


def box_ratio(bb1, bb2) -> float:
    area1 = (bb1[2] - bb1[0] + 1) * (bb1[3] - bb1[1] + 1)
    area2 = (bb2[2] - bb2[0] + 1) * (bb2[3] - bb2[1] + 1)
    return min(area1, area2) / max(area1, area2)


def distance_ratio(bb1, bb2, img_diag: float) -> float:
    cx1 = (bb1[0] + bb1[2]) / 2
    cy1 = (bb1[1] + bb1[3]) / 2
    cx2 = (bb2[0] + bb2[2]) / 2
    cy2 = (bb2[1] + bb2[3]) / 2
    dist = math.sqrt((cx2 - cx1) ** 2 + (cy2 - cy1) ** 2)
    return dist / img_diag if img_diag > 0 else 1.0


def image_diagonal(width: int, height: int) -> int:
    return int(math.ceil(math.sqrt(width**2 + height**2)))


def total_cost(f1, f2, bb1, bb2, diag) -> float:
    """Matching cost between two detections; lower means more likely the same insect.

    The appearance term is dropped when either detection has no embedding, leaving
    a geometry-only cost. Dropping a non-negative term lowers the total, so a
    geometry-only run matches more readily at the same threshold.
    """
    geometry = (1 - iou(bb1, bb2)) + (1 - box_ratio(bb1, bb2)) + distance_ratio(bb1, bb2, diag)
    if f1 is None or f2 is None:
        return geometry
    return (1 - cosine_similarity(f1, f2)) + geometry


@dataclasses.dataclass(frozen=True)
class LinkOptions:
    """The optional link rules of ``TrackingConfig``; the defaults leave linking as the plain cost sum."""

    appearance_weight: float = 1.0
    iou_weight: float = 1.0
    size_weight: float = 1.0
    distance_weight: float = 1.0
    species_gate: str = "off"
    species_gate_min_score: float = 0.5
    species_gate_penalty: float = 1.0
    activity_scaling: str = "off"
    activity_reference_count: int = 5
    activity_steps: tuple[tuple[int, float], ...] = ()
    stationary_first: bool = False
    stationary_max_shift: float = 0.01
    stationary_min_iou: float = 0.7
    stationary_cost_threshold: float = 0.2
    stationary_allow_missing_features: bool = False


DEFAULT_LINK_OPTIONS = LinkOptions()


@dataclasses.dataclass(frozen=True)
class PairTerms:
    """The raw cost terms of one pair of detections. ``appearance`` is 1 - cosine similarity,
    or None when either detection has no embedding."""

    appearance: float | None
    iou: float
    size_ratio: float
    distance: float


@dataclasses.dataclass(frozen=True)
class TopLabel:
    """A detection's highest-scoring terminal label and the ids of that taxon's ancestors."""

    taxon_id: int
    score: float
    ancestor_ids: frozenset[int] = frozenset()


def pair_terms(f1, f2, bb1, bb2, diag: float) -> PairTerms:
    appearance = None if f1 is None or f2 is None else 1 - cosine_similarity(f1, f2)
    return PairTerms(appearance, iou(bb1, bb2), box_ratio(bb1, bb2), distance_ratio(bb1, bb2, diag))


def weighted_cost(terms: PairTerms, options: LinkOptions = DEFAULT_LINK_OPTIONS, distance_multiplier=1.0) -> float:
    """The matching cost from its terms. At the default weights it equals ``total_cost``
    exactly: the terms are summed in the same order and multiplying by 1.0 changes nothing."""
    geometry = (
        options.iou_weight * (1 - terms.iou)
        + options.size_weight * (1 - terms.size_ratio)
        + options.distance_weight * distance_multiplier * terms.distance
    )
    if terms.appearance is None:
        return geometry
    return options.appearance_weight * terms.appearance + geometry


def activity_multiplier(detection_count: int, options: LinkOptions) -> float:
    """How much more the distance term weighs for a pair of captures holding this many detections."""
    if options.activity_scaling == "log":
        return max(1.0, math.log1p(detection_count) / math.log1p(options.activity_reference_count))
    if options.activity_scaling == "steps":
        multiplier = 1.0
        for count, step_multiplier in options.activity_steps:
            if detection_count >= count:
                multiplier = step_multiplier
        return multiplier
    return 1.0


def labels_conflict(a: TopLabel | None, b: TopLabel | None, min_score: float) -> bool:
    """Do two confident labels name unrelated taxa? A genus and one of its species do not conflict."""
    if a is None or b is None or a.score < min_score or b.score < min_score:
        return False
    if a.taxon_id == b.taxon_id:
        return False
    return a.taxon_id not in b.ancestor_ids and b.taxon_id not in a.ancestor_ids


def is_stationary(terms: PairTerms, options: LinkOptions) -> bool:
    return terms.distance <= options.stationary_max_shift and terms.iou >= options.stationary_min_iou


def choose_links(
    pairs: Iterable[tuple[typing.Any, typing.Any, PairTerms]],
    cost_threshold: float,
    require_features: bool = True,
    options: LinkOptions = DEFAULT_LINK_OPTIONS,
    detection_count: int = 0,
    labels: typing.Mapping[typing.Any, TopLabel] | None = None,
    key=lambda detection: detection,
) -> list[tuple[typing.Any, typing.Any, float]]:
    """Pick the links between two adjacent captures from the scored pairs, one link per detection a side.

    With ``stationary_first``, pairs that sit still are taken first (lowest cost first), then
    every other candidate below ``cost_threshold`` is. ``key`` gives the id that breaks ties
    between equal costs, so the order is the same across runs.
    """
    labels = labels or {}
    multiplier = activity_multiplier(detection_count, options)
    stationary: list[tuple[typing.Any, typing.Any, float]] = []
    candidates: list[tuple[typing.Any, typing.Any, float]] = []
    for det, nxt, terms in pairs:
        missing = terms.appearance is None
        cost = weighted_cost(terms, options, multiplier)
        if options.species_gate != "off" and labels_conflict(
            labels.get(key(det)), labels.get(key(nxt)), options.species_gate_min_score
        ):
            if options.species_gate == "forbid":
                continue
            cost += options.species_gate_penalty
        if (
            options.stationary_first
            and cost < options.stationary_cost_threshold
            and (not missing or not require_features or options.stationary_allow_missing_features)
            and is_stationary(terms, options)
        ):
            stationary.append((det, nxt, cost))
        elif (not missing or not require_features) and cost < cost_threshold:
            candidates.append((det, nxt, cost))

    claimed_current: set = set()
    claimed_next: set = set()
    links: list[tuple[typing.Any, typing.Any, float]] = []
    for group in (stationary, candidates):
        # Secondary keys keep tied costs deterministic across runs.
        group.sort(key=lambda x: (x[2], key(x[0]), key(x[1])))
        for det, nxt, cost in group:
            if key(det) in claimed_current or key(nxt) in claimed_next:
                continue
            claimed_current.add(key(det))
            claimed_next.add(key(nxt))
            links.append((det, nxt, cost))
    return links


def top_labels(detection_ids: Iterable[int]) -> dict[int, TopLabel]:
    """Each detection's highest-scoring terminal label, in two queries for the whole batch.

    Rows copied from another classification (``applied_to`` set, as tracking and class
    masking leave) are left out, so the label is what a classifier said about this crop.
    """
    from ami.main.models import Taxon

    best: dict[int, tuple[int, float]] = {}
    rows = (
        Classification.objects.filter(
            detection_id__in=list(detection_ids),
            terminal=True,
            applied_to__isnull=True,
            taxon_id__isnull=False,
            score__isnull=False,
        )
        .order_by("detection_id", "-score", "-pk")
        .values_list("detection_id", "taxon_id", "score")
    )
    for detection_id, taxon_id, score in rows:
        best.setdefault(detection_id, (taxon_id, score))
    ancestors: dict[int, frozenset[int]] = {}
    for taxon_id, parents in Taxon.objects.filter(pk__in={t for t, _ in best.values()}).values_list(
        "pk", "parents_json"
    ):
        ids = set()
        for parent in parents or []:
            parent_id = parent.get("id") if isinstance(parent, dict) else getattr(parent, "id", None)
            if parent_id is not None:
                ids.add(int(parent_id))
        ancestors[taxon_id] = frozenset(ids)
    return {
        detection_id: TopLabel(taxon_id, score, ancestors.get(taxon_id, frozenset()))
        for detection_id, (taxon_id, score) in best.items()
    }


def get_unique_feature_algorithm_for_event(event: Event) -> tuple[Algorithm | None, list[Algorithm]]:
    """
    Return ``(unique_algorithm, all_candidates)``.

    If exactly one feature-extraction algorithm produced ``features_2048`` for this
    event, returns that algorithm and a single-element list. Otherwise returns
    ``(None, candidates)`` so the caller can either skip with a warning or require
    the operator to pass an explicit ``feature_extraction_algorithm_id``.
    """
    algo_ids = (
        Classification.objects.filter(
            detection__source_image__event=event,
            features_2048__isnull=False,
            algorithm_id__isnull=False,
        )
        .values_list("algorithm_id", flat=True)
        .distinct()
    )
    candidates = list(Algorithm.objects.filter(pk__in=list(algo_ids)))
    if len(candidates) == 1:
        return candidates[0], candidates
    return None, candidates


def resolve_feature_algorithm(
    event: Event, config: TrackingConfig, candidates: list[Algorithm] | None = None
) -> tuple[Algorithm | None, bool, str]:
    """The feature extractor a tracking run compares embeddings from, and whether it tracks the event.

    Returns ``(algorithm, should_track, note)``. ``algorithm`` is None when the run falls
    back to geometry alone, and ``note`` says why a run falls back or skips; it is empty
    when one extractor was configured or found. ``candidates`` are the extractors that
    produced embeddings: every one in the event unless the caller passes a narrower set.
    """
    if config.feature_extraction_algorithm_id is not None:
        algorithm = Algorithm.objects.filter(pk=config.feature_extraction_algorithm_id).first()
        if algorithm is None:
            return (
                None,
                False,
                f"Configured feature_extraction_algorithm_id="
                f"{config.feature_extraction_algorithm_id} not found; skipping event {event.pk}.",
            )
        return algorithm, True, ""

    if candidates is None:
        _, candidates = get_unique_feature_algorithm_for_event(event)
    if len(candidates) == 1:
        return candidates[0], True, ""

    if candidates:
        candidate_names = [f"#{a.pk} {a.name}" for a in candidates]
        message = (
            f"Event {event.pk}: detections classified by {len(candidates)} different "
            f"feature-extraction algorithms ({candidate_names}). Pass "
            "feature_extraction_algorithm_id in the job config to disambiguate."
        )
    else:
        message = f"Event {event.pk}: no detections carry feature embeddings."

    if config.require_features:
        return None, False, f"{message} Skipping."
    return None, True, f"{message} Matching on bounding-box geometry alone."


def event_is_fresh(event: Event) -> tuple[bool, str]:
    """Has this event's detections already been grouped into chains?

    The guard exists to keep v1 away from events that were already consolidated:
    merging those again can delete an occurrence that carries identifications.
    An occurrence spanning more than one detection is the signal for that.

    A detection with no occurrence at all is not that signal — the chain walk
    creates an occurrence for a chain that has none — so orphans do not block a
    run. Real sessions routinely carry a handful of them.

    Occurrences are found through their detections' captures, not ``Occurrence.event``,
    so a track that reaches into this session from another one also counts.
    """
    multi_detection_occurrences = (
        Occurrence.objects.filter(pk__in=Detection.objects.filter(source_image__event=event).values("occurrence_id"))
        .annotate(_n=Count("detections"))
        .filter(_n__gt=1)
        .count()
    )
    if multi_detection_occurrences:
        return False, f"{multi_detection_occurrences} occurrence(s) already span >1 detection"

    return True, ""


def event_fully_processed(event: Event, logger: logging.Logger, algorithm: Algorithm) -> bool:
    total = event.captures.count()
    processed = (
        event.captures.filter(
            detections__classifications__features_2048__isnull=False,
            detections__classifications__algorithm=algorithm,
        )
        .distinct()
        .count()
    )
    if processed < total:
        logger.info(f"Event {event.pk} not fully processed: {processed}/{total} captures")
        return False
    return True


def record_tracking_determination(occurrence: Occurrence, algorithm: Algorithm) -> Classification | None:
    """Leave a terminal classification, attributed to the tracking algorithm, when a merge
    changed the occurrence's determination, so the history shows what tracking decided.

    Mirrors class masking: the row carries the winning prediction and points back at it via
    ``applied_to``. It copies the merge's best score; a per-track vote is a separate change.
    """
    winner = occurrence.best_prediction
    if winner is None or winner.detection_id is None or winner.taxon_id is None:
        return None
    if winner.algorithm_id == algorithm.pk:
        return None
    return Classification.objects.create(
        detection=winner.detection,
        taxon=winner.taxon,
        score=winner.score,
        terminal=True,
        algorithm=algorithm,
        timestamp=timezone.now(),
        applied_to=winner,
    )


def assign_occurrences_from_detection_chains(
    source_images: list[SourceImage], logger: logging.Logger, record_as: Algorithm | None = None
) -> dict[str, int]:
    """
    Walk chains via ``Detection.next_detection`` and consolidate each chain into
    a single occurrence using a merge-into-first strategy:

    - A chain never crosses a session boundary: the walk stops at a detection in another
      session, and a detection linked from another session starts a chain of its own.
    - Pick the first existing occurrence in the chain as the keeper.
    - Reassign every other detection in the chain to the keeper.
    - Move any identifications off the siblings onto the keeper, then delete them.
    - If no detection in the chain has an occurrence yet, create one.
    - With ``record_as`` set, a merge that changes the keeper's determination leaves a
      classification attributed to that algorithm (see ``record_tracking_determination``).
    - Clear grouping verification from every occurrence whose detection set changed;
      an occurrence the chains leave as it was keeps its mark.
    - Store the track statistics of every occurrence the chains settle on, so the list
      can sort by them (see ``track_stats.refresh_track_stats_for_ids``).

    Designed for fresh-event input (1:1 detection/occurrence). v2 incremental tracking
    can reuse this primitive for prepend/append: keeper survives, new detections fold in.

    Returns counters for the caller's stage metrics.
    """
    visited: set[int] = set()
    settled: set[int] = set()
    created = 0
    merged = 0
    identifications_moved = 0
    determinations_recorded = 0
    existing = Occurrence.objects.filter(detections__source_image__in=source_images).distinct().count()

    # A chain ends at a session boundary. A regroup that splits a track keeps the link
    # between its pieces, and following it would merge them back into one occurrence.
    session_of_capture = {image.pk: image.event_id for image in source_images}

    def session_of(detection: Detection) -> int | None:
        if detection.source_image_id not in session_of_capture:
            session_of_capture[detection.source_image_id] = (
                SourceImage.objects.filter(pk=detection.source_image_id).values_list("event_id", flat=True).first()
            )
        return session_of_capture[detection.source_image_id]

    for image in source_images:
        # Null-marker sentinels (bbox IS NULL) mark a capture as processed; they are not insects.
        for det in image.detections.valid():
            if det.pk in visited:
                continue
            try:
                prior: Detection | None = det.previous_detection
            except Detection.DoesNotExist:
                prior = None
            if prior is not None and session_of(prior) == image.event_id:
                continue

            chain: list[Detection] = []
            current: Detection | None = det
            while current and current.pk not in visited:
                chain.append(current)
                visited.add(current.pk)
                current = current.next_detection
                if current is not None and session_of(current) != image.event_id:
                    break

            old_occ_ids = {d.occurrence_id for d in chain if d.occurrence_id}
            all_assigned = all(d.occurrence_id is not None for d in chain)

            # Coherent: every detection assigned and all share one occurrence. Nothing to
            # change, but it still gets its stats stored below, so a re-run fills in
            # occurrences that were tracked before the stored fields existed.
            if len(old_occ_ids) == 1 and all_assigned:
                settled.update(old_occ_ids)
                continue

            # Pick keeper: first existing occurrence in chain order.
            keeper: Occurrence | None = None
            for d in chain:
                if d.occurrence_id:
                    keeper = d.occurrence
                    break

            previous_determination_id = keeper.determination_id if keeper is not None else None
            if keeper is None:
                keeper = Occurrence.objects.create(
                    event=chain[0].source_image.event,
                    deployment=chain[0].source_image.deployment,
                    project=chain[0].source_image.project,
                )
                created += 1

            # Reassign chain detections to keeper.
            keeper_gained_frames = False
            for d in chain:
                if d.occurrence_id != keeper.pk:
                    d.occurrence = keeper
                    d.save()
                    keeper_gained_frames = True

            # Move identifications onto the keeper before deleting the occurrences that
            # held them. Identification.occurrence CASCADEs, so deleting first destroys a
            # person's work. A fresh event is not protection: freshness means no chains
            # exist yet, which says nothing about whether anyone has reviewed the
            # detections. An untracked-but-reviewed session is ordinary.
            doomed = old_occ_ids - {keeper.pk}
            if doomed:
                identifications_moved += Identification.objects.filter(occurrence_id__in=doomed).update(
                    occurrence=keeper
                )
            undeleted: list[int] = []
            for occ_id in doomed:
                try:
                    Occurrence.objects.filter(id=occ_id).delete()
                    merged += 1
                except Exception as e:
                    logger.error(f"Failed to delete occurrence {occ_id}: {e}")
                    undeleted.append(occ_id)

            # A confirmation covers the frames a person looked at, so an occurrence whose
            # frames tracking changes loses it, the same as after a manual edit.
            if keeper_gained_frames:
                clear_grouping_verification(keeper)
            if undeleted:
                clear_grouping_verification(*Occurrence.objects.filter(pk__in=undeleted))

            keeper.save()
            if record_as is not None and keeper.determination_id != previous_determination_id:
                if record_tracking_determination(keeper, record_as) is not None:
                    determinations_recorded += 1
            settled.add(keeper.pk)

    # Stored once every determination is settled, since id_agreement is measured against
    # it, and in batches for the whole event rather than three queries per chain.
    stats_stored = refresh_track_stats_for_ids(settled)

    new_count = Occurrence.objects.filter(detections__source_image__in=source_images).distinct().count()
    removed = existing - new_count
    if removed > 0:
        logger.info(f"Merged {merged} sibling occurrences into chain keepers (net -{removed}).")
    if identifications_moved:
        logger.info(f"Moved {identifications_moved} identification(s) onto chain keepers before merging.")
    if determinations_recorded:
        logger.info(f"Recorded {determinations_recorded} determination change(s) as tracking classifications.")
    logger.info(
        f"Materialized {created} new occurrences across {len(source_images)} images. "
        f"Occurrences before: {existing}, after: {new_count}. Detections processed: {len(visited)}. "
        f"Track statistics stored for {stats_stored} occurrences."
    )
    return {
        "occurrences_before": existing,
        "occurrences_after": new_count,
        "occurrences_created": created,
        "occurrences_merged": merged,
        "identifications_moved": identifications_moved,
        "determinations_recorded": determinations_recorded,
    }


def nothing_tracked_summary(skip_reasons: collections.Counter[str]) -> str:
    """The line a job shows when every session in scope was skipped, with the count per reason."""
    total = sum(skip_reasons.values())
    reasons = "; ".join(f"{count} because {reason}" for reason, count in skip_reasons.most_common())
    return f"Nothing was tracked: {total} session(s) skipped ({reasons})."


def latest_feature_vectors(detection_ids: Iterable[int], algorithm_id: int) -> dict[int, typing.Any]:
    """The most recent embedding from one algorithm for each detection given, by detection id.

    Detections without one are left out. One query for the whole batch.
    """
    vectors: dict[int, typing.Any] = {}
    rows = (
        Classification.objects.filter(
            detection_id__in=list(detection_ids), algorithm_id=algorithm_id, features_2048__isnull=False
        )
        .order_by("-timestamp", "-pk")
        .values_list("detection_id", "features_2048")
    )
    for detection_id, vector in rows:
        vectors.setdefault(detection_id, vector)
    return vectors


def select_links(
    current_detections: Sequence[Detection],
    next_detections: Sequence[Detection],
    vectors: dict[int, typing.Any],
    diag: float,
    cost_threshold: float,
    require_features: bool = True,
    options: LinkOptions = DEFAULT_LINK_OPTIONS,
    labels: typing.Mapping[int, TopLabel] | None = None,
) -> list[tuple[Detection, Detection, float]]:
    """The links tracking makes between two adjacent captures, lowest cost first, saving nothing.

    A pair is a candidate when its matching cost is below ``cost_threshold``; with
    ``require_features``, a detection with no embedding in ``vectors`` never is (unless the
    stationary pass allows it). Each detection is linked at most once on either side; see
    ``choose_links`` for the order. Tracking runs and the session view's link preview both
    call this, so they cannot differ.
    """
    skip_missing = require_features and not (options.stationary_first and options.stationary_allow_missing_features)
    pairs = []
    for det in current_detections:
        det_vec = vectors.get(det.pk)
        if det_vec is None and skip_missing:
            continue
        for nxt in next_detections:
            nxt_vec = vectors.get(nxt.pk)
            if nxt_vec is None and skip_missing:
                continue
            pairs.append((det, nxt, pair_terms(det_vec, nxt_vec, det.bbox, nxt.bbox, diag)))
    return choose_links(
        pairs,
        cost_threshold,
        require_features,
        options,
        detection_count=max(len(current_detections), len(next_detections)),
        labels=labels,
        key=lambda detection: detection.pk,
    )


def select_transition_links(
    current_detections: Sequence[Detection],
    next_detections: Sequence[Detection],
    image_width: int,
    image_height: int,
    cost_threshold: float,
    algorithm: Algorithm | None,
    require_features: bool = True,
    options: LinkOptions = DEFAULT_LINK_OPTIONS,
    labels: typing.Mapping[int, TopLabel] | None = None,
    vectors: dict[int, typing.Any] | None = None,
) -> list[tuple[Detection, Detection, float]]:
    """The links tracking makes between two adjacent captures, reading embeddings but saving nothing.

    ``vectors`` replaces the embeddings read from ``algorithm``, for scoring embeddings that
    are not stored as classifications.
    """
    if vectors is None:
        vectors = {}
        if algorithm is not None:
            vectors = latest_feature_vectors([det.pk for det in [*current_detections, *next_detections]], algorithm.pk)
    return select_links(
        current_detections,
        next_detections,
        vectors,
        image_diagonal(image_width, image_height),
        cost_threshold,
        require_features,
        options,
        labels,
    )


def save_links(links: Iterable[tuple[Detection, Detection, float]], logger: logging.Logger) -> None:
    """Store each link as ``next_detection``, first detaching any other detection pointing at the target."""
    for det, nxt, cost in links:
        # Detach any existing inbound link to `nxt` before reassigning.
        try:
            prior: Detection | None = nxt.previous_detection
        except Detection.DoesNotExist:
            prior = None
        if prior is not None:
            prior.next_detection = None
            prior.save()

        det.next_detection = nxt
        det.save()
        logger.debug(f"Linked detection {det.id} -> {nxt.id} (cost {cost:.4f})")


def pair_detections(
    current_detections: list[Detection],
    next_detections: list[Detection],
    image_width: int,
    image_height: int,
    cost_threshold: float,
    algorithm: Algorithm | None,
    logger: logging.Logger,
    require_features: bool = True,
) -> int:
    """
    Greedy lowest-cost matching between two adjacent images. Sets `next_detection`
    on each detection in `current_detections` for the best partner in `next_detections`,
    if that partner's cost is below `cost_threshold` and not already claimed. The links
    are chosen by `select_links`; this saves them.

    With ``require_features=False``, detections that carry no embedding are still
    matched, on geometry alone. Returns the number of links created.
    """
    links = select_transition_links(
        current_detections,
        next_detections,
        image_width,
        image_height,
        cost_threshold,
        algorithm,
        require_features,
    )
    save_links(links, logger)
    return len(links)


def iter_transition_links(
    source_images: Sequence[SourceImage],
    algorithm: Algorithm | None,
    config: TrackingConfig,
    logger: logging.Logger,
    vectors: dict[int, typing.Any] | None = None,
) -> Iterator[list[tuple[Detection, Detection, float]] | None]:
    """Yield the proposed links for each pair of consecutive captures, in order, saving nothing.

    Yields None for a transition skipped because the earlier capture has no dimensions. The
    generator is lazy, so a caller that saves each transition's links before asking for the
    next one sees detections as they stand after its own writes.
    """
    options = config.link_options()
    labels = None
    if options.species_gate != "off":
        # One read for the session, so the gate costs no query per pair of captures.
        labels = top_labels(
            Detection.objects.valid().filter(source_image__in=source_images).values_list("pk", flat=True)
        )
    transitions = len(source_images) - 1
    for i in range(transitions):
        cur = source_images[i]
        nxt = source_images[i + 1]
        if not cur.width or not cur.height:
            logger.warning(
                f"Image {cur.pk} has no dimensions; skipping transition {i + 1}/{transitions} "
                f"for event {cur.event_id}."
            )
            yield None
            continue
        yield select_transition_links(
            list(cur.detections.valid()),
            list(nxt.detections.valid()),
            image_width=cur.width,
            image_height=cur.height,
            cost_threshold=config.cost_threshold,
            algorithm=algorithm,
            require_features=config.require_features,
            options=options,
            labels=labels,
            vectors=vectors,
        )


def propose_event_links(
    event: Event,
    algorithm: Algorithm | None,
    config: TrackingConfig,
    logger: logging.Logger,
    vectors: dict[int, typing.Any] | None = None,
) -> list[tuple[int, int, float]]:
    """The ``(detection_id, next_detection_id, cost)`` links a tracking run would make in one
    event, treating every detection as unlinked and writing nothing.

    Tracking runs choose links the same way (``iter_transition_links``), so an evaluation
    built on this scores what the task would do on the same detections. ``vectors`` replaces
    the stored embeddings, as in ``select_transition_links``.
    """
    source_images = list(event.captures.order_by("timestamp"))
    links: list[tuple[int, int, float]] = []
    for transition in iter_transition_links(source_images, algorithm, config, logger, vectors):
        links.extend((det.pk, nxt.pk, cost) for det, nxt, cost in transition or [])
    return links


@dataclasses.dataclass
class TransitionPairs:
    """Every pair of detections across two adjacent captures, with its cost terms, for re-scoring
    under many settings without reading the database again."""

    pairs: list[tuple[int, int, PairTerms]]
    detection_count: int


def event_transition_pairs(
    event: Event, algorithm: Algorithm | None, vectors: dict[int, typing.Any] | None = None
) -> tuple[list[TransitionPairs], list[int]]:
    """The scored pairs of every transition in one event, and every valid detection id in it.

    ``links_from_transition_pairs`` over the result gives the same links as
    ``propose_event_links`` for any setting: the same terms feed ``choose_links``.
    """
    source_images = list(event.captures.order_by("timestamp"))
    detections = list(
        Detection.objects.valid().filter(source_image__in=source_images).only("pk", "bbox", "source_image_id")
    )
    by_capture: dict[int, list[Detection]] = collections.defaultdict(list)
    for detection in sorted(detections, key=lambda d: d.pk):
        by_capture[detection.source_image_id].append(detection)
    if vectors is None:
        vectors = latest_feature_vectors([d.pk for d in detections], algorithm.pk) if algorithm is not None else {}
    # Convert once per detection rather than once per pair; the values are unchanged.
    arrays = {pk: np.asarray(vector) for pk, vector in vectors.items()}

    transitions: list[TransitionPairs] = []
    for cur, nxt in zip(source_images, source_images[1:]):
        if not cur.width or not cur.height:
            continue
        diag = image_diagonal(cur.width, cur.height)
        current, following = by_capture.get(cur.pk, []), by_capture.get(nxt.pk, [])
        pairs = [
            (a.pk, b.pk, pair_terms(arrays.get(a.pk), arrays.get(b.pk), a.bbox, b.bbox, diag))
            for a in current
            for b in following
        ]
        transitions.append(TransitionPairs(pairs, max(len(current), len(following))))
    return transitions, [d.pk for d in detections]


def links_from_transition_pairs(
    transitions: Iterable[TransitionPairs],
    config: TrackingConfig,
    labels: typing.Mapping[int, TopLabel] | None = None,
) -> list[tuple[int, int, float]]:
    """The links a run with ``config`` makes over pre-scored transitions (see ``event_transition_pairs``)."""
    options = config.link_options()
    links: list[tuple[int, int, float]] = []
    for transition in transitions:
        links.extend(
            choose_links(
                transition.pairs,
                config.cost_threshold,
                config.require_features,
                options,
                detection_count=transition.detection_count,
                labels=labels if options.species_gate != "off" else None,
            )
        )
    return links


def assign_occurrences_by_tracking_images(
    event: Event,
    logger: logging.Logger,
    algorithm: Algorithm | None,
    config: TrackingConfig,
    progress_cb: typing.Callable[[float], None] | None = None,
    record_as: Algorithm | None = None,
) -> dict[str, int]:
    source_images = list(event.captures.order_by("timestamp"))
    if len(source_images) < 2:
        logger.warning(f"Event {event.pk}: not enough images to track ({len(source_images)})")
        return {}

    transitions = len(source_images) - 1
    skipped_transitions = 0
    links = 0
    # Per-event atomic boundary: a crash mid-event rolls back chain links + occurrence
    # consolidation for THIS event only, leaving other events in the job intact.
    with transaction.atomic():
        transition_links = iter_transition_links(source_images, algorithm, config, logger)
        for i, proposed in enumerate(transition_links):
            if proposed is None:
                skipped_transitions += 1
            else:
                save_links(proposed, logger)
                links += len(proposed)
            if progress_cb:
                progress_cb((i + 1) / transitions)

        if skipped_transitions:
            logger.info(
                f"Event {event.pk}: skipped {skipped_transitions}/{transitions} transitions "
                "due to missing image dimensions."
            )

        counters = assign_occurrences_from_detection_chains(source_images, logger, record_as=record_as)

    counters["links_created"] = links
    return counters


class TrackingTask(BasePostProcessingTask):
    """
    Reconstruct occurrences by tracking detections across consecutive captures using
    feature embeddings and bbox geometry. Updates each Detection's ``next_detection``
    link and folds each chain of detections into a single Occurrence.
    """

    key = "tracking"
    name = "Occurrence Tracking"
    config_schema = TrackingConfig

    config: TrackingConfig

    def _resolve_events(self) -> list[Event]:
        """
        Return the events to track, from either scope in the config.

        A capture set is flattened to the events its images belong to. When a job is
        attached, every resolved event must belong to ``job.project``; cross-project
        IDs are dropped with a warning. That guards against a trigger smuggling event
        IDs from a project the operator cannot see.
        """
        if self.config.source_image_collection_id is not None:
            collection = SourceImageCollection.objects.filter(pk=self.config.source_image_collection_id).first()
            if collection is None:
                raise ValueError(f"Capture set {self.config.source_image_collection_id} not found.")
            qs = Event.objects.filter(captures__collections=collection).distinct()
            requested: list[int] | None = None
        else:
            requested = list(self.config.event_ids)
            qs = Event.objects.filter(pk__in=requested)

        if self.job and self.job.project_id:
            cross_project = list(qs.exclude(project_id=self.job.project_id).values_list("pk", flat=True))
            if cross_project:
                self.logger.warning(
                    f"Dropping {len(cross_project)} event(s) outside job project "
                    f"{self.job.project_id}: {cross_project}"
                )
                qs = qs.filter(project_id=self.job.project_id)

        events = list(qs.order_by("pk").distinct())
        if requested is not None:
            missing = set(requested) - {e.pk for e in events}
            if missing:
                self.logger.warning(f"Tracking requested {sorted(missing)} but those events were not found.")
        return events

    def _resolve_algorithm(self, event: Event) -> tuple[Algorithm | None, bool]:
        """Return ``(algorithm, should_track)`` for one event, logging why a run falls back or skips.

        ``algorithm`` is the feature extractor whose embeddings to compare, or None
        when the run falls back to geometry alone.
        """
        algorithm, should_track, note = resolve_feature_algorithm(event, self.config)
        if note and should_track:
            self.logger.info(note)
        elif note:
            self.logger.warning(note)
        return algorithm, should_track

    def run(self) -> None:
        self.logger.info(f"Tracking starting with config: {self.config.dict()}")

        events = self._resolve_events()
        total = len(events)
        self.logger.info(f"Tracking: {total} event(s) in scope")

        totals = {"events_tracked": 0, "events_skipped": 0, "links_created": 0, "occurrences_merged": 0}
        tracked_event_ids: list[int] = []
        # Why each session was skipped, so a run that tracks nothing can say so.
        skip_reasons: collections.Counter[str] = collections.Counter()

        for idx, event in enumerate(events, start=1):
            self.logger.info(f"Tracking event {idx}/{total} (id={event.pk})")

            if self.config.require_fresh_event:
                fresh, reason = event_is_fresh(event)
                if not fresh:
                    self.logger.info(
                        f"Skipping event {event.pk}: not fresh ({reason}). "
                        "v1 only handles 1:1 detection/occurrence input. "
                        "Re-tracking previously-tracked data lands in v2 (incremental)."
                    )
                    totals["events_skipped"] += 1
                    skip_reasons["it was already tracked or edited"] += 1
                    continue

            algorithm, should_track = self._resolve_algorithm(event)
            if not should_track:
                totals["events_skipped"] += 1
                skip_reasons["it has no embeddings from a single feature extractor to compare"] += 1
                continue

            if (
                self.config.skip_if_human_identifications
                and Occurrence.objects.filter(event=event, identifications__isnull=False).exists()
            ):
                self.logger.info(f"Skipping event {event.pk}: has human identifications.")
                totals["events_skipped"] += 1
                skip_reasons["it has human identifications"] += 1
                continue

            if (
                self.config.require_completely_processed_session
                and algorithm is not None
                and not event_fully_processed(event, logger=self.logger, algorithm=algorithm)
            ):
                self.logger.info(f"Skipping event {event.pk}: not fully processed.")
                totals["events_skipped"] += 1
                skip_reasons["it is not fully processed"] += 1
                continue

            def _stage_progress(p: float, _idx=idx, _total=total) -> None:
                # Aggregate per-event progress into overall task progress.
                overall = ((_idx - 1) + p) / _total
                self.update_progress(overall)

            counters = assign_occurrences_by_tracking_images(
                event=event,
                logger=self.logger,
                algorithm=algorithm,
                config=self.config,
                record_as=self.algorithm,
                progress_cb=_stage_progress,
            )
            totals["events_tracked"] += 1
            tracked_event_ids.append(event.pk)
            totals["links_created"] += counters.get("links_created", 0)
            totals["occurrences_merged"] += counters.get("occurrences_merged", 0)

        # Merging occurrences changes the session and station counts, which no save refreshes.
        # This already runs in a background job, so the station refresh stays inline.
        update_calculated_fields_for_sessions_and_stations(tracked_event_ids, stations_async=False)

        metrics: dict[str, typing.Any] = {
            "Events tracked": totals["events_tracked"],
            "Events skipped": totals["events_skipped"],
            "Detection links created": totals["links_created"],
            "Occurrences merged": totals["occurrences_merged"],
        }
        # The job still succeeds, so without this line a run that skipped every session
        # looks the same in the job details as one that did the work. It is written on every
        # run because a retry keeps text params, and a stale line would contradict the counts.
        if totals["events_tracked"]:
            metrics["Result"] = f"Tracked {totals['events_tracked']} session(s)."
        elif skip_reasons:
            metrics["Result"] = nothing_tracked_summary(skip_reasons)
            self.logger.warning(metrics["Result"])
        else:
            metrics["Result"] = "Nothing was tracked: no sessions in scope."
        self.report_stage_metrics(metrics)
        self.update_progress(1.0)
        self.logger.info(f"Tracking finished: {totals}")
