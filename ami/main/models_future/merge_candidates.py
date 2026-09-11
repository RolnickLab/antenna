"""Other occurrences one occurrence could be merged with, best fit first.

Tracking leaves one animal as two occurrences rather than risk merging two animals,
so the repair is a merge a person chooses. This ranks the choices the way tracking
would have: by the matching cost between the two frames that are nearest in time,
the occurrence's edge frame and the candidate's frame closest to it.

Candidates are occurrences of the same session with a frame within a window around
the occurrence's first or last frame. Each is described by:

- ``relation``: ``before`` when the candidate ends before the occurrence starts,
  ``after`` when it starts after the occurrence ends, ``overlapping`` otherwise.
- ``time_offset_seconds``: the gap between the two spans, negative for ``before``,
  positive for ``after`` and zero when they overlap.
- ``distance``: centre-to-centre distance of the nearest pair of boxes as a fraction
  of the frame diagonal.
- ``similarity``: cosine similarity of the pair's feature vectors, from the same
  algorithm that produced the occurrence's own vector. Null when either has none.
- ``cost``: the tracking method's matching cost for the pair. Geometry only when
  similarity is null, which lowers the total, so a candidate without a vector can
  outrank one with a poor vector match. Null when either box is malformed.

Vectors are loaded only for the pairs scored: the occurrence's two edge frames and one
frame per candidate.
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
MAX_CANDIDATES = 50

RELATION_BEFORE = "before"
RELATION_AFTER = "after"
RELATION_OVERLAPPING = "overlapping"
RELATIONS = (RELATION_BEFORE, RELATION_AFTER, RELATION_OVERLAPPING)

_ROUND_TO = 4

# One frame as a plain row, so nothing here can trigger a deferred-field query.
_FRAME_FIELDS = (
    "pk",
    "occurrence_id",
    "timestamp",
    "bbox",
    "path",
    "source_image__width",
    "source_image__height",
)


def _timed_frames(queryset) -> list[dict[str, Any]]:
    return [row for row in queryset.order_by("timestamp", "pk").values(*_FRAME_FIELDS) if row["timestamp"] is not None]


def _nearest_pair(edges: list[dict], frames: list[dict]) -> tuple[dict, dict]:
    """The occurrence edge and candidate frame closest to each other in time."""
    return min(
        ((edge, frame) for edge in edges for frame in frames),
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
    return RELATION_OVERLAPPING, 0.0


def _pair_diagonal(edge: dict, frame: dict, corners_a, corners_b) -> float:
    """The tracking method's integer diagonal when the captures carry dimensions, else
    the same fallback the track stats use."""
    from ami.ml.post_processing.tracking_task import image_diagonal

    width = max(edge["source_image__width"] or 0, frame["source_image__width"] or 0)
    height = max(edge["source_image__height"] or 0, frame["source_image__height"] or 0)
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


def _score_pair(edge: dict, frame: dict, edge_vector, frame_vector) -> tuple[float | None, float | None, float | None]:
    """(distance, similarity, cost) for one pair, or Nones for a box that cannot be read."""
    from ami.ml.post_processing.tracking_task import cosine_similarity, distance_ratio, total_cost

    corners_a = bbox_corners(edge["bbox"])
    corners_b = bbox_corners(frame["bbox"])
    if corners_a is None or corners_b is None:
        return None, None, None

    diagonal = _pair_diagonal(edge, frame, corners_a, corners_b)
    distance = round(distance_ratio(corners_a, corners_b, diagonal), _ROUND_TO)
    similarity = (
        round(cosine_similarity(edge_vector, frame_vector), _ROUND_TO)
        if edge_vector is not None and frame_vector is not None
        else None
    )
    cost = round(total_cost(edge_vector, frame_vector, corners_a, corners_b, diagonal), _ROUND_TO)
    return distance, similarity, cost


def rank_merge_candidates(
    occurrence: Occurrence,
    occurrences: QuerySet[Occurrence],
    minutes: int = DEFAULT_WINDOW_MINUTES,
    limit: int = MAX_CANDIDATES,
) -> list[dict[str, Any]]:
    """Candidates for merging with ``occurrence``, lowest cost first, at most ``limit``.

    ``occurrences`` decides which occurrences may be offered at all: pass the API's
    queryset so visibility and the project's default filters apply, and so the list
    matches what the merge action accepts. It must carry ``with_timestamps()`` and
    ``with_detections_count()`` and select ``determination``. Prefetches on it are
    wasted, since only the annotated fields are read.

    Five queries regardless of how many candidates there are: the occurrence's
    frames, the frames in the window, the candidate occurrences, and one vector
    query for each side of the pairs.
    """
    from ami.main.models import Classification, Detection, get_media_url

    target_frames = _timed_frames(Detection.objects.valid().filter(occurrence_id=occurrence.pk))
    if not target_frames:
        return []
    first, last = target_frames[0], target_frames[-1]
    edges = [first] if first["pk"] == last["pk"] else [first, last]

    delta = datetime.timedelta(minutes=minutes)
    window = Q(timestamp__range=(first["timestamp"] - delta, first["timestamp"] + delta)) | Q(
        timestamp__range=(last["timestamp"] - delta, last["timestamp"] + delta)
    )
    nearby = _timed_frames(
        Detection.objects.valid()
        .filter(window, occurrence__event_id=occurrence.event_id)
        .exclude(occurrence_id=occurrence.pk)
        .exclude(occurrence_id__isnull=True)
    )
    frames_by_occurrence: dict[int, list[dict]] = {}
    for frame in nearby:
        frames_by_occurrence.setdefault(frame["occurrence_id"], []).append(frame)
    if not frames_by_occurrence:
        return []

    candidates = list(occurrences.filter(pk__in=list(frames_by_occurrence)))
    pairs = {candidate.pk: _nearest_pair(edges, frames_by_occurrence[candidate.pk]) for candidate in candidates}

    edge_vectors = _latest_vectors(
        Classification.objects.filter(
            detection_id__in=[edge["pk"] for edge in edges],
            algorithm_id__isnull=False,
            features_2048__isnull=False,
        )
    )
    frame_vectors: dict[tuple[int, int], Any] = {}
    if edge_vectors:
        frame_vectors = _latest_vectors(
            Classification.objects.filter(
                detection_id__in=[frame["pk"] for _, frame in pairs.values()],
                algorithm_id__in={algorithm_id for _, algorithm_id in edge_vectors},
                features_2048__isnull=False,
            )
        )
    vector_by_edge = {
        detection_id: (algorithm_id, vector) for (detection_id, algorithm_id), vector in edge_vectors.items()
    }

    ranked = []
    for candidate in candidates:
        edge, frame = pairs[candidate.pk]
        algorithm_id, edge_vector = vector_by_edge.get(edge["pk"], (None, None))
        frame_vector = frame_vectors.get((frame["pk"], algorithm_id)) if algorithm_id is not None else None
        distance, similarity, cost = _score_pair(edge, frame, edge_vector, frame_vector)
        relation, offset = _relation(
            first["timestamp"],
            last["timestamp"],
            candidate.first_appearance_timestamp,
            candidate.last_appearance_timestamp,
        )
        crop = frame["path"] or next((f["path"] for f in frames_by_occurrence[candidate.pk] if f["path"]), None)
        ranked.append(
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
            }
        )

    ranked.sort(key=lambda row: (row["cost"] is None, row["cost"] or 0.0, abs(row["time_offset_seconds"]), row["id"]))
    return ranked[:limit]
