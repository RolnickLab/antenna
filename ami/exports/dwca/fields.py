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


def _humboldt_effort_value(event) -> str:
    """Sampling effort value: prefer image count, fall back to nothing."""
    count = getattr(event, "captures_count", None) or 0
    return str(count) if count else ""


def _associated_media(occurrence) -> str:
    """Pipe-separated distinct public URLs of source captures for this occurrence.

    Ordered by detection timestamp; timestamp-less detections sort last. Uses
    prefetched detections + source_image; the exporter ensures the prefetch
    chain so this stays O(N) at write time.
    """
    import datetime as _dt

    seen: set[str] = set()
    urls: list[str] = []
    _far_future = _dt.datetime.max

    def _sort_key(d):
        ts = d.timestamp or (d.source_image.timestamp if d.source_image else None)
        return ts or _far_future

    detections = sorted(occurrence.detections.all(), key=_sort_key)
    for det in detections:
        si = det.source_image
        if si is None:
            continue
        url = si.public_url()
        if not url or url in seen:
            continue
        seen.add(url)
        urls.append(url)
    return "|".join(urls)


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
    # ── Humboldt Extension (eco:) terms flattened onto event.txt ──
    DwCAField(
        ECO + "isSamplingEffortReported",
        "isSamplingEffortReported",
        lambda e, slug: "true",
    ),
    DwCAField(
        ECO + "samplingEffortValue",
        "samplingEffortValue",
        lambda e, slug: _humboldt_effort_value(e),
    ),
    DwCAField(
        ECO + "samplingEffortUnit",
        "samplingEffortUnit",
        lambda e, slug: "images",
    ),
    DwCAField(
        ECO + "samplingEffortProtocol",
        "samplingEffortProtocol",
        lambda e, slug: (
            "automated camera trap with light attractant; continuous overnight monitoring "
            "with fixed image-capture interval; images processed by ML detector + classifier pipeline"
        ),
    ),
    DwCAField(
        ECO + "isAbsenceReported",
        "isAbsenceReported",
        lambda e, slug: "true",
    ),
    DwCAField(
        ECO + "targetTaxonomicScope",
        "targetTaxonomicScope",
        lambda e, slug: getattr(e, "_target_taxonomic_scope", "") or "",
    ),
    DwCAField(
        ECO + "inventoryTypes",
        "inventoryTypes",
        lambda e, slug: "trap or sample",
    ),
    DwCAField(
        ECO + "protocolNames",
        "protocolNames",
        lambda e, slug: "AMI ML detector + classifier pipeline",
    ),
    DwCAField(
        ECO + "protocolDescriptions",
        "protocolDescriptions",
        lambda e, slug: (
            "Images captured at a fixed interval by an automated monitoring station; each image "
            "processed through a detector (bounding-box extraction) and classifier (species "
            "prediction). Occurrences grouped from co-located detections; default filters applied."
        ),
    ),
    DwCAField(
        ECO + "hasMaterialSamples",
        "hasMaterialSamples",
        lambda e, slug: "true",
    ),
    DwCAField(
        ECO + "materialSampleTypes",
        "materialSampleTypes",
        lambda e, slug: "digital images",
    ),
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
    DwCAField(
        DWC + "associatedMedia",
        "associatedMedia",
        lambda o, slug: _associated_media(o),
    ),
]


MULTIMEDIA_FIELDS: list[DwCAField] = [
    DwCAField(DWC + "eventID", "eventID", lambda r, slug: r["eventID"], required=True),
    DwCAField(DWC + "occurrenceID", "occurrenceID", lambda r, slug: r.get("occurrenceID", "")),
    DwCAField(DC + "type", "type", lambda r, slug: r.get("type", "StillImage")),
    DwCAField(DC + "format", "format", lambda r, slug: r.get("format", "image/jpeg")),
    DwCAField(DC + "identifier", "identifier", lambda r, slug: r["identifier"], required=True),
    DwCAField(DC + "references", "references", lambda r, slug: r.get("references", "")),
    DwCAField(DC + "created", "created", lambda r, slug: r.get("created", "")),
    DwCAField(DC + "license", "license", lambda r, slug: r.get("license", "")),
    DwCAField(DC + "rightsHolder", "rightsHolder", lambda r, slug: r.get("rightsHolder", "")),
    DwCAField(DC + "creator", "creator", lambda r, slug: r.get("creator", "")),
    DwCAField(DC + "description", "description", lambda r, slug: r.get("description", "")),
]
