"""Unit tests for the offline DwC-A structural validator.

Covers the error paths that the integration test against a real export
will never hit (malformed meta.xml, duplicate core ids, dangling coreids,
empty required fields, column count mismatches).
"""

from __future__ import annotations

import tempfile
import zipfile

from django.test import SimpleTestCase

from ami.exports.dwca_validator import validate_dwca_zip

DWC = "http://rs.tdwg.org/dwc/terms/"


META_OK = """<?xml version="1.0" encoding="UTF-8"?>
<archive xmlns="http://rs.tdwg.org/dwc/text/" metadata="eml.xml">
  <core rowType="http://rs.tdwg.org/dwc/terms/Event" encoding="UTF-8"
        fieldsTerminatedBy="\\t" linesTerminatedBy="\\n" fieldsEnclosedBy='"' ignoreHeaderLines="1">
    <files><location>event.txt</location></files>
    <id index="0"/>
    <field index="0" term="http://rs.tdwg.org/dwc/terms/eventID"/>
    <field index="1" term="http://rs.tdwg.org/dwc/terms/eventDate"/>
  </core>
  <extension rowType="http://rs.tdwg.org/dwc/terms/Occurrence" encoding="UTF-8"
             fieldsTerminatedBy="\\t" linesTerminatedBy="\\n" fieldsEnclosedBy='"' ignoreHeaderLines="1">
    <files><location>occurrence.txt</location></files>
    <coreid index="0"/>
    <field index="0" term="http://rs.tdwg.org/dwc/terms/eventID"/>
    <field index="1" term="http://rs.tdwg.org/dwc/terms/occurrenceID"/>
  </extension>
</archive>
"""

EML_OK = '<?xml version="1.0"?><eml:eml xmlns:eml="eml://ecoinformatics.org/eml-2.1.1"><dataset/></eml:eml>'


def _build_zip(files: dict[str, str]) -> str:
    tmp = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
    tmp.close()
    with zipfile.ZipFile(tmp.name, "w") as zf:
        for name, content in files.items():
            zf.writestr(name, content)
    return tmp.name


class DwCAValidatorTests(SimpleTestCase):
    def test_well_formed_archive_passes(self):
        path = _build_zip(
            {
                "meta.xml": META_OK,
                "eml.xml": EML_OK,
                "event.txt": "eventID\teventDate\nE1\t2024-06-15\nE2\t2024-06-16\n",
                "occurrence.txt": "eventID\toccurrenceID\nE1\tO1\nE2\tO2\n",
            }
        )
        result = validate_dwca_zip(path, required_terms={DWC + "eventID"})
        self.assertTrue(result.ok, msg="\n".join(result.errors))

    def test_missing_meta_xml_fails(self):
        path = _build_zip({"eml.xml": EML_OK})
        result = validate_dwca_zip(path)
        self.assertFalse(result.ok)
        self.assertTrue(any("meta.xml" in e for e in result.errors))

    def test_dangling_coreid_is_detected(self):
        path = _build_zip(
            {
                "meta.xml": META_OK,
                "eml.xml": EML_OK,
                "event.txt": "eventID\teventDate\nE1\t2024-06-15\n",
                # O2 references event E2, which doesn't exist in event.txt
                "occurrence.txt": "eventID\toccurrenceID\nE1\tO1\nE2\tO2\n",
            }
        )
        result = validate_dwca_zip(path)
        self.assertFalse(result.ok)
        self.assertTrue(any("coreid" in e and "E2" in e for e in result.errors))

    def test_duplicate_core_id_is_detected(self):
        path = _build_zip(
            {
                "meta.xml": META_OK,
                "eml.xml": EML_OK,
                "event.txt": "eventID\teventDate\nE1\t2024-06-15\nE1\t2024-06-16\n",
                "occurrence.txt": "eventID\toccurrenceID\nE1\tO1\n",
            }
        )
        result = validate_dwca_zip(path)
        self.assertFalse(result.ok)
        self.assertTrue(any("duplicate core id" in e for e in result.errors))

    def test_empty_required_term_is_detected(self):
        path = _build_zip(
            {
                "meta.xml": META_OK,
                "eml.xml": EML_OK,
                "event.txt": "eventID\teventDate\nE1\t\n",
                "occurrence.txt": "eventID\toccurrenceID\nE1\tO1\n",
            }
        )
        result = validate_dwca_zip(path, required_terms={DWC + "eventDate"})
        self.assertFalse(result.ok)
        self.assertTrue(any("eventDate" in e and "empty" in e for e in result.errors))

    def test_column_count_mismatch_is_detected(self):
        path = _build_zip(
            {
                "meta.xml": META_OK,
                "eml.xml": EML_OK,
                # Only 1 column but meta.xml declares 2
                "event.txt": "eventID\nE1\n",
                "occurrence.txt": "eventID\toccurrenceID\nE1\tO1\n",
            }
        )
        result = validate_dwca_zip(path)
        self.assertFalse(result.ok)
        self.assertTrue(any("columns" in e and "meta.xml" in e for e in result.errors))

    def test_malformed_meta_xml_fails_gracefully(self):
        path = _build_zip(
            {
                "meta.xml": "<archive>not closed",
                "eml.xml": EML_OK,
            }
        )
        result = validate_dwca_zip(path)
        self.assertFalse(result.ok)
        self.assertTrue(any("meta.xml" in e and "parse" in e for e in result.errors))

    def test_not_a_zip_fails(self):
        tmp = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
        tmp.write(b"not a zip")
        tmp.close()
        result = validate_dwca_zip(tmp.name)
        self.assertFalse(result.ok)
        self.assertTrue(any("Not a zip" in e for e in result.errors))
