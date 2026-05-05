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


@dataclasses.dataclass
class TaxonAccumulator:
    """Streaming per-taxon aggregator. Memory: O(1) per taxon."""

    direct_occurrences_count: int = 0

    score_min: float | None = None
    score_max: float | None = None
    score_sum: float = 0.0
    score_count: int = 0  # occurrences with a non-null score

    first_dt_min: datetime.datetime | None = None
    first_dt_max: datetime.datetime | None = None
    first_dt_epoch_sum: float = 0.0
    first_dt_count: int = 0  # occurrences with a non-null first_appearance_timestamp

    # Time-of-night aggregations are stored in noon-anchored seconds (see
    # noon_shift) so they survive midnight wraparound.
    time_min_shifted: int | None = None
    time_max_shifted: int | None = None
    time_sum_shifted: int = 0
    time_count: int = 0

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

        # We use the OCCURRENCE's first_appearance_timestamp as the canonical
        # "when this taxon was seen on this occasion" anchor for date and
        # time-of-night stats. The last_dt is used only to widen the date
        # range so the displayed [first_date, last_date] window covers all
        # appearances.
        if first_dt is not None:
            self.first_dt_min = first_dt if self.first_dt_min is None else min(self.first_dt_min, first_dt)
            epoch = first_dt.timestamp()
            self.first_dt_epoch_sum += epoch
            self.first_dt_count += 1

            shifted = noon_shift(time_to_seconds(first_dt.time()))
            self.time_min_shifted = shifted if self.time_min_shifted is None else min(self.time_min_shifted, shifted)
            self.time_max_shifted = shifted if self.time_max_shifted is None else max(self.time_max_shifted, shifted)
            self.time_sum_shifted += shifted
            self.time_count += 1

        # Widen the [min, max] datetime window with last_dt as well.
        widening = last_dt or first_dt
        if widening is not None:
            self.first_dt_max = widening if self.first_dt_max is None else max(self.first_dt_max, widening)

    @property
    def avg_score(self) -> float | None:
        if self.score_count == 0:
            return None
        return self.score_sum / self.score_count

    @property
    def avg_first_dt(self) -> datetime.datetime | None:
        if self.first_dt_count == 0:
            return None
        return datetime.datetime.fromtimestamp(self.first_dt_epoch_sum / self.first_dt_count)

    @property
    def time_min_clock(self) -> int | None:
        return None if self.time_min_shifted is None else noon_unshift(self.time_min_shifted)

    @property
    def time_max_clock(self) -> int | None:
        return None if self.time_max_shifted is None else noon_unshift(self.time_max_shifted)

    @property
    def time_avg_clock(self) -> int | None:
        if self.time_count == 0:
            return None
        return noon_unshift(self.time_sum_shifted / self.time_count)


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
    "first_occurrence_date",
    "last_occurrence_date",
    "avg_occurrence_date",
    "min_time_of_night",
    "max_time_of_night",
    "avg_time_of_night",
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


def _format_date(value: datetime.datetime | datetime.date | None) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime.datetime):
        value = value.date()
    return value.isoformat()


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
        "first_occurrence_date": _format_date(accum.first_dt_min),
        "last_occurrence_date": _format_date(accum.first_dt_max),
        "avg_occurrence_date": _format_date(accum.avg_first_dt),
        "min_time_of_night": seconds_to_clock_str(accum.time_min_clock),
        "max_time_of_night": seconds_to_clock_str(accum.time_max_clock),
        "avg_time_of_night": seconds_to_clock_str(accum.time_avg_clock),
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
