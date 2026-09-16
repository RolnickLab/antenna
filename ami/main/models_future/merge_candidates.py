"""Other occurrences one occurrence could be merged with, best fit first.

Tracking leaves one animal as two occurrences rather than risk merging two animals,
so the repair is a merge a person chooses. This ranks the choices the way tracking
would have: by the matching cost between the two frames, one from each, that are
nearest in time.

Candidates are occurrences of the same session with a frame among the searched
captures. By default those are the captures adjacent to the occurrence: a number of
captures before its first frame and after its last one (``captures``), plus the
captures inside its own span. Passing ``minutes`` searches from that many minutes
before the first frame to that many minutes after the last instead.

One animal cannot appear twice in one capture, so an occurrence with a frame on one
of the occurrence's captures is another animal and is never offered. In a dense
session those outnumber the true neighbours many times over.

Each candidate is described by:

- ``relation``: ``before`` when the candidate ends before the occurrence starts,
  ``after`` when it starts after the occurrence ends, and ``gap`` otherwise: it lies
  within the occurrence's span on captures the occurrence has no frame on, where
  tracking lost the animal for a few captures.
- ``time_offset_seconds``: the gap between the two spans, negative for ``before``,
  positive for ``after`` and zero for ``gap``.
- ``distance``: centre-to-centre distance of the nearest pair of boxes as a fraction
  of the frame diagonal.
- ``similarity``: cosine similarity of the pair's feature vectors, from the same
  algorithm that produced the occurrence's own vector. Null when either has none.
- ``cost``: the tracking method's matching cost for the pair. Geometry only when
  similarity is null, which lowers the total, so a candidate without a vector can
  outrank one with a poor vector match. Null when either box is malformed.
- ``iou``, ``size_ratio`` and ``likelihood``: the remaining terms of that cost and
  one minus its mean term, the same numbers the capture preview reports.
- ``would_link``: whether the pair passes the tracker's pairing rule, a cost under
  its threshold with a vector on both frames when it requires one.
- ``capture_id`` and ``image_timestamp``: the candidate's frame in the scored pair,
  the one its ``image`` is a crop of.
- ``edge_image`` and ``edge_timestamp``: the track frame in the scored pair: its first
  frame for a ``before`` candidate, its last for an ``after`` one, the nearest one in
  time for a ``gap`` candidate. The two crops can then be shown side by side.

Candidates of every relation are sorted together by cost and capped once.

Vectors are loaded only for the frames in the scored pairs: one per candidate and the
occurrence's frames those are paired with.

``match_capture_detections`` previews what tracking would link on one capture, with the
tracker's own matcher, for a person extending the track capture by capture.
"""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING, Any

from django.db.models import Q, QuerySet

from ami.main.models_future.track_stats import bbox_corners, frame_diagonal

if TYPE_CHECKING:
    from ami.main.models import Occurrence, SourceImage
    from ami.ml.post_processing.tracking_task import TrackingConfig

DEFAULT_WINDOW_MINUTES = 5
MAX_WINDOW_MINUTES = 30
DEFAULT_ADJACENT_CAPTURES = 1
MAX_ADJACENT_CAPTURES = 10
MAX_CANDIDATES = 50

RELATION_BEFORE = "before"
RELATION_AFTER = "after"
RELATION_GAP = "gap"
RELATIONS = (RELATION_BEFORE, RELATION_AFTER, RELATION_GAP)
# A capture that already holds one of the track's frames, scored against another frame.
RELATION_SAME = "same"
CAPTURE_MATCH_RELATIONS = (*RELATIONS, RELATION_SAME)

_ROUND_TO = 4

# One frame as a plain row, so nothing here can trigger a deferred-field query.
_FRAME_FIELDS = (
    "pk",
    "occurrence_id",
    "source_image_id",
    "timestamp",
    "bbox",
    "path",
    "source_image__width",
    "source_image__height",
)


def _timed_frames(queryset) -> list[dict[str, Any]]:
    return [row for row in queryset.order_by("timestamp", "pk").values(*_FRAME_FIELDS) if row["timestamp"] is not None]


def _adjacent_capture_ids(
    event_id: int, first: datetime.datetime, last: datetime.datetime, captures: int
) -> list[int]:
    """Ids of the ``captures`` captures of the session just before ``first`` and just after ``last``.

    The ids are materialised so the frame query filters on literal values, which the
    planner can serve from the index instead of scanning the detections table.
    """
    from ami.main.models import SourceImage

    session = SourceImage.objects.filter(event_id=event_id)
    before = session.filter(timestamp__lt=first).order_by("-timestamp", "-pk").values_list("pk", flat=True)
    after = session.filter(timestamp__gt=last).order_by("timestamp", "pk").values_list("pk", flat=True)
    return list(before[:captures]) + list(after[:captures])


def _nearest_pair(track_frames: list[dict], frames: list[dict]) -> tuple[dict, dict]:
    """The track frame and candidate frame closest to each other in time."""
    return min(
        ((track_frame, frame) for track_frame in track_frames for frame in frames),
        key=lambda pair: (abs(pair[1]["timestamp"] - pair[0]["timestamp"]), pair[0]["pk"], pair[1]["pk"]),
    )


def _relation(
    target_first: datetime.datetime,
    target_last: datetime.datetime,
    candidate_first: datetime.datetime,
    candidate_last: datetime.datetime,
) -> tuple[str, float]:
    if candidate_last < target_first:
        return RELATION_BEFORE, (candidate_last - target_first).total_seconds()
    if candidate_first > target_last:
        return RELATION_AFTER, (candidate_first - target_last).total_seconds()
    return RELATION_GAP, 0.0


def _pair_diagonal(track_frame: dict, frame: dict, corners_a, corners_b) -> float:
    """The tracking method's integer diagonal when the captures carry dimensions, else
    the same fallback the track stats use."""
    from ami.ml.post_processing.tracking_task import image_diagonal

    width = max(track_frame["source_image__width"] or 0, frame["source_image__width"] or 0)
    height = max(track_frame["source_image__height"] or 0, frame["source_image__height"] or 0)
    if width and height:
        return float(image_diagonal(width, height))
    return frame_diagonal(None, None, max(corners_a[2], corners_b[2]), max(corners_a[3], corners_b[3]))


def _latest_vectors(classifications) -> dict[tuple[int, int], Any]:
    """Most recent feature vector per (detection, algorithm) among the rows given."""
    vectors: dict[tuple[int, int], Any] = {}
    rows = classifications.order_by("-timestamp", "-pk").values_list("detection_id", "algorithm_id", "features_2048")
    for detection_id, algorithm_id, vector in rows:
        vectors.setdefault((detection_id, algorithm_id), vector)
    return vectors


def _score_pair(track_frame: dict, frame: dict, track_vector, frame_vector) -> dict[str, float | None]:
    """The cost terms for one pair of frames, all None for a box that cannot be read."""
    corners_a = bbox_corners(track_frame["bbox"])
    corners_b = bbox_corners(frame["bbox"])
    if corners_a is None or corners_b is None:
        return dict.fromkeys(_PAIR_SCORE_FIELDS)
    diagonal = _pair_diagonal(track_frame, frame, corners_a, corners_b)
    return _pair_scores(corners_a, corners_b, track_vector, frame_vector, diagonal)


def _would_link(scores: dict[str, float | None], config: TrackingConfig) -> bool:
    """Whether the pair passes the tracker's pairing rule: a cost under its threshold, and a
    vector on both frames when it requires them. A preview of the rule, not of a run: the
    matcher only pairs adjacent captures and claims each box once."""
    if scores["cost"] is None or (config.require_features and scores["similarity"] is None):
        return False
    return scores["cost"] < config.cost_threshold


def _rank_key(row: dict[str, Any]) -> tuple:
    """Lowest cost first, unscored rows last, nearest in time and then oldest as tie-breaks."""
    return (row["cost"] is None, row["cost"] or 0.0, abs(row["time_offset_seconds"]), row["id"])


def rank_merge_candidates(
    occurrence: Occurrence,
    occurrences: QuerySet[Occurrence],
    minutes: int | None = None,
    captures: int = DEFAULT_ADJACENT_CAPTURES,
    limit: int = MAX_CANDIDATES,
) -> list[dict[str, Any]]:
    """Candidates for merging with ``occurrence``, lowest cost first, at most ``limit``.

    The captures searched are the ``captures`` captures before the occurrence's first
    frame and after its last one, plus those inside its span, unless ``minutes`` is
    given, in which case the search runs from that many minutes before the first
    frame to that many minutes after the last.

    Candidates with a frame on one of the occurrence's captures are dropped using the
    frames already loaded. That is exact because those captures all lie inside the
    occurrence's span, which both searches cover in full.

    ``occurrences`` decides which occurrences may be offered at all: pass the API's
    queryset so visibility and the project's default filters apply, and so the list
    matches what the merge action accepts. It must carry ``with_timestamps()`` and
    ``with_detections_count()`` and select ``determination``. Prefetches on it are
    wasted, since only the annotated fields are read.

    The query count does not depend on how many candidates there are: the
    occurrence's frames, the adjacent capture ids (two queries, skipped in minutes
    mode), the searched frames, the candidate occurrences, and one vector query for
    each side of the pairs.
    """
    from ami.main.models import Classification, Detection, get_media_url

    config = tracking_config_for(occurrence)
    target_frames = _timed_frames(Detection.objects.valid().filter(occurrence_id=occurrence.pk))
    if not target_frames:
        return []
    first, last = target_frames[0], target_frames[-1]
    target_captures = {frame["source_image_id"] for frame in target_frames}

    if minutes is not None:
        delta = datetime.timedelta(minutes=minutes)
        searched = Q(timestamp__range=(first["timestamp"] - delta, last["timestamp"] + delta))
    else:
        adjacent = _adjacent_capture_ids(occurrence.event_id, first["timestamp"], last["timestamp"], captures)
        searched = Q(source_image_id__in=adjacent) | Q(timestamp__range=(first["timestamp"], last["timestamp"]))
    nearby = _timed_frames(
        Detection.objects.valid()
        .filter(searched, occurrence__event_id=occurrence.event_id)
        .exclude(occurrence_id=occurrence.pk)
        .exclude(occurrence_id__isnull=True)
    )
    other_animals = {frame["occurrence_id"] for frame in nearby if frame["source_image_id"] in target_captures}
    frames_by_occurrence: dict[int, list[dict]] = {}
    for frame in nearby:
        if frame["occurrence_id"] not in other_animals:
            frames_by_occurrence.setdefault(frame["occurrence_id"], []).append(frame)
    if not frames_by_occurrence:
        return []

    scored = [
        (
            candidate,
            *_relation(
                first["timestamp"],
                last["timestamp"],
                candidate.first_appearance_timestamp,
                candidate.last_appearance_timestamp,
            ),
        )
        for candidate in occurrences.filter(pk__in=list(frames_by_occurrence))
    ]
    if not scored:
        return []

    # A gap candidate lies inside the track's span, so any track frame can be nearest it.
    track_side = {RELATION_BEFORE: [first], RELATION_AFTER: [last], RELATION_GAP: target_frames}
    pairs = {
        candidate.pk: _nearest_pair(track_side[relation], frames_by_occurrence[candidate.pk])
        for candidate, relation, _ in scored
    }

    track_vectors = _latest_vectors(
        Classification.objects.filter(
            detection_id__in={track_frame["pk"] for track_frame, _ in pairs.values()},
            algorithm_id__isnull=False,
            features_2048__isnull=False,
        )
    )
    frame_vectors: dict[tuple[int, int], Any] = {}
    if track_vectors:
        frame_vectors = _latest_vectors(
            Classification.objects.filter(
                detection_id__in=[frame["pk"] for _, frame in pairs.values()],
                algorithm_id__in={algorithm_id for _, algorithm_id in track_vectors},
                features_2048__isnull=False,
            )
        )
    vector_by_track_frame = {
        detection_id: (algorithm_id, vector) for (detection_id, algorithm_id), vector in track_vectors.items()
    }

    rows: list[dict[str, Any]] = []
    for candidate, relation, offset in scored:
        track_frame, frame = pairs[candidate.pk]
        algorithm_id, track_vector = vector_by_track_frame.get(track_frame["pk"], (None, None))
        frame_vector = frame_vectors.get((frame["pk"], algorithm_id)) if algorithm_id is not None else None
        scores = _score_pair(track_frame, frame, track_vector, frame_vector)
        crop = frame["path"] or next((f["path"] for f in frames_by_occurrence[candidate.pk] if f["path"]), None)
        rows.append(
            {
                "id": candidate.pk,
                "determination": (
                    {"id": candidate.determination_id, "name": candidate.determination.name}
                    if candidate.determination_id
                    else None
                ),
                "detections_count": candidate.detections_count,
                "first_appearance_timestamp": candidate.first_appearance_timestamp,
                "last_appearance_timestamp": candidate.last_appearance_timestamp,
                "relation": relation,
                "time_offset_seconds": offset,
                **scores,
                "would_link": _would_link(scores, config),
                "image": get_media_url(crop) if crop else None,
                "capture_id": frame["source_image_id"],
                "image_timestamp": frame["timestamp"],
                "edge_image": get_media_url(track_frame["path"]) if track_frame["path"] else None,
                "edge_timestamp": track_frame["timestamp"],
            }
        )

    rows.sort(key=_rank_key)
    return rows[:limit]


_PAIR_SCORE_FIELDS = ("likelihood", "cost", "distance", "iou", "size_ratio", "similarity")
_MATCH_SCORE_FIELDS = _PAIR_SCORE_FIELDS + ("time_offset_seconds",)
SKIPPED_NO_VECTOR = "no_vector"
SKIPPED_REASONS = (SKIPPED_NO_VECTOR,)


def tracking_config_for(occurrence: Occurrence) -> TrackingConfig:
    """The settings tracking runs with on the occurrence's session: the threshold and the
    feature requirement the previews here judge pairs by."""
    from ami.ml.post_processing.tracking_task import TrackingConfig

    return TrackingConfig(event_ids=[occurrence.event_id])


def _likelihood(cost: float, similarity: float | None) -> float:
    # One minus the mean cost term. Every term lies in [0, 1], so a value reads the same on any
    # capture, and the tracker's 0.2 cut-off sits near 0.95. It stays continuous so near misses
    # still read as likely; ``would_link`` carries the tracker's own decision.
    terms = 3 if similarity is None else 4
    return round(min(max(1 - cost / terms, 0.0), 1.0), _ROUND_TO)


def _pair_scores(bbox_a, bbox_b, vector_a, vector_b, diag: float) -> dict[str, float | None]:
    """The tracking cost between two boxes, each of its terms, and the likelihood."""
    from ami.ml.post_processing.tracking_task import box_ratio, cosine_similarity, distance_ratio, iou, total_cost

    cost = total_cost(vector_a, vector_b, bbox_a, bbox_b, diag)
    similarity = None
    if vector_a is not None and vector_b is not None:
        similarity = round(cosine_similarity(vector_a, vector_b), _ROUND_TO)
    return {
        "likelihood": _likelihood(cost, similarity),
        "cost": round(cost, _ROUND_TO),
        "distance": round(distance_ratio(bbox_a, bbox_b, diag), _ROUND_TO),
        "iou": round(iou(bbox_a, bbox_b), _ROUND_TO),
        "size_ratio": round(box_ratio(bbox_a, bbox_b), _ROUND_TO),
        "similarity": similarity,
    }


def _reference_frame(occurrence_id: int, capture: SourceImage) -> tuple[dict | None, str | None]:
    """The track frame nearest in time to ``capture`` on another capture, and which side of
    the track the capture lies on, read from the nearest frame on each side of it."""
    from ami.main.models import Detection

    track = (
        Detection.objects.valid()
        .filter(occurrence_id=occurrence_id, timestamp__isnull=False)
        .exclude(source_image_id=capture.pk)
    )
    earlier = track.filter(timestamp__lte=capture.timestamp).order_by("-timestamp", "-pk").values(*_FRAME_FIELDS)
    later = track.filter(timestamp__gte=capture.timestamp).order_by("timestamp", "pk").values(*_FRAME_FIELDS)
    frames = sorted(earlier[:1].union(later[:1], all=True), key=lambda frame: (frame["timestamp"], frame["pk"]))
    if not frames:
        return None, None
    reference, _ = _nearest_pair(frames, [{"pk": capture.pk, "timestamp": capture.timestamp}])
    relation, _ = _relation(frames[0]["timestamp"], frames[-1]["timestamp"], capture.timestamp, capture.timestamp)
    return reference, relation


def match_capture_detections(occurrence: Occurrence, capture: SourceImage) -> dict[str, Any]:
    """Every real box on ``capture`` scored against ``occurrence``'s track the way tracking scores it.

    The reference is the track frame nearest in time on another capture. The tracker's own
    matcher runs between every box on the reference frame's capture and every box on
    ``capture``, with the tracker's default settings, feature algorithm and image diagonal,
    and ``would_link`` marks the box it links the reference frame to. Tracking only pairs
    adjacent captures, so across a longer gap this previews its pairing rule, not a run.

    The track's own box is returned unscored. So is every box when the track has no other
    frame, or when the earlier of the two captures has no dimensions, since tracking skips
    such a pair of captures. The query count is fixed, whatever the track's length or the
    number of boxes.
    """
    from ami.main.models import Classification, Detection, SourceImage
    from ami.ml.models import Algorithm
    from ami.ml.post_processing.tracking_task import (
        image_diagonal,
        latest_feature_vectors,
        resolve_feature_algorithm,
        select_links,
    )

    config = tracking_config_for(occurrence)
    reference, relation = _reference_frame(occurrence.pk, capture) if capture.timestamp else (None, None)
    reference_capture_id = reference["source_image_id"] if reference is not None else None
    detections = list(
        Detection.objects.valid()
        .filter(source_image_id__in=[capture.pk] + ([reference_capture_id] if reference_capture_id else []))
        .only("pk", "bbox", "occurrence_id", "source_image_id")
        .order_by("pk")
    )
    boxes = [detection for detection in detections if detection.source_image_id == capture.pk]
    if reference is not None and any(box.occurrence_id == occurrence.pk for box in boxes):
        relation = RELATION_SAME

    # Tracking takes the one extractor with embeddings anywhere in the session, which scans
    # every classification (about 40 ms). The two captures being paired give the same answer
    # unless a session mixes extractors.
    detection_ids = [detection.pk for detection in detections]
    extractor_ids = set(
        Classification.objects.filter(
            detection_id__in=detection_ids, features_2048__isnull=False, algorithm_id__isnull=False
        )
        .order_by()
        .values_list("algorithm_id", flat=True)
        .distinct()
    )
    extractors = list(Algorithm.objects.filter(pk__in=extractor_ids))
    algorithm, _, _ = resolve_feature_algorithm(occurrence.event, config, candidates=extractors)
    vectors = latest_feature_vectors(detection_ids, algorithm.pk) if algorithm is not None else {}

    def skipped(detection_id: int) -> str | None:
        return SKIPPED_NO_VECTOR if config.require_features and detection_id not in vectors else None

    diag, linked, reference_detection = None, set(), None
    if reference is not None:
        reference_detection = next(d for d in detections if d.pk == reference["pk"])
        reference_boxes = [d for d in detections if d.source_image_id == reference_capture_id]
        capture_first = (capture.timestamp, capture.pk) < (reference["timestamp"], reference_capture_id)
        width, height = (
            (capture.width, capture.height)
            if capture_first
            else (reference["source_image__width"], reference["source_image__height"])
        )
        if width and height:
            diag = image_diagonal(width, height)
            current, following = (boxes, reference_boxes) if capture_first else (reference_boxes, boxes)
            links = select_links(current, following, vectors, diag, config.cost_threshold, config.require_features)
            linked = {frozenset((det.pk, nxt.pk)) for det, nxt, _ in links}

    # Captures from the reference frame's to this one, signed: 1 is the adjacent capture the
    # tracker would pair, so a larger count means the preview spans captures it never compares.
    capture_offset = None
    if reference is not None:
        (low_ts, low_pk), (high_ts, high_pk) = sorted(
            [(reference["timestamp"], reference_capture_id), (capture.timestamp, capture.pk)]
        )
        # The occurrence's session, not the capture's: the view loads the capture with
        # ``only()`` and reading ``capture.event_id`` would cost a query.
        between = (
            SourceImage.objects.filter(event_id=occurrence.event_id, timestamp__gte=low_ts, timestamp__lte=high_ts)
            .exclude(timestamp=low_ts, pk__lte=low_pk)
            .exclude(timestamp=high_ts, pk__gt=high_pk)
            .count()
        )
        capture_offset = (
            between if (capture.timestamp, capture.pk) > (reference["timestamp"], reference_capture_id) else -between
        )

    rows: list[dict[str, Any]] = []
    for box in boxes:
        in_track = box.occurrence_id == occurrence.pk
        row = {
            "detection_id": box.pk,
            "occurrence_id": box.occurrence_id,
            "in_track": in_track,
            "would_link": reference is not None and frozenset((reference["pk"], box.pk)) in linked,
            "skipped_reason": skipped(box.pk),
        }
        row.update(dict.fromkeys(_MATCH_SCORE_FIELDS))
        if reference is not None and not in_track:
            row["time_offset_seconds"] = (capture.timestamp - reference["timestamp"]).total_seconds()
            if diag is not None:
                row.update(
                    _pair_scores(
                        reference_detection.bbox,
                        box.bbox,
                        vectors.get(reference["pk"]),
                        vectors.get(box.pk),
                        diag,
                    )
                )
        rows.append(row)
    rows.sort(key=lambda row: (row["likelihood"] is None, -(row["likelihood"] or 0.0), row["detection_id"]))

    return {
        "capture_id": capture.pk,
        "cost_threshold": config.cost_threshold,
        "feature_algorithm_id": algorithm.pk if algorithm is not None else None,
        "requires_features": config.require_features,
        "reference": (
            {
                "detection_id": reference["pk"],
                "capture_id": reference_capture_id,
                "timestamp": reference["timestamp"],
                "relation": relation,
                "capture_offset": capture_offset,
                "skipped_reason": skipped(reference["pk"]),
            }
            if reference is not None
            else None
        ),
        "detections": rows,
    }
