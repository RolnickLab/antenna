"""Score a tracking run against tracks a person has confirmed.

Ground truth is the set of occurrences whose grouping a person confirmed: each one is taken
to be a complete and accurate track. Nothing is known about detections outside those tracks,
so every metric here is computed only over the detections that belong to a confirmed track.

This module imports nothing from Django, so it also runs outside Antenna on exported CSVs:

    python -m ami.ml.post_processing.tracking_evaluation --ground-truth gt.csv --predictions pred.csv
"""

from __future__ import annotations

import argparse
import collections
import csv
import dataclasses
import datetime
import json
import sys
import typing
from collections.abc import Hashable, Iterable, Mapping

DetectionId = Hashable
TrackId = Hashable

TRUE_VALUES = {"true", "1", "yes", "t", "y"}


def _sort_key(value: typing.Any) -> tuple:
    """Order ids of mixed types deterministically: numbers before strings."""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return (0, value, "")
    return (1, 0, str(value))


def _ratio(numerator: int, denominator: int) -> float | None:
    """A ratio, or None when it is undefined because nothing was counted."""
    return numerator / denominator if denominator else None


def _f1(precision: float | None, recall: float | None) -> float | None:
    if precision is None or recall is None:
        return None
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def _pairs(n: int) -> int:
    return n * (n - 1) // 2


@dataclasses.dataclass
class GroundTruthTrackScore:
    """How one confirmed track was rebuilt.

    ``fragments`` is the number of predicted tracks its detections were split across (1 is
    best); ``completeness`` is the share of its detections held by the largest of them.
    """

    track_id: TrackId
    length: int
    fragments: int
    completeness: float
    exactly_recovered: bool


@dataclasses.dataclass
class PredictedTrackScore:
    """One predicted track that holds at least one detection from a confirmed track.

    ``length`` counts only its detections in confirmed tracks. ``purity`` is the share of
    those held by the confirmed track it overlaps most; ``ground_truth_tracks`` above 1 is
    a merge of different insects.
    """

    track_id: TrackId
    length: int
    ground_truth_tracks: int
    purity: float


@dataclasses.dataclass
class TrackingEvaluation:
    """Scores of predicted tracks against confirmed tracks, over detections in confirmed tracks.

    Precision and recall are None when their denominator is zero, for example precision when
    no two detections were predicted to be the same insect.
    """

    ground_truth_tracks: int
    detections: int
    ground_truth_singletons: int
    predicted_tracks: int
    predicted_singletons: int

    # Every unordered pair of detections: is it the same insect in both?
    pairwise_true_positives: int
    pairwise_predicted: int
    pairwise_ground_truth: int
    pairwise_precision: float | None
    pairwise_recall: float | None
    pairwise_f1: float | None

    # Links between detections that follow each other in time within a track.
    links_correct: int
    links_predicted: int
    links_ground_truth: int
    link_precision: float | None
    link_recall: float | None
    link_f1: float | None

    merges: int
    fragmented_tracks: int
    exactly_recovered: int
    mean_completeness: float | None
    mean_purity: float | None

    ground_truth_track_scores: list[GroundTruthTrackScore]
    predicted_track_scores: list[PredictedTrackScore]

    def to_dict(self, include_tracks: bool = True) -> dict[str, typing.Any]:
        result = dataclasses.asdict(self)
        if not include_tracks:
            result.pop("ground_truth_track_scores")
            result.pop("predicted_track_scores")
        return result

    def summary_lines(self) -> list[str]:
        """The headline numbers as short human-readable lines."""

        def fmt(value: float | None) -> str:
            return "n/a" if value is None else f"{value:.3f}"

        return [
            f"Confirmed tracks: {self.ground_truth_tracks} ({self.ground_truth_singletons} single-detection), "
            f"detections: {self.detections}",
            f"Predicted tracks over those detections: {self.predicted_tracks} "
            f"({self.predicted_singletons} single-detection)",
            f"Pairwise precision {fmt(self.pairwise_precision)}  recall {fmt(self.pairwise_recall)}  "
            f"F1 {fmt(self.pairwise_f1)}  ({self.pairwise_true_positives}/{self.pairwise_predicted} predicted, "
            f"{self.pairwise_ground_truth} true pairs)",
            f"Link precision {fmt(self.link_precision)}  recall {fmt(self.link_recall)}  F1 {fmt(self.link_f1)}  "
            f"({self.links_correct}/{self.links_predicted} predicted, {self.links_ground_truth} true links)",
            f"Exactly recovered: {self.exactly_recovered}/{self.ground_truth_tracks}  "
            f"fragmented: {self.fragmented_tracks}  merges: {self.merges}",
            f"Mean completeness {fmt(self.mean_completeness)}  mean purity {fmt(self.mean_purity)}",
        ]


def _time_ordered(detection_ids: Iterable[DetectionId], timestamps: Mapping[DetectionId, typing.Any]) -> list:
    """Detections in capture order; the detection id breaks ties so the order is deterministic."""
    return sorted(detection_ids, key=lambda d: (timestamps[d], _sort_key(d)))


def _consecutive_links(tracks: Mapping[TrackId, list[DetectionId]]) -> set[frozenset]:
    links: set[frozenset] = set()
    for members in tracks.values():
        for first, second in zip(members, members[1:]):
            links.add(frozenset((first, second)))
    return links


def evaluate_tracks(
    ground_truth: Mapping[DetectionId, TrackId],
    predictions: Mapping[DetectionId, TrackId],
    timestamps: Mapping[DetectionId, typing.Any],
) -> TrackingEvaluation:
    """Score predicted tracks against confirmed tracks.

    ``ground_truth`` and ``predictions`` map a detection id to the id of the track it is in;
    ``timestamps`` gives each ground-truth detection a sortable capture time. Only detections
    in ``ground_truth`` are scored. A predicted track is cut down to those detections, so its
    links are between consecutive scored detections; a scored detection missing from
    ``predictions`` counts as a predicted track of its own.
    """
    scored = list(ground_truth)
    missing_times = [d for d in scored if timestamps.get(d) is None]
    if missing_times:
        raise ValueError(f"{len(missing_times)} detection(s) have no timestamp, e.g. {missing_times[:3]}")

    # Private sentinel keys keep an unpredicted detection from sharing a track with anything.
    predicted_track_of = {d: predictions[d] if d in predictions else ("__unpredicted__", d) for d in scored}

    gt_tracks: dict[TrackId, list[DetectionId]] = collections.defaultdict(list)
    pred_tracks: dict[TrackId, list[DetectionId]] = collections.defaultdict(list)
    for d in _time_ordered(scored, timestamps):
        gt_tracks[ground_truth[d]].append(d)
        pred_tracks[predicted_track_of[d]].append(d)

    overlap: collections.Counter = collections.Counter((ground_truth[d], predicted_track_of[d]) for d in scored)
    pred_by_gt: dict[TrackId, collections.Counter] = collections.defaultdict(collections.Counter)
    gt_by_pred: dict[TrackId, collections.Counter] = collections.defaultdict(collections.Counter)
    for (gt_id, pred_id), n in overlap.items():
        pred_by_gt[gt_id][pred_id] = n
        gt_by_pred[pred_id][gt_id] = n

    pairwise_tp = sum(_pairs(n) for n in overlap.values())
    pairwise_pred = sum(_pairs(len(m)) for m in pred_tracks.values())
    pairwise_gt = sum(_pairs(len(m)) for m in gt_tracks.values())
    pairwise_precision = _ratio(pairwise_tp, pairwise_pred)
    pairwise_recall = _ratio(pairwise_tp, pairwise_gt)

    gt_links = _consecutive_links(gt_tracks)
    pred_links = _consecutive_links(pred_tracks)
    links_correct = len(gt_links & pred_links)
    link_precision = _ratio(links_correct, len(pred_links))
    link_recall = _ratio(links_correct, len(gt_links))

    gt_scores = []
    for gt_id in sorted(gt_tracks, key=_sort_key):
        pieces = pred_by_gt[gt_id]
        length = len(gt_tracks[gt_id])
        (largest_pred, largest), *_ = sorted(pieces.items(), key=lambda kv: (-kv[1], _sort_key(kv[0])))
        gt_scores.append(
            GroundTruthTrackScore(
                track_id=gt_id,
                length=length,
                fragments=len(pieces),
                completeness=largest / length,
                exactly_recovered=len(pieces) == 1 and len(gt_by_pred[largest_pred]) == 1,
            )
        )

    pred_scores = []
    for pred_id in sorted(pred_tracks, key=_sort_key):
        spans = gt_by_pred[pred_id]
        length = len(pred_tracks[pred_id])
        pred_scores.append(
            PredictedTrackScore(
                track_id=pred_id,
                length=length,
                ground_truth_tracks=len(spans),
                purity=max(spans.values()) / length,
            )
        )

    return TrackingEvaluation(
        ground_truth_tracks=len(gt_tracks),
        detections=len(scored),
        ground_truth_singletons=sum(1 for m in gt_tracks.values() if len(m) == 1),
        predicted_tracks=len(pred_tracks),
        predicted_singletons=sum(1 for m in pred_tracks.values() if len(m) == 1),
        pairwise_true_positives=pairwise_tp,
        pairwise_predicted=pairwise_pred,
        pairwise_ground_truth=pairwise_gt,
        pairwise_precision=pairwise_precision,
        pairwise_recall=pairwise_recall,
        pairwise_f1=_f1(pairwise_precision, pairwise_recall),
        links_correct=links_correct,
        links_predicted=len(pred_links),
        links_ground_truth=len(gt_links),
        link_precision=link_precision,
        link_recall=link_recall,
        link_f1=_f1(link_precision, link_recall),
        merges=sum(1 for s in pred_scores if s.ground_truth_tracks > 1),
        fragmented_tracks=sum(1 for s in gt_scores if s.fragments > 1),
        exactly_recovered=sum(1 for s in gt_scores if s.exactly_recovered),
        mean_completeness=(sum(s.completeness for s in gt_scores) / len(gt_scores)) if gt_scores else None,
        mean_purity=(sum(s.purity for s in pred_scores) / len(pred_scores)) if pred_scores else None,
        ground_truth_track_scores=gt_scores,
        predicted_track_scores=pred_scores,
    )


def tracks_from_links(
    detection_ids: Iterable[DetectionId], links: Iterable[tuple[DetectionId, DetectionId]]
) -> dict[DetectionId, DetectionId]:
    """Group detections joined by ``(earlier, later)`` links into tracks.

    Returns detection id -> track id, where a track's id is its first detection. Each
    detection has at most one link in and one out, as tracking produces; a detection with no
    links is a track of its own.
    """
    next_of: dict[DetectionId, DetectionId] = {}
    has_previous: set[DetectionId] = set()
    for earlier, later in links:
        if earlier in next_of or later in has_previous:
            raise ValueError(f"Detection linked more than once: {earlier} -> {later}")
        next_of[earlier] = later
        has_previous.add(later)

    track_of: dict[DetectionId, DetectionId] = {}
    all_ids = set(detection_ids) | set(next_of) | has_previous
    for start in sorted(all_ids - has_previous, key=_sort_key):
        current: DetectionId | None = start
        while current is not None and current not in track_of:
            track_of[current] = start
            current = next_of.get(current)
    unreached = all_ids - set(track_of)
    if unreached:
        raise ValueError(f"Links form a cycle through {sorted(unreached, key=_sort_key)[:3]}")
    return track_of


# CSV adapter: the tracks export writes one row per detection, grouped by occurrence.


def _parse_timestamp(value: str) -> datetime.datetime | str:
    try:
        return datetime.datetime.fromisoformat(value)
    except ValueError:
        return value


def read_tracks_csv(path: str) -> list[dict[str, str]]:
    with open(path, newline="") as handle:
        rows = list(csv.DictReader(handle))
    required = {"occurrence_id", "detection_id", "timestamp"}
    if rows and not required <= set(rows[0]):
        raise ValueError(f"{path} is missing columns {sorted(required - set(rows[0]))}")
    return rows


def evaluate_csv_files(ground_truth_path: str, predictions_path: str) -> TrackingEvaluation:
    """Score a predictions CSV against the confirmed tracks in a ground-truth CSV.

    Both files use the tracks export format. Ground truth is every row whose
    ``grouping_verified`` is true, grouped by ``occurrence_id``; predictions are every row of
    the second file, grouped the same way. Capture order comes from ``timestamp``, then
    ``frame_index`` when present.
    """
    ground_truth: dict[str, str] = {}
    timestamps: dict[str, tuple] = {}
    for row in read_tracks_csv(ground_truth_path):
        if row.get("grouping_verified", "").strip().lower() not in TRUE_VALUES:
            continue
        detection_id = row["detection_id"]
        ground_truth[detection_id] = row["occurrence_id"]
        frame_index = row.get("frame_index") or ""
        timestamps[detection_id] = (
            _parse_timestamp(row["timestamp"]),
            int(frame_index) if frame_index.lstrip("-").isdigit() else -1,
        )
    predictions = {row["detection_id"]: row["occurrence_id"] for row in read_tracks_csv(predictions_path)}
    return evaluate_tracks(ground_truth, predictions, timestamps)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Score predicted tracks against confirmed tracks (tracks CSVs).")
    parser.add_argument("--ground-truth", required=True, help="Tracks CSV; rows with grouping_verified=true count.")
    parser.add_argument("--predictions", required=True, help="Tracks CSV of the run to score.")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    parser.add_argument("--per-track", action="store_true", help="Include per-track scores in JSON output.")
    args = parser.parse_args(argv)

    result = evaluate_csv_files(args.ground_truth, args.predictions)
    if args.format == "json":
        json.dump(result.to_dict(include_tracks=args.per_track), sys.stdout, indent=2, default=str)
        sys.stdout.write("\n")
    else:
        sys.stdout.write("\n".join(result.summary_lines()) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
