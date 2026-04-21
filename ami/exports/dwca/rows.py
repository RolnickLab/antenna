"""Row generators for DwC-A extension TSVs (multimedia, measurementorfact).

These generators yield plain dicts so the existing write_tsv + DwCAField
pattern handles both query-backed tables and computed row streams uniformly.
"""

from __future__ import annotations

from ami.exports.dwca.helpers import _format_datetime


def _event_id(event, slug: str) -> str:
    return f"urn:ami:event:{slug}:{event.id}"


def _occurrence_id(occurrence, slug: str) -> str:
    return f"urn:ami:occurrence:{slug}:{occurrence.id}"


def iter_multimedia_rows(events_qs, occurrences_qs, project_slug: str):
    """Yield dicts for multimedia.txt rows.

    Two row types:
      - Capture row: one per SourceImage linked to >=1 occurrence in filter set.
        occurrenceID is blank; identifier is the capture URL.
      - Crop row: one per Detection whose occurrence is in filter set
        AND which has a usable crop URL. occurrenceID populated;
        references = source capture URL.
    """
    events_list = list(events_qs)
    license_value = _project_license(events_list)
    rights_holder = _project_rights_holder(events_list)

    occurrences_by_event: dict[int, list] = {}
    for occ in occurrences_qs.select_related("event").prefetch_related("detections__source_image"):
        if occ.event_id is None:
            continue
        occurrences_by_event.setdefault(occ.event_id, []).append(occ)

    for event in events_list:
        eid = _event_id(event, project_slug)
        occurrences_for_event = occurrences_by_event.get(event.id, [])

        # Deduplicate capture images across all occurrences in this event.
        seen_captures: set[int] = set()
        for occ in occurrences_for_event:
            for det in occ.detections.all():
                si = det.source_image
                if si is None or si.id in seen_captures:
                    continue
                seen_captures.add(si.id)
                capture_url = si.public_url()
                if not capture_url:
                    continue
                yield {
                    "eventID": eid,
                    "occurrenceID": "",
                    "type": "StillImage",
                    "format": "image/jpeg",
                    "identifier": capture_url,
                    "references": "",
                    "created": _format_datetime(si.timestamp),
                    "license": license_value,
                    "rightsHolder": rights_holder,
                    "creator": "",
                    "description": "Source capture image from automated monitoring station",
                }

        # Detection crop rows.
        for occ in occurrences_for_event:
            occ_urn = _occurrence_id(occ, project_slug)
            for det in occ.detections.all():
                crop_url = det.url() if hasattr(det, "url") else None
                if not crop_url:
                    continue
                si = det.source_image
                capture_url = si.public_url() if si else ""
                created_ts = getattr(det, "timestamp", None) or (si.timestamp if si else None)
                yield {
                    "eventID": eid,
                    "occurrenceID": occ_urn,
                    "type": "StillImage",
                    "format": "image/jpeg",
                    "identifier": crop_url,
                    "references": capture_url,
                    "created": _format_datetime(created_ts),
                    "license": license_value,
                    "rightsHolder": rights_holder,
                    "creator": "",
                    "description": "Cropped detection from source capture",
                }


def _project_license(events) -> str:
    for e in events:
        if e.project and getattr(e.project, "license", ""):
            return e.project.license
        break
    return ""


def _project_rights_holder(events) -> str:
    for e in events:
        if e.project and getattr(e.project, "rights_holder", ""):
            return e.project.rights_holder
        break
    return ""
