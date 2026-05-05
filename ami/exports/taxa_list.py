"""Helpers for the `taxa_list_csv` export.

One row per unique taxon that appears as the `determination` of at least one
valid occurrence (after project default filters) in the user-selected
`SourceImageCollection`. The aggregations and column shape are also intended to
cover the data needed for a future Darwin Core Taxon-Core archive variant
(`taxa_list_dwca`) — see the project design doc at
`docs/claude/planning/2026-05-05-taxa-list-export-design.md`.

Time-of-night handling: the typical AMI monitoring window straddles midnight,
so naive midnight-anchored aggregation of clock times misbehaves (the average
of 22:00 and 02:00 is 12:00 noon, not 00:00 midnight). We aggregate in
"seconds since noon" space and convert back. See `noon_shift` /
`noon_unshift` below.
"""

from __future__ import annotations

import dataclasses
import datetime
import math
from collections.abc import Iterable

from ami.main.models import DEFAULT_RANKS, Taxon, TaxonRank

# Linnaean rank columns emitted in the CSV, in this order. Lower-cased so the
# column headers read naturally in a spreadsheet.
HIERARCHY_RANKS: list[TaxonRank] = list(DEFAULT_RANKS)
HIERARCHY_COLUMN_NAMES: list[str] = [r.value.lower() for r in HIERARCHY_RANKS]

SECONDS_PER_DAY = 24 * 60 * 60
NOON_SECONDS = 12 * 60 * 60


def noon_shift(seconds_since_midnight: int) -> int:
    """Map clock seconds-since-midnight into a "noon-anchored" axis where 12:00
    is 0 and the typical nocturnal AMI window (e.g. 18:00 → 06:00) is contiguous.
    """
    return (seconds_since_midnight - NOON_SECONDS + SECONDS_PER_DAY) % SECONDS_PER_DAY


def noon_unshift(noon_anchored_seconds: float) -> int:
    """Inverse of `noon_shift`. Returns clock seconds-since-midnight (0 - 86399)."""
    return int((noon_anchored_seconds + NOON_SECONDS) % SECONDS_PER_DAY)


def time_to_seconds(t: datetime.time) -> int:
    return t.hour * 3600 + t.minute * 60 + t.second


def seconds_to_clock_str(seconds: int | float | None) -> str:
    """Render `HH:MM:SS` from seconds-since-midnight, or empty string for None."""
    if seconds is None:
        return ""
    s = int(round(seconds)) % SECONDS_PER_DAY
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{sec:02d}"


def _median_int(values: list[int]) -> int | None:
    """Median of an integer list, rounded toward 0 for even-length lists.
    Returns None for empty input.
    """
    if not values:
        return None
    s = sorted(values)
    n = len(s)
    mid = n // 2
    if n % 2 == 1:
        return s[mid]
    return (s[mid - 1] + s[mid]) // 2


@dataclasses.dataclass
class TaxonAccumulator:
    """Per-taxon aggregator. Stores one entry per occurrence for the
    `first_appearance_timestamp`-derived "session" stats so we can compute
    medians; running stats elsewhere stay O(1).

    "Session" here means the monitoring session (typically one night) the
    occurrence was observed in. We use `first_appearance_timestamp` as the
    canonical anchor for that session's day-of-year, time-of-night, and month.
    """

    direct_occurrences_count: int = 0

    score_min: float | None = None
    score_max: float | None = None
    score_sum: float = 0.0
    score_count: int = 0  # occurrences with a non-null score

    # Per-occurrence session anchors derived from first_appearance_timestamp.
    # We keep all values to compute medians; min/max/mean are derived from the
    # same lists rather than maintaining parallel running stats.
    session_doys: list[int] = dataclasses.field(default_factory=list)  # 1..366
    session_months: list[int] = dataclasses.field(default_factory=list)  # 1..12
    # Times of night are stored noon-anchored so midnight-spanning windows
    # work for min/max/median.
    session_times_shifted: list[int] = dataclasses.field(default_factory=list)

    # Per-occurrence duration in seconds (last_appearance - first_appearance).
    # Will be more meaningful once detection tracking is wired up; today many
    # occurrences are single-detection and end up with duration 0 / blank.
    duration_min_seconds: float | None = None
    duration_max_seconds: float | None = None
    duration_sum_seconds: float = 0.0
    duration_count: int = 0

    def add(
        self,
        score: float | None,
        first_dt: datetime.datetime | None,
        last_dt: datetime.datetime | None,
    ) -> None:
        self.direct_occurrences_count += 1

        if score is not None and not math.isnan(score):
            self.score_min = score if self.score_min is None else min(self.score_min, score)
            self.score_max = score if self.score_max is None else max(self.score_max, score)
            self.score_sum += score
            self.score_count += 1

        if first_dt is not None:
            self.session_doys.append(first_dt.timetuple().tm_yday)
            self.session_months.append(first_dt.month)
            self.session_times_shifted.append(noon_shift(time_to_seconds(first_dt.time())))

        # Per-occurrence duration. Skipped when either bound is missing OR
        # when there's only one detection (first == last), which would always
        # be 0 and clutter the aggregations.
        if first_dt is not None and last_dt is not None and last_dt > first_dt:
            seconds = (last_dt - first_dt).total_seconds()
            self.duration_min_seconds = (
                seconds if self.duration_min_seconds is None else min(self.duration_min_seconds, seconds)
            )
            self.duration_max_seconds = (
                seconds if self.duration_max_seconds is None else max(self.duration_max_seconds, seconds)
            )
            self.duration_sum_seconds += seconds
            self.duration_count += 1

    @property
    def avg_score(self) -> float | None:
        if self.score_count == 0:
            return None
        return self.score_sum / self.score_count

    # Session-day stats — day of year, 1..366. Min/max are calendar bounds;
    # median is the day-of-year of the typical observation.
    @property
    def session_day_min(self) -> int | None:
        return min(self.session_doys) if self.session_doys else None

    @property
    def session_day_max(self) -> int | None:
        return max(self.session_doys) if self.session_doys else None

    @property
    def session_day_median(self) -> int | None:
        return _median_int(self.session_doys)

    # Session-time stats — clock seconds-since-midnight, midnight-spanning.
    @property
    def session_time_min(self) -> int | None:
        return None if not self.session_times_shifted else noon_unshift(min(self.session_times_shifted))

    @property
    def session_time_max(self) -> int | None:
        return None if not self.session_times_shifted else noon_unshift(max(self.session_times_shifted))

    @property
    def session_time_median(self) -> int | None:
        med = _median_int(self.session_times_shifted)
        return None if med is None else noon_unshift(med)

    # Session-month stats — calendar month, 1..12. Mean is informative for
    # phenology bucketing (e.g. "mostly mid-July").
    @property
    def session_month_min(self) -> int | None:
        return min(self.session_months) if self.session_months else None

    @property
    def session_month_max(self) -> int | None:
        return max(self.session_months) if self.session_months else None

    @property
    def session_month_mean(self) -> float | None:
        if not self.session_months:
            return None
        return sum(self.session_months) / len(self.session_months)

    @property
    def duration_avg_seconds(self) -> float | None:
        if self.duration_count == 0:
            return None
        return self.duration_sum_seconds / self.duration_count


def hierarchy_columns_from_parents_json(taxon: Taxon) -> dict[str, str]:
    """Extract one column per Linnaean rank from `parents_json`, plus the
    taxon's own name on its own rank. Returns lowercase rank → name string;
    missing ranks map to empty strings.
    """
    out: dict[str, str] = {col: "" for col in HIERARCHY_COLUMN_NAMES}
    parents = list(getattr(taxon, "parents_json", None) or [])
    for parent in parents:
        # parent is a TaxonParent pydantic model with .rank (TaxonRank enum)
        rank = getattr(parent, "rank", None)
        if rank is None:
            continue
        rank_value = rank.value if hasattr(rank, "value") else str(rank)
        col = rank_value.lower()
        if col in out:
            out[col] = parent.name
    own_rank = getattr(taxon, "rank", None)
    if own_rank:
        col = str(own_rank).lower()
        if col in out:
            out[col] = taxon.name
    return out


# External link templates. Empty string when the underlying ID is missing.
def gbif_url(key: int | None) -> str:
    return f"https://www.gbif.org/species/{key}" if key else ""


def inat_url(taxon_id: int | None) -> str:
    return f"https://www.inaturalist.org/taxa/{taxon_id}" if taxon_id else ""


def bold_url(bin_id: str | None) -> str:
    if not bin_id:
        return ""
    # BOLD's BIN viewer URL pattern.
    return (
        "https://www.boldsystems.org/index.php/Public_BarcodeIndexNumber_RecordView"
        f"?searchtype=records&recordID={bin_id}"
    )


def fieldguide_url(fg_id: str | None) -> str:
    return f"https://fieldguide.app/taxa/{fg_id}" if fg_id else ""


# Column order. Keep this in sync with `row_for_taxon` below.
COLUMN_ORDER: list[str] = [
    "id",
    "name",
    "display_name",
    "rank",
    "common_name_en",
    *HIERARCHY_COLUMN_NAMES,
    "direct_occurrences_count",
    "min_score",
    "max_score",
    "avg_score",
    "session_day_min",
    "session_day_max",
    "session_day_median",
    "session_time_min",
    "session_time_max",
    "session_time_median",
    "session_month_min",
    "session_month_max",
    "session_month_mean",
    "min_duration_seconds",
    "max_duration_seconds",
    "avg_duration_seconds",
    "gbif_taxon_key",
    "gbif_url",
    "inat_taxon_id",
    "inat_url",
    "bold_taxon_bin",
    "bold_url",
    "fieldguide_id",
    "fieldguide_url",
    "cover_image_url",
]


def _format_score(value: float | None) -> str:
    return "" if value is None else f"{value:.4f}"


def _format_seconds(value: float | None) -> str:
    """Render duration seconds. Empty for None; otherwise rounded to int."""
    if value is None:
        return ""
    return str(int(round(value)))


def _format_int(value: int | None) -> str:
    return "" if value is None else str(value)


def _format_float_1dp(value: float | None) -> str:
    return "" if value is None else f"{value:.1f}"


def row_for_taxon(taxon: Taxon, accum: TaxonAccumulator) -> dict[str, str]:
    """Build a single CSV row dict for a taxon + its accumulator."""
    hierarchy = hierarchy_columns_from_parents_json(taxon)
    row: dict[str, str] = {
        "id": str(taxon.pk),
        "name": taxon.name or "",
        "display_name": taxon.display_name or "",
        "rank": str(taxon.rank or ""),
        "common_name_en": taxon.common_name_en or "",
        **hierarchy,
        "direct_occurrences_count": str(accum.direct_occurrences_count),
        "min_score": _format_score(accum.score_min),
        "max_score": _format_score(accum.score_max),
        "avg_score": _format_score(accum.avg_score),
        "session_day_min": _format_int(accum.session_day_min),
        "session_day_max": _format_int(accum.session_day_max),
        "session_day_median": _format_int(accum.session_day_median),
        "session_time_min": seconds_to_clock_str(accum.session_time_min),
        "session_time_max": seconds_to_clock_str(accum.session_time_max),
        "session_time_median": seconds_to_clock_str(accum.session_time_median),
        "session_month_min": _format_int(accum.session_month_min),
        "session_month_max": _format_int(accum.session_month_max),
        "session_month_mean": _format_float_1dp(accum.session_month_mean),
        "min_duration_seconds": _format_seconds(accum.duration_min_seconds),
        "max_duration_seconds": _format_seconds(accum.duration_max_seconds),
        "avg_duration_seconds": _format_seconds(accum.duration_avg_seconds),
        "gbif_taxon_key": str(taxon.gbif_taxon_key) if taxon.gbif_taxon_key else "",
        "gbif_url": gbif_url(taxon.gbif_taxon_key),
        "inat_taxon_id": str(taxon.inat_taxon_id) if taxon.inat_taxon_id else "",
        "inat_url": inat_url(taxon.inat_taxon_id),
        "bold_taxon_bin": taxon.bold_taxon_bin or "",
        "bold_url": bold_url(taxon.bold_taxon_bin),
        "fieldguide_id": taxon.fieldguide_id or "",
        "fieldguide_url": fieldguide_url(taxon.fieldguide_id),
        "cover_image_url": taxon.cover_image_url or "",
    }
    return row


def empty_row_for_taxon(taxon: Taxon) -> dict[str, str]:
    """Row for a taxon expected to be in the project's taxonomic scope but not
    observed in the selected collection. All aggregation columns blank;
    `direct_occurrences_count = 0`. Currently unused — see
    `TaxaListCSVExporter._get_expected_taxa`.
    """
    return row_for_taxon(taxon, TaxonAccumulator())


def iter_observed_taxa(taxa: Iterable[Taxon], accumulators: dict[int, TaxonAccumulator]):
    """Yield (taxon, accumulator) pairs for taxa that appear in the
    accumulator dict. Caller controls ordering via the `taxa` iterable.
    """
    for taxon in taxa:
        accum = accumulators.get(taxon.pk)
        if accum is None:
            continue
        yield taxon, accum
