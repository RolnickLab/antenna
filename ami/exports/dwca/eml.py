"""Generate EML 2.2.0 metadata for the DwC-A.

EML 2.2.0 is the current ratified version and what GBIF expects. Geographic
and temporal coverage are computed from the event list; a methods section
documents the automated capture + ML pipeline and the quality-control filters
applied at export time.
"""

from __future__ import annotations

from xml.etree import ElementTree as ET

from django.utils import timezone
from django.utils.text import slugify

EML_NS = "https://eml.ecoinformatics.org/eml-2.2.0"
XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"


def generate_eml_xml(project, events=None) -> str:
    """Return the eml.xml body.

    If `events` is provided (iterable of Event), geographic and temporal
    coverage are computed from it. If absent, the coverage element is omitted.
    """
    project_slug = slugify(project.name)
    now = timezone.now().strftime("%Y-%m-%dT%H:%M:%S")

    eml = ET.Element("eml:eml")
    eml.set("xmlns:eml", EML_NS)
    eml.set("xmlns:dc", "http://purl.org/dc/terms/")
    eml.set("xmlns:xsi", XSI_NS)
    eml.set("xsi:schemaLocation", f"{EML_NS} https://eml.ecoinformatics.org/eml-2.2.0/eml.xsd")
    eml.set("packageId", f"urn:ami:dataset:{project_slug}:{now}")
    eml.set("system", "AMI")

    dataset = ET.SubElement(eml, "dataset")
    _add_text(dataset, "title", project.name)

    creator = ET.SubElement(dataset, "creator")
    _add_text(creator, "organizationName", "Automated Monitoring of Insects (AMI)")
    if project.owner and project.owner.name:
        individual = ET.SubElement(creator, "individualName")
        _add_text(individual, "surName", project.owner.name)

    abstract = ET.SubElement(dataset, "abstract")
    _add_text(abstract, "para", project.description or f"Biodiversity monitoring data from {project.name}.")

    _add_intellectual_rights(dataset, project)

    if events is not None:
        _add_coverage(dataset, events)

    _add_methods(dataset)

    _add_draft_notice(dataset)

    contact = ET.SubElement(dataset, "contact")
    _add_text(contact, "organizationName", "Automated Monitoring of Insects (AMI)")

    ET.indent(eml, space="  ")
    xml_str = ET.tostring(eml, encoding="unicode", xml_declaration=False)
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + xml_str + "\n"


def _add_text(parent, tag, text):
    child = ET.SubElement(parent, tag)
    child.text = text or ""
    return child


def _add_intellectual_rights(dataset, project):
    rights = ET.SubElement(dataset, "intellectualRights")
    para = ET.SubElement(rights, "para")
    project_license = (getattr(project, "license", "") or "").strip()
    para.text = project_license if project_license else "All rights reserved. No license specified."
    if getattr(project, "rights_holder", ""):
        additional = ET.SubElement(dataset, "additionalInfo")
        _add_text(additional, "para", f"Rights holder: {project.rights_holder}")


def _add_coverage(dataset, events):
    lats = [e.deployment.latitude for e in events if e.deployment and e.deployment.latitude is not None]
    lons = [e.deployment.longitude for e in events if e.deployment and e.deployment.longitude is not None]
    starts = [e.start for e in events if e.start]
    ends = [e.end for e in events if e.end] or starts

    if not (lats and lons) and not starts:
        return

    coverage = ET.SubElement(dataset, "coverage")

    if lats and lons:
        geo = ET.SubElement(coverage, "geographicCoverage")
        _add_text(geo, "geographicDescription", "Computed from event deployment coordinates")
        bounding = ET.SubElement(geo, "boundingCoordinates")
        _add_text(bounding, "westBoundingCoordinate", f"{min(lons):.6f}")
        _add_text(bounding, "eastBoundingCoordinate", f"{max(lons):.6f}")
        _add_text(bounding, "northBoundingCoordinate", f"{max(lats):.6f}")
        _add_text(bounding, "southBoundingCoordinate", f"{min(lats):.6f}")

    if starts:
        temporal = ET.SubElement(coverage, "temporalCoverage")
        range_of_dates = ET.SubElement(temporal, "rangeOfDates")
        begin = ET.SubElement(range_of_dates, "beginDate")
        _add_text(begin, "calendarDate", min(starts).date().isoformat())
        end = ET.SubElement(range_of_dates, "endDate")
        _add_text(end, "calendarDate", max(ends).date().isoformat())


def _add_methods(dataset):
    methods = ET.SubElement(dataset, "methods")
    step = ET.SubElement(methods, "methodStep")
    description = ET.SubElement(step, "description")
    _add_text(
        description,
        "para",
        "Images captured at a fixed interval by an automated camera trap with light attractant. "
        "Each image is processed through an ML detector (bounding-box extraction) and an ML "
        "classifier (species prediction). Individual detections are aggregated into occurrences "
        "by spatiotemporal grouping and assigned a consensus determination.",
    )
    sampling = ET.SubElement(methods, "sampling")
    study_extent = ET.SubElement(sampling, "studyExtent")
    _add_text(study_extent, "description", "See <coverage> for geographic and temporal extent.")
    _add_text(sampling, "samplingDescription", "Automated overnight monitoring with continuous image capture.")
    qc = ET.SubElement(methods, "qualityControl")
    qc_description = ET.SubElement(qc, "description")
    _add_text(
        qc_description,
        "para",
        "Project default filters applied before export: score thresholds, include/exclude taxa "
        "lists, soft-delete exclusion. Only occurrences with at least one detection are included.",
    )


def _add_draft_notice(dataset):
    additional = ET.SubElement(dataset, "additionalInfo")
    _add_text(
        additional,
        "para",
        "DRAFT SCHEMA (April 2026). This archive is a preview of the Darwin Core Archive format "
        "being developed for AMI data. Schema details (terms, extensions, required fields) are "
        "subject to change. Do not submit to GBIF or other biodiversity aggregators without first "
        "confirming the current schema with the AMI team.",
    )
