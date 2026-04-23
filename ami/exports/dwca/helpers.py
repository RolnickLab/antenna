"""Small pure helpers used by DwC-A field extractors."""

from __future__ import annotations

import datetime
import logging

logger = logging.getLogger(__name__)


def _format_event_date(event) -> str:
    """Format event date as ISO date or date interval."""
    if not event.start:
        return ""
    start_date = event.start.date().isoformat()
    if event.end and event.end.date() != event.start.date():
        return f"{start_date}/{event.end.date().isoformat()}"
    return start_date


def _format_time(dt) -> str:
    if not dt:
        return ""
    return dt.strftime("%H:%M:%S")


def _format_datetime(dt) -> str:
    if not dt:
        return ""
    if isinstance(dt, datetime.datetime):
        return dt.isoformat()
    return str(dt)


def _format_coord(value) -> str:
    if value is None:
        return ""
    return str(round(value, 6))


def _format_duration(event) -> str:
    """Format event duration as human-readable string."""
    if not event.start or not event.end:
        return ""
    delta = event.end - event.start
    total_seconds = int(delta.total_seconds())
    if total_seconds < 0:
        return ""
    hours, remainder = divmod(total_seconds, 3600)
    minutes, _ = divmod(remainder, 60)
    if hours > 0:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"


def _get_rank_from_parents(occurrence, rank: str) -> str:
    """Extract a taxon name at a specific rank from determination.parents_json."""
    if not occurrence.determination:
        return ""
    parents = occurrence.determination.parents_json
    if not parents:
        return ""
    for parent in parents:
        # parents_json contains TaxonParent objects (or dicts with id, name, rank)
        parent_rank = parent.rank if hasattr(parent, "rank") else parent.get("rank", "")
        # TaxonRank enum values are uppercase strings
        parent_rank_str = parent_rank.name if hasattr(parent_rank, "name") else str(parent_rank)
        if parent_rank_str.upper() == rank:
            return parent.name if hasattr(parent, "name") else parent.get("name", "")
    # Also check the determination itself if it matches the requested rank
    det_rank = occurrence.determination.rank
    if det_rank and det_rank.upper() == rank:
        return occurrence.determination.name
    return ""


def get_specific_epithet(name: str) -> str:
    """Extract the specific epithet (second word) from a binomial name."""
    parts = name.split()
    if len(parts) >= 2:
        return parts[1]
    return ""


def _get_verification_status(occurrence) -> str:
    """Return "verified" when a non-withdrawn human Identification exists, else "unverified"."""
    if hasattr(occurrence, "_prefetched_objects_cache") and "identifications" in occurrence._prefetched_objects_cache:
        return "verified" if any(not i.withdrawn for i in occurrence.identifications.all()) else "unverified"
    return "verified" if occurrence.identifications.filter(withdrawn=False).exists() else "unverified"
