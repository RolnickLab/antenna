"""
Darwin Core Archive (DwC-A) field mappings, metadata generators, and taxonomy helpers.

Implements Event Core architecture with Occurrence Extension for GBIF-compatible archives.
"""

import csv
import datetime
import logging
import tempfile
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from xml.etree import ElementTree as ET

from django.utils.text import slugify

logger = logging.getLogger(__name__)

# DwC term URI base
DWC = "http://rs.tdwg.org/dwc/terms/"
DC = "http://purl.org/dc/terms/"


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


# ──────────────────────────────────────────────────────────────
# Event field definitions
# ──────────────────────────────────────────────────────────────

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

# ──────────────────────────────────────────────────────────────
# Occurrence field definitions
# ──────────────────────────────────────────────────────────────

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


# ──────────────────────────────────────────────────────────────
# Helper functions
# ──────────────────────────────────────────────────────────────


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
    """Return verification status based on whether identifications exist."""
    # Use prefetched identifications if available
    if hasattr(occurrence, "_prefetched_objects_cache") and "identifications" in occurrence._prefetched_objects_cache:
        return "verified" if occurrence.identifications.all() else "unverified"
    # Fall back to exists() check
    return "verified" if occurrence.identifications.exists() else "unverified"


# ──────────────────────────────────────────────────────────────
# TSV writing
# ──────────────────────────────────────────────────────────────


def write_tsv(
    filepath: str,
    fields: list[DwCAField],
    queryset,
    project_slug: str,
    progress_callback=None,
):
    """Write a tab-delimited file from a queryset using field definitions.

    Returns the number of records written.
    """
    headers = [f.header for f in fields]
    records_written = 0

    with open(filepath, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter="\t", quoting=csv.QUOTE_MINIMAL, lineterminator="\n")
        writer.writerow(headers)

        for obj in queryset.iterator(chunk_size=500):
            row = [field.extract(obj, project_slug) for field in fields]
            writer.writerow(row)
            records_written += 1
            if progress_callback and records_written % 500 == 0:
                progress_callback(records_written)

    return records_written


# ──────────────────────────────────────────────────────────────
# meta.xml generation
# ──────────────────────────────────────────────────────────────


def generate_meta_xml(
    event_fields: list[DwCAField],
    occurrence_fields: list[DwCAField],
    event_filename: str = "event.txt",
    occurrence_filename: str = "occurrence.txt",
) -> str:
    """Generate DwC-A meta.xml descriptor mapping columns to DwC term URIs.

    meta.xml is derived directly from the field catalogues so that term URIs
    can never drift from the TSV columns. Column 0 carries both a structural
    role (<id> in core, <coreid> in extension) and a term mapping (<field>),
    matching GBIF IPT output.
    """

    archive = ET.Element("archive")
    archive.set("xmlns", "http://rs.tdwg.org/dwc/text/")
    archive.set("metadata", "eml.xml")

    _append_table(
        archive,
        tag="core",
        row_type=DWC + "Event",
        filename=event_filename,
        fields=event_fields,
        id_tag="id",
    )
    _append_table(
        archive,
        tag="extension",
        row_type=DWC + "Occurrence",
        filename=occurrence_filename,
        fields=occurrence_fields,
        id_tag="coreid",
    )

    ET.indent(archive, space="  ")
    xml_str = ET.tostring(archive, encoding="unicode", xml_declaration=False)
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + xml_str + "\n"


def _append_table(
    archive: ET.Element,
    *,
    tag: str,
    row_type: str,
    filename: str,
    fields: list[DwCAField],
    id_tag: str,
) -> None:
    table = ET.SubElement(archive, tag)
    table.set("rowType", row_type)
    table.set("encoding", "UTF-8")
    table.set("fieldsTerminatedBy", "\\t")
    table.set("linesTerminatedBy", "\\n")
    table.set("fieldsEnclosedBy", '"')
    table.set("ignoreHeaderLines", "1")

    files = ET.SubElement(table, "files")
    location = ET.SubElement(files, "location")
    location.text = filename

    id_elem = ET.SubElement(table, id_tag)
    id_elem.set("index", "0")

    for i, field in enumerate(fields):
        field_elem = ET.SubElement(table, "field")
        field_elem.set("index", str(i))
        field_elem.set("term", field.term)


# ──────────────────────────────────────────────────────────────
# eml.xml generation
# ──────────────────────────────────────────────────────────────


def generate_eml_xml(project) -> str:
    """Generate minimal EML 2.1.1 metadata XML for the dataset."""
    from django.utils import timezone

    project_slug = slugify(project.name)
    now = timezone.now().strftime("%Y-%m-%dT%H:%M:%S")

    eml = ET.Element("eml:eml")
    eml.set("xmlns:eml", "eml://ecoinformatics.org/eml-2.1.1")
    eml.set("xmlns:dc", "http://purl.org/dc/terms/")
    eml.set("xmlns:xsi", "http://www.w3.org/2001/XMLSchema-instance")
    eml.set(
        "xsi:schemaLocation",
        "eml://ecoinformatics.org/eml-2.1.1 https://eml.ecoinformatics.org/eml-2.1.1/eml.xsd",
    )
    eml.set("packageId", f"urn:ami:dataset:{project_slug}:{now}")
    eml.set("system", "AMI")

    dataset = ET.SubElement(eml, "dataset")

    title = ET.SubElement(dataset, "title")
    title.text = project.name

    # Creator
    creator = ET.SubElement(dataset, "creator")
    org = ET.SubElement(creator, "organizationName")
    org.text = "Automated Monitoring of Insects (AMI)"
    if project.owner and project.owner.name:
        individual = ET.SubElement(creator, "individualName")
        surname = ET.SubElement(individual, "surName")
        surname.text = project.owner.name

    # Abstract
    abstract = ET.SubElement(dataset, "abstract")
    para = ET.SubElement(abstract, "para")
    para.text = project.description or f"Biodiversity monitoring data from {project.name}."

    # Contact
    contact = ET.SubElement(dataset, "contact")
    contact_org = ET.SubElement(contact, "organizationName")
    contact_org.text = "Automated Monitoring of Insects (AMI)"

    # Intellectual rights (required by GBIF). Project.license should be an
    # SPDX identifier or URL; fall back to a conservative "rights reserved"
    # statement when unset rather than claiming a CC license the data isn't
    # actually under.
    rights = ET.SubElement(dataset, "intellectualRights")
    rights_para = ET.SubElement(rights, "para")
    project_license = (getattr(project, "license", "") or "").strip()
    if project_license:
        rights_para.text = project_license
    else:
        rights_para.text = "All rights reserved. No license specified."

    if getattr(project, "rights_holder", ""):
        # EML's <additionalInfo> is the standard slot for rights-holder text
        # when the license block doesn't carry it.
        additional = ET.SubElement(dataset, "additionalInfo")
        additional_para = ET.SubElement(additional, "para")
        additional_para.text = f"Rights holder: {project.rights_holder}"

    ET.indent(eml, space="  ")
    xml_str = ET.tostring(eml, encoding="unicode", xml_declaration=False)
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + xml_str + "\n"


# ──────────────────────────────────────────────────────────────
# Archive packaging
# ──────────────────────────────────────────────────────────────


def create_dwca_zip(event_file: str, occurrence_file: str, meta_xml: str, eml_xml: str) -> str:
    """Package event.txt, occurrence.txt, meta.xml, and eml.xml into a DwC-A ZIP.

    Returns the path to the temporary ZIP file.
    """
    temp_zip = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
    temp_zip.close()

    with zipfile.ZipFile(temp_zip.name, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(event_file, "event.txt")
        zf.write(occurrence_file, "occurrence.txt")
        zf.writestr("meta.xml", meta_xml)
        zf.writestr("eml.xml", eml_xml)

    return temp_zip.name
