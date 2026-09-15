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
- ``capture_id`` and ``image_timestamp``: the candidate's frame in the scored pair,
  the one its ``image`` is a crop of.
- ``edge_image`` and ``edge_timestamp``: the track frame in the scored pair: its first
  frame for a ``before`` candidate, its last for an ``after`` one, the nearest one in
  time for a ``gap`` candidate. The two crops can then be shown side by side.

Candidates of every relation are sorted together by cost and capped once.

Vectors are loaded only for the frames in the scored pairs: one per candidate and the
occurrence's frames those are paired with.
"""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING, Any

from django.db.models import Q, QuerySet

from ami.main.models_future.track_stats import bbox_corners, frame_diagonal

if TYPE_CHECKING:
    from ami.main.models import Occurrence

DEFAULT_WINDOW_MINUTES = 5
MAX_WINDOW_MINUTES = 30
DEFAULT_ADJACENT_CAPTURES = 1
MAX_ADJACENT_CAPTURES = 10
MAX_CANDIDATES = 50

RELATION_BEFORE = "before"
RELATION_AFTER = "after"
RELATION_GAP = "gap"
RELATIONS = (RELATION_BEFORE, RELATION_AFTER, RELATION_GAP)

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


def _score_pair(
    track_frame: dict, frame: dict, track_vector, frame_vector
) -> tuple[float | None, float | None, float | None]:
    """(distance, similarity, cost) for one pair, or Nones for a box that cannot be read."""
    from ami.ml.post_processing.tracking_task import cosine_similarity, distance_ratio, total_cost

    corners_a = bbox_corners(track_frame["bbox"])
    corners_b = bbox_corners(frame["bbox"])
    if corners_a is None or corners_b is None:
        return None, None, None

    diagonal = _pair_diagonal(track_frame, frame, corners_a, corners_b)
    distance = round(distance_ratio(corners_a, corners_b, diagonal), _ROUND_TO)
    similarity = (
        round(cosine_similarity(track_vector, frame_vector), _ROUND_TO)
        if track_vector is not None and frame_vector is not None
        else None
    )
    cost = round(total_cost(track_vector, frame_vector, corners_a, corners_b, diagonal), _ROUND_TO)
    return distance, similarity, cost


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
        distance, similarity, cost = _score_pair(track_frame, frame, track_vector, frame_vector)
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
                "distance": distance,
                "similarity": similarity,
                "cost": cost,
                "image": get_media_url(crop) if crop else None,
                "capture_id": frame["source_image_id"],
                "image_timestamp": frame["timestamp"],
                "edge_image": get_media_url(track_frame["path"]) if track_frame["path"] else None,
                "edge_timestamp": track_frame["timestamp"],
            }
        )

    rows.sort(key=_rank_key)
    return rows[:limit]
