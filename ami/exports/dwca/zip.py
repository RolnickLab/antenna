"""Package DwC-A files into a single ZIP.

Task 6 generalizes this to accept an arbitrary file dict; the current
two-extension signature is kept here so the mechanical refactor leaves
behavior unchanged.
"""

from __future__ import annotations

import tempfile
import zipfile


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
