"""What a tracking run records about each occurrence it changed."""

import typing

import pydantic

from ami.ml.results.schemas import DeterminationSnapshot


class TaxonLabelCount(pydantic.BaseModel):
    """One taxon named by the machine labels of an occurrence's detections, as it was when the run recorded it."""

    taxon_id: int
    # A copy of the taxon's name, kept so the record still reads after the taxon is renamed, merged or deleted.
    name: str
    # Detections whose label names the taxon, and the mean and best score of those labels.
    detection_count: int
    score_mean: float | None = None
    score_max: float | None = None

    class Config:
        extra = "forbid"


class TrackingResultData(DeterminationSnapshot):
    """Figures from the detections the run linked into the occurrence, in capture order."""

    kind: typing.ClassVar[str] = "tracking"
    value_field: typing.ClassVar[str | None] = "motion"

    detection_count: int
    # Mean distance per step between consecutive detection centres, as a fraction of the image diagonal;
    # 0 for one detection.
    motion: float
    # The same distances added up over the whole path, as a fraction of the image diagonal.
    path_length: float
    # The largest box area over the smallest (at least 1), with areas floored at 1; 1 when the box never changed size.
    size_change: float
    # Distinct taxa among the detections' labels at the time of the run. Each detection's label is its best
    # classification, chosen as the determination chooses (terminal first, then the highest score).
    distinct_taxa: int
    # The share of detections whose label names the determination after the run; None when none has a label.
    label_agreement: float | None = None
    # Each of those distinct taxa, most detections first.
    taxa: list[TaxonLabelCount] = []
    # Seconds from the first capture to the last; None when fewer than two have a time.
    duration_seconds: float | None = None
    # The lowest, mean and highest score of the detections' labels; None when no label has a score.
    score_min: float | None = None
    score_mean: float | None = None
    score_max: float | None = None
    # One entry per detection in ``detection_ids``: the matching cost, rounded to 4 places, of the link this
    # run made from it, or None when its link is older or it is the last. See #1412 for the planned shape.
    link_costs: list[float | None] = []
    # Occurrences the run folded into this one. They are deleted, so these are plain ids, not references.
    merged_occurrence_ids: list[int] = []
    # The grouping before the run, so a reset can restore it: the occurrence's detections in capture order,
    # the occurrence each one was in, each identification moved here as (identification, earlier occurrence),
    # and the identifications withdrawn because their user had another active one on a merged occurrence.
    detection_ids: list[int] = []
    previous_occurrence_ids: list[int | None] = []
    moved_identifications: list[tuple[int, int]] = []
    withdrawn_identification_ids: list[int] = []
