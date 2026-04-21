"""DwC-A column catalogues.

Each DwCAField ties a term URI, a TSV header, and a row extractor together so
meta.xml cannot drift from the TSV. Catalogues here: EVENT_FIELDS,
OCCURRENCE_FIELDS. Additional catalogues (multimedia, MoF) live beside them and
are added in later PRs.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from ami.exports.dwca.helpers import (
    _format_coord,
    _format_datetime,
    _format_duration,
    _format_event_date,
    _format_time,
    _get_rank_from_parents,
    _get_verification_status,
    get_specific_epithet,
)

DWC = "http://rs.tdwg.org/dwc/terms/"
DC = "http://purl.org/dc/terms/"
ECO = "http://rs.tdwg.org/eco/terms/"


@dataclass(frozen=True)
class DwCAField:
    """A single column mapping in a DwC-A text file.

    Ties together the Darwin Core term URI (written to meta.xml), the
    TSV header, and the extractor that produces the cell value from a
    model instance. Consolidating all three here makes the field the
    unit of test and review, and lets meta.xml be derived from the
    same list instead of reconstructed in parallel.
    """

    term: str
    header: str
    extract: Callable[[Any, str], str]
    required: bool = False  # GBIF acceptance bar; informational today, validated later.


EVENT_FIELDS: list[DwCAField] = [
    DwCAField(DWC + "eventID", "eventID", lambda e, slug: f"urn:ami:event:{slug}:{e.id}", required=True),
    DwCAField(DWC + "eventDate", "eventDate", lambda e, slug: _format_event_date(e), required=True),
    DwCAField(DWC + "eventTime", "eventTime", lambda e, slug: _format_time(e.start)),
    DwCAField(DWC + "year", "year", lambda e, slug: str(e.start.year) if e.start else ""),
    DwCAField(DWC + "month", "month", lambda e, slug: str(e.start.month) if e.start else ""),
    DwCAField(DWC + "day", "day", lambda e, slug: str(e.start.day) if e.start else ""),
    DwCAField(DWC + "samplingProtocol", "samplingProtocol", lambda e, slug: "automated light trap with camera"),
    DwCAField(DWC + "sampleSizeValue", "sampleSizeValue", lambda e, slug: str(e.captures_count or 0)),
    DwCAField(DWC + "sampleSizeUnit", "sampleSizeUnit", lambda e, slug: "images"),
    DwCAField(DWC + "samplingEffort", "samplingEffort", lambda e, slug: _format_duration(e)),
    DwCAField(DWC + "locationID", "locationID", lambda e, slug: e.deployment.name if e.deployment else ""),
    DwCAField(
        DWC + "decimalLatitude",
        "decimalLatitude",
        lambda e, slug: _format_coord(e.deployment.latitude if e.deployment else None),
        required=True,
    ),
    DwCAField(
        DWC + "decimalLongitude",
        "decimalLongitude",
        lambda e, slug: _format_coord(e.deployment.longitude if e.deployment else None),
        required=True,
    ),
    DwCAField(DWC + "geodeticDatum", "geodeticDatum", lambda e, slug: "WGS84"),
    DwCAField(DWC + "datasetName", "datasetName", lambda e, slug: e.project.name if e.project else ""),
    DwCAField(DC + "license", "license", lambda e, slug: (e.project.license if e.project else "") or ""),
    DwCAField(
        DC + "rightsHolder", "rightsHolder", lambda e, slug: (e.project.rights_holder if e.project else "") or ""
    ),
    DwCAField(DC + "modified", "modified", lambda e, slug: _format_datetime(e.updated_at)),
]


OCCURRENCE_FIELDS: list[DwCAField] = [
    DwCAField(
        DWC + "eventID",
        "eventID",
        lambda o, slug: f"urn:ami:event:{slug}:{o.event_id}" if o.event_id else "",
        required=True,
    ),
    DwCAField(
        DWC + "occurrenceID", "occurrenceID", lambda o, slug: f"urn:ami:occurrence:{slug}:{o.id}", required=True
    ),
    DwCAField(DWC + "basisOfRecord", "basisOfRecord", lambda o, slug: "MachineObservation", required=True),
    DwCAField(DWC + "occurrenceStatus", "occurrenceStatus", lambda o, slug: "present"),
    DwCAField(
        DWC + "scientificName",
        "scientificName",
        lambda o, slug: o.determination.name if o.determination else "",
        required=True,
    ),
    DwCAField(
        DWC + "taxonRank",
        "taxonRank",
        lambda o, slug: (o.determination.rank.lower() if o.determination and o.determination.rank else ""),
    ),
    DwCAField(DWC + "kingdom", "kingdom", lambda o, slug: _get_rank_from_parents(o, "KINGDOM")),
    DwCAField(DWC + "phylum", "phylum", lambda o, slug: _get_rank_from_parents(o, "PHYLUM")),
    DwCAField(DWC + "class", "class", lambda o, slug: _get_rank_from_parents(o, "CLASS")),
    DwCAField(DWC + "order", "order", lambda o, slug: _get_rank_from_parents(o, "ORDER")),
    DwCAField(DWC + "family", "family", lambda o, slug: _get_rank_from_parents(o, "FAMILY")),
    DwCAField(DWC + "genus", "genus", lambda o, slug: _get_rank_from_parents(o, "GENUS")),
    DwCAField(
        DWC + "specificEpithet",
        "specificEpithet",
        lambda o, slug: get_specific_epithet(o.determination.name if o.determination else ""),
    ),
    DwCAField(
        DWC + "vernacularName",
        "vernacularName",
        lambda o, slug: (o.determination.common_name_en or "") if o.determination else "",
    ),
    DwCAField(
        DWC + "taxonID",
        "taxonID",
        lambda o, slug: (
            str(o.determination.gbif_taxon_key) if o.determination and o.determination.gbif_taxon_key else ""
        ),
    ),
    DwCAField(DWC + "individualCount", "individualCount", lambda o, slug: "1"),
    DwCAField(DWC + "identifiedBy", "identifiedBy", lambda o, slug: o.get_identified_by()),
    DwCAField(
        DWC + "dateIdentified",
        "dateIdentified",
        lambda o, slug: _format_datetime(o.get_identified_date()),
    ),
    DwCAField(
        DWC + "identificationVerificationStatus",
        "identificationVerificationStatus",
        lambda o, slug: _get_verification_status(o),
    ),
    DwCAField(DC + "modified", "modified", lambda o, slug: _format_datetime(o.updated_at)),
]
