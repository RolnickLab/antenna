"""Package DwC-A files into a single ZIP."""

from __future__ import annotations

import tempfile
import zipfile


def create_dwca_zip(files: dict[str, str], meta_xml: str, eml_xml: str) -> str:
    """Build the archive.

    `files` maps archive-internal name -> source tempfile path.
    Returns the path to the new ZIP.
    """
    temp_zip = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
    temp_zip.close()
    with zipfile.ZipFile(temp_zip.name, "w", zipfile.ZIP_DEFLATED) as zf:
        for archive_name, source_path in files.items():
            zf.write(source_path, archive_name)
        zf.writestr("meta.xml", meta_xml)
        zf.writestr("eml.xml", eml_xml)
    return temp_zip.name
