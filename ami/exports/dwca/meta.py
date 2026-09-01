"""Generate the DwC-A descriptor (meta.xml).

meta.xml is derived from the field catalogues so TSV columns cannot drift from
declared term URIs. The core/extension list is passed in so the caller composes
the archive shape.
"""

from __future__ import annotations

from xml.etree import ElementTree as ET

from ami.exports.dwca.fields import DwCAField


def generate_meta_xml(tables: list[dict]) -> str:
    """Build meta.xml from a list of table descriptors.

    Each descriptor is a dict:
        {
            "role": "core" | "extension",
            "row_type": <URI>,
            "filename": "event.txt",
            "fields": list[DwCAField],
        }

    The first descriptor must have role="core"; remaining are extensions.
    """
    if not tables or tables[0]["role"] != "core":
        raise ValueError("First table must be the core (role='core')")

    archive = ET.Element("archive")
    archive.set("xmlns", "http://rs.tdwg.org/dwc/text/")
    archive.set("metadata", "eml.xml")

    for table in tables:
        tag = table["role"]
        _append_table(
            archive,
            tag=tag,
            row_type=table["row_type"],
            filename=table["filename"],
            fields=table["fields"],
            id_tag="id" if tag == "core" else "coreid",
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
