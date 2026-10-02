"""Find a detection again on another Antenna instance, without its primary key.

Primary keys do not survive a move between databases: a fresh import assigns new ids to
every capture, detection and occurrence. What does survive is the capture's path under its
data source, its timestamp and station, the bounding box, and the name of the detector
that drew it. A ``DetectionKey`` carries exactly those, and ``match_detections`` turns a
list of keys back into detection ids on the target database.

Matching is exact when the detector rerun gives the same box, and falls back to the
candidate with the highest intersection over union when it does not (a newer model
version, or a rounding difference). Every match records which of the two it was and the
IoU, so a caller can refuse to trust a fuzzy match where exactness matters.
"""

from __future__ import annotations

import dataclasses
import datetime
import logging
from collections import defaultdict
from collections.abc import Iterable

from ami.main.models import Detection, Project, SourceImage

logger = logging.getLogger(__name__)

DEFAULT_IOU_THRESHOLD = 0.7

# Two boxes within this many pixels on every edge are the same box: JSON round trips and
# float formatting can shift a coordinate by a fraction of a pixel.
EXACT_BOX_TOLERANCE_PX = 0.5

# How a key was, or was not, found again on the target database.
MATCH_EXACT = "exact"
MATCH_IOU = "iou"
MATCH_NO_CANDIDATE = "no_candidate"  # the capture exists but no box on it is close enough
MATCH_NO_CAPTURE = "no_capture"  # the capture itself is not in the project


@dataclasses.dataclass(frozen=True)
class DetectionKey:
    """The natural key of a detection: where its capture is and what box it holds."""

    capture_path: str
    bbox: tuple[float, float, float, float]
    capture_timestamp: str | None = None
    deployment: str | None = None
    detector: str | None = None

    @classmethod
    def for_detection(cls, detection: Detection) -> DetectionKey:
        """Build the key of a loaded detection. ``source_image`` and its ``deployment`` should be
        selected already, and ``detection_algorithm`` too, or this costs three queries per call."""
        capture = detection.source_image
        return cls(
            capture_path=capture.path,
            bbox=normalise_bbox(detection.bbox),
            capture_timestamp=capture.timestamp.isoformat() if capture.timestamp else None,
            deployment=capture.deployment.name if capture.deployment_id else None,
            detector=detection.detection_algorithm.name if detection.detection_algorithm_id else None,
        )

    def as_dict(self) -> dict:
        data = dataclasses.asdict(self)
        data["bbox"] = list(self.bbox)
        return data

    @classmethod
    def from_dict(cls, data: dict) -> DetectionKey:
        return cls(
            capture_path=data["capture_path"],
            bbox=normalise_bbox(data["bbox"]),
            capture_timestamp=data.get("capture_timestamp"),
            deployment=data.get("deployment"),
            detector=data.get("detector"),
        )


@dataclasses.dataclass
class DetectionMatch:
    """What ``match_detections`` found for one key."""

    key: DetectionKey
    status: str
    detection_id: int | None = None
    capture_id: int | None = None
    occurrence_id: int | None = None
    event_id: int | None = None
    iou: float | None = None

    @property
    def found(self) -> bool:
        return self.detection_id is not None

    def as_dict(self) -> dict:
        return {
            "key": self.key.as_dict(),
            "status": self.status,
            "detection_id": self.detection_id,
            "capture_id": self.capture_id,
            "occurrence_id": self.occurrence_id,
            "iou": self.iou,
        }


def normalise_bbox(bbox: Iterable[float] | None) -> tuple[float, float, float, float]:
    if bbox is None:
        raise ValueError("A detection without a bounding box has no natural key.")
    x1, y1, x2, y2 = (float(value) for value in bbox)
    return (x1, y1, x2, y2)


def bbox_iou(a: Iterable[float], b: Iterable[float]) -> float:
    """Intersection over union of two ``[x1, y1, x2, y2]`` boxes; 0 when either is empty."""
    ax1, ay1, ax2, ay2 = normalise_bbox(a)
    bx1, by1, bx2, by2 = normalise_bbox(b)
    inter_w = min(ax2, bx2) - max(ax1, bx1)
    inter_h = min(ay2, by2) - max(ay1, by1)
    if inter_w <= 0 or inter_h <= 0:
        return 0.0
    intersection = inter_w * inter_h
    union = (ax2 - ax1) * (ay2 - ay1) + (bx2 - bx1) * (by2 - by1) - intersection
    return intersection / union if union > 0 else 0.0


def boxes_are_the_same(a: Iterable[float], b: Iterable[float], tolerance: float = EXACT_BOX_TOLERANCE_PX) -> bool:
    return all(abs(p - q) <= tolerance for p, q in zip(normalise_bbox(a), normalise_bbox(b)))


def _parse_timestamp(value: str | None) -> datetime.datetime | None:
    if not value:
        return None
    # Capture timestamps are naive local time (USE_TZ is off); drop any offset an exporter added.
    return datetime.datetime.fromisoformat(value).replace(tzinfo=None)


@dataclasses.dataclass
class _Capture:
    id: int
    path: str
    timestamp: datetime.datetime | None
    deployment: str | None
    event_id: int | None


@dataclasses.dataclass
class _Candidate:
    id: int
    bbox: list[float]
    detector: str | None
    occurrence_id: int | None


def _captures_for_keys(project: Project, keys: Iterable[DetectionKey]) -> dict[DetectionKey, _Capture | None]:
    """Resolve each key's capture: by path within the project, else by station and timestamp."""
    keys = list(keys)
    by_path: dict[str, list[_Capture]] = defaultdict(list)
    rows = (
        SourceImage.objects.filter(project=project, path__in={key.capture_path for key in keys})
        .order_by("pk")
        .values_list("pk", "path", "timestamp", "deployment__name", "event_id")
    )
    for pk, path, timestamp, deployment, event_id in rows:
        by_path[path].append(_Capture(pk, path, timestamp, deployment, event_id))

    resolved: dict[DetectionKey, _Capture | None] = {}
    unresolved: list[DetectionKey] = []
    for key in keys:
        candidates = by_path.get(key.capture_path, [])
        if len(candidates) > 1:
            # The same path under two data sources: the station and the timestamp decide.
            narrowed = [c for c in candidates if key.deployment is None or c.deployment == key.deployment]
            wanted = _parse_timestamp(key.capture_timestamp)
            if wanted is not None and len(narrowed) > 1:
                narrowed = [c for c in narrowed if c.timestamp == wanted]
            candidates = narrowed or candidates
        if candidates:
            resolved[key] = candidates[0]
        else:
            unresolved.append(key)

    if unresolved:
        # A re-import under a different prefix changes the path but not the station or the time.
        wanted = {(key.deployment, _parse_timestamp(key.capture_timestamp)) for key in unresolved}
        wanted.discard((None, None))
        rows = (
            SourceImage.objects.filter(
                project=project,
                deployment__name__in={deployment for deployment, _ in wanted if deployment},
                timestamp__in={timestamp for _, timestamp in wanted if timestamp},
            )
            .order_by("pk")
            .values_list("pk", "path", "timestamp", "deployment__name", "event_id")
        )
        by_station_time = {
            (deployment, timestamp): _Capture(pk, path, timestamp, deployment, event_id)
            for pk, path, timestamp, deployment, event_id in rows
        }
        for key in unresolved:
            resolved[key] = by_station_time.get((key.deployment, _parse_timestamp(key.capture_timestamp)))
    return resolved


def _candidates_by_capture(capture_ids: Iterable[int]) -> dict[int, list[_Candidate]]:
    candidates: dict[int, list[_Candidate]] = defaultdict(list)
    rows = (
        Detection.objects.valid()
        .filter(source_image_id__in=list(capture_ids), bbox__isnull=False)
        .order_by("pk")
        .values_list("pk", "source_image_id", "bbox", "detection_algorithm__name", "occurrence_id")
    )
    for pk, capture_id, bbox, detector, occurrence_id in rows:
        candidates[capture_id].append(_Candidate(pk, bbox, detector, occurrence_id))
    return candidates


def _pick(key: DetectionKey, candidates: list[_Candidate], threshold: float) -> tuple[_Candidate | None, str, float]:
    """The best unclaimed candidate for ``key``: the same box, else the closest box past the threshold.

    Candidates from the key's own detector are preferred when any exist, so a box the
    classifier's own detector drew wins over a coincidentally similar box from another one.
    """
    same_detector = [c for c in candidates if key.detector and c.detector == key.detector]
    pool = same_detector or candidates
    for candidate in pool:
        if boxes_are_the_same(candidate.bbox, key.bbox):
            return candidate, MATCH_EXACT, 1.0
    best, best_iou = None, 0.0
    for candidate in pool:
        iou = bbox_iou(candidate.bbox, key.bbox)
        if iou > best_iou:
            best, best_iou = candidate, iou
    if best is not None and best_iou >= threshold:
        return best, MATCH_IOU, best_iou
    return None, MATCH_NO_CANDIDATE, best_iou


def match_detections(
    project: Project, keys: Iterable[DetectionKey], iou_threshold: float = DEFAULT_IOU_THRESHOLD
) -> list[DetectionMatch]:
    """Find each key's detection in ``project``, in the order given, with two queries per call.

    A detection on the target is claimed by at most one key, so two keys that both
    resemble one box do not both land on it. Keys are matched in the order given, and a
    key whose exact box was already claimed falls through to its next best candidate.
    """
    keys = list(keys)
    captures = _captures_for_keys(project, keys)
    candidates = _candidates_by_capture({capture.id for capture in captures.values() if capture})
    claimed: set[int] = set()
    matches: list[DetectionMatch] = []
    for key in keys:
        capture = captures.get(key)
        if capture is None:
            matches.append(DetectionMatch(key=key, status=MATCH_NO_CAPTURE))
            continue
        available = [c for c in candidates.get(capture.id, []) if c.id not in claimed]
        picked, status, iou = _pick(key, available, iou_threshold)
        if picked is None:
            matches.append(DetectionMatch(key=key, status=status, capture_id=capture.id, event_id=capture.event_id))
            continue
        claimed.add(picked.id)
        matches.append(
            DetectionMatch(
                key=key,
                status=status,
                detection_id=picked.id,
                capture_id=capture.id,
                occurrence_id=picked.occurrence_id,
                event_id=capture.event_id,
                iou=round(iou, 4),
            )
        )
    return matches
