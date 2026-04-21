"""Generate the DwC-A descriptor (meta.xml).

meta.xml is derived from the field catalogues so TSV columns cannot drift from
declared term URIs. This module currently hard-codes the Event-Core + Occurrence
layout; Task 6 will generalize it to take an arbitrary extension list.
"""

from __future__ import annotations

from xml.etree import ElementTree as ET

from ami.exports.dwca.fields import DWC, DwCAField


def generate_meta_xml(
    event_fields: list[DwCAField],
    occurrence_fields: list[DwCAField],
    event_filename: str = "event.txt",
    occurrence_filename: str = "occurrence.txt",
) -> str:
    """Generate DwC-A meta.xml descriptor mapping columns to DwC term URIs."""

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
