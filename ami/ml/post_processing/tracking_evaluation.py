"""Score a tracking run against tracks a person has confirmed.

Ground truth is the set of occurrences whose grouping a person confirmed: each one is taken
to be a complete and accurate track. Nothing is known about detections outside those tracks,
so every metric here is computed only over the detections that belong to a confirmed track.
In particular, a predicted detection outside every confirmed track is never an identity false
positive, which makes ID precision, ID recall and IDF1 the same number here.

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

# Share of a confirmed track's detections held by one predicted track, at or above which it is
# mostly tracked, and below which it is mostly lost; in between it is partly tracked.
MOSTLY_TRACKED = 0.8
MOSTLY_LOST = 0.2

REPORT_NOTES = [
    "Headline: IDF1, the share of confirmed detections whose predicted track is the one matched "
    "one-to-one to their confirmed track. Predicted detections outside confirmed tracks are not counted "
    "as errors, because the confirmed tracks are only part of the session.",
    "Weighting: IDF1 and link scores count each detection or link once, so long tracks weigh more; "
    "pairwise scores grow with the square of track length; track counts and means count each "
    "confirmed track once.",
]


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
    # How many times the predicted track changes between consecutive detections, in time order.
    id_switches: int


@dataclasses.dataclass
class PredictedTrackScore:
    """One predicted track that holds at least one detection from a confirmed track.

    ``length`` counts only its detections in confirmed tracks. ``purity`` is the share of
    those held by the confirmed track it overlaps most; ``ground_truth_tracks`` above 1 is
    a merge of different insects. ``first_detection_id`` is its earliest detection among
    those, a detection id rather than a track id, so it cannot be confused with the
    occurrence ids that name confirmed tracks.
    """

    first_detection_id: DetectionId
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

    # The headline score, IDF1 (Ristani et al. 2016), from a one-to-one matching of confirmed
    # and predicted tracks that keeps as many detections as possible in their matched track.
    idf1: float | None
    id_true_positives: int
    id_switches: int
    mostly_tracked: int
    partly_tracked: int
    mostly_lost: int

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
            f"IDF1 {fmt(self.idf1)}  ({self.id_true_positives}/{self.detections} detections in their "
            f"matched predicted track)",
            f"Mostly tracked {self.mostly_tracked}  partly tracked {self.partly_tracked}  "
            f"mostly lost {self.mostly_lost}  ID switches {self.id_switches}",
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


def _best_assignment_total(weights: list[list[int]]) -> int:
    """The largest total weight of a one-to-one matching of rows to columns (Hungarian method).

    scipy's ``linear_sum_assignment`` does this, but scipy is not a dependency of this module.
    """
    infinity = float("inf")
    if len(weights) > len(weights[0]):
        weights = [list(column) for column in zip(*weights)]
    rows, columns = len(weights), len(weights[0])
    # Potentials and matches are 1-indexed; column 0 is a free slot the method starts from.
    row_potential = [0] * (rows + 1)
    column_potential = [0] * (columns + 1)
    row_of_column = [0] * (columns + 1)
    previous_column = [0] * (columns + 1)
    for row in range(1, rows + 1):
        row_of_column[0] = row
        column = 0
        slack = [infinity] * (columns + 1)
        used = [False] * (columns + 1)
        while row_of_column[column]:
            used[column] = True
            current_row, delta, next_column = row_of_column[column], infinity, 0
            for j in range(1, columns + 1):
                if used[j]:
                    continue
                cost = -weights[current_row - 1][j - 1] - row_potential[current_row] - column_potential[j]
                if cost < slack[j]:
                    slack[j], previous_column[j] = cost, column
                if slack[j] < delta:
                    delta, next_column = slack[j], j
            for j in range(columns + 1):
                if used[j]:
                    row_potential[row_of_column[j]] += delta
                    column_potential[j] -= delta
                else:
                    slack[j] -= delta
            column = next_column
        while column:
            row_of_column[column] = row_of_column[previous_column[column]]
            column = previous_column[column]
    return sum(weights[row_of_column[j] - 1][j - 1] for j in range(1, columns + 1) if row_of_column[j])


def _identity_true_positives(overlap: Mapping[tuple[TrackId, TrackId], int]) -> int:
    """Detections kept in their track by the best one-to-one matching of confirmed to predicted tracks.

    The matching is solved separately for each group of tracks connected by shared detections,
    which keeps every matrix small.
    """
    parent: dict[tuple, tuple] = {}

    def root(node: tuple) -> tuple:
        while parent.setdefault(node, node) != node:
            node = parent[node]
        return node

    for gt_id, pred_id in overlap:
        parent[root(("gt", gt_id))] = root(("pred", pred_id))
    groups: dict[tuple, list[tuple[TrackId, TrackId]]] = collections.defaultdict(list)
    for key in overlap:
        groups[root(("gt", key[0]))].append(key)

    total = 0
    for keys in groups.values():
        gt_ids = sorted({gt_id for gt_id, _ in keys}, key=_sort_key)
        pred_ids = sorted({pred_id for _, pred_id in keys}, key=_sort_key)
        total += _best_assignment_total([[overlap.get((g, p), 0) for p in pred_ids] for g in gt_ids])
    return total


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

    id_true_positives = _identity_true_positives(overlap)

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
                id_switches=sum(
                    predicted_track_of[a] != predicted_track_of[b]
                    for a, b in zip(gt_tracks[gt_id], gt_tracks[gt_id][1:])
                ),
            )
        )

    pred_scores = []
    # Listed in the order of the ids they are reported under.
    for pred_id in sorted(pred_tracks, key=lambda p: _sort_key(pred_tracks[p][0])):
        spans = gt_by_pred[pred_id]
        length = len(pred_tracks[pred_id])
        pred_scores.append(
            PredictedTrackScore(
                first_detection_id=pred_tracks[pred_id][0],
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
        idf1=_ratio(id_true_positives, len(scored)),
        id_true_positives=id_true_positives,
        id_switches=sum(s.id_switches for s in gt_scores),
        mostly_tracked=sum(1 for s in gt_scores if s.completeness >= MOSTLY_TRACKED),
        partly_tracked=sum(1 for s in gt_scores if MOSTLY_LOST <= s.completeness < MOSTLY_TRACKED),
        mostly_lost=sum(1 for s in gt_scores if s.completeness < MOSTLY_LOST),
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


def _parse_timestamps(raw: Mapping[str, str]) -> dict[str, datetime.datetime]:
    """Parse ISO capture times, raising ValueError for blank, unreadable or mixed-zone values.

    Every value must parse, and all must be timezone-aware or all naive, because Python
    cannot order a mix of datetimes and strings, or of naive and aware datetimes.
    """
    parsed: dict[str, datetime.datetime] = {}
    blank: list[str] = []
    unreadable: list[str] = []
    for detection_id, value in raw.items():
        value = (value or "").strip()
        if not value:
            blank.append(detection_id)
            continue
        try:
            parsed[detection_id] = datetime.datetime.fromisoformat(value)
        except ValueError:
            unreadable.append(detection_id)
    if blank:
        raise ValueError(f"{len(blank)} confirmed detection(s) have no timestamp, e.g. detection_id {blank[:3]}")
    if unreadable:
        raise ValueError(
            f"{len(unreadable)} confirmed detection(s) have a timestamp that is not ISO 8601, "
            f"e.g. detection_id {unreadable[:3]}"
        )
    aware = {detection_id for detection_id, value in parsed.items() if value.utcoffset() is not None}
    if aware and len(aware) < len(parsed):
        naive = sorted(set(parsed) - aware)
        raise ValueError(
            "Timestamps mix timezone-aware and naive values; "
            f"e.g. aware detection_id {sorted(aware)[:3]}, naive detection_id {naive[:3]}"
        )
    return parsed


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
    raw_times: dict[str, str] = {}
    frame_indexes: dict[str, int] = {}
    for row in read_tracks_csv(ground_truth_path):
        if (row.get("grouping_verified") or "").strip().lower() not in TRUE_VALUES:
            continue
        detection_id = row["detection_id"]
        ground_truth[detection_id] = row["occurrence_id"]
        raw_times[detection_id] = row["timestamp"]
        frame_index = (row.get("frame_index") or "").strip()
        frame_indexes[detection_id] = int(frame_index) if frame_index.lstrip("-").isdigit() else -1
    timestamps = {
        detection_id: (parsed, frame_indexes[detection_id])
        for detection_id, parsed in _parse_timestamps(raw_times).items()
    }
    predictions = {row["detection_id"]: row["occurrence_id"] for row in read_tracks_csv(predictions_path)}
    return evaluate_tracks(ground_truth, predictions, timestamps)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Score predicted tracks against confirmed tracks (tracks CSVs).")
    parser.add_argument("--ground-truth", required=True, help="Tracks CSV; rows with grouping_verified=true count.")
    parser.add_argument("--predictions", required=True, help="Tracks CSV of the run to score.")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    parser.add_argument("--per-track", action="store_true", help="Include per-track scores in JSON output.")
    args = parser.parse_args(argv)

    try:
        result = evaluate_csv_files(args.ground_truth, args.predictions)
    except (OSError, ValueError) as error:
        parser.exit(2, f"error: {error}\n")
    if args.format == "json":
        json.dump(result.to_dict(include_tracks=args.per_track), sys.stdout, indent=2, default=str)
        sys.stdout.write("\n")
    else:
        sys.stdout.write("\n".join(REPORT_NOTES + result.summary_lines()) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
