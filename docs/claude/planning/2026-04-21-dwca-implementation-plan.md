# DwC-A April 2026 Draft — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a scientifically-defensible Darwin Core Archive export that preserves sampling-effort and absence-inference context (Event Core + Humboldt Extension), adds multimedia and measurement extensions, upgrades EML to 2.2.0, runs structural validation before packaging, and ships behind a clearly-labeled "April 2026 Draft" UI option for field testing.

**Architecture:** Event-Core DwC-A. `event.txt` carries DwC Event terms + flattened Humboldt `eco:` terms. `occurrence.txt`, `multimedia.txt`, and `measurementorfact.txt` are coreid=eventID extensions. Extension rows that pertain to a single occurrence carry an `occurrenceID` column for back-linkage. EML 2.2.0 with computed geographic/temporal coverage + methods section. Runtime pre-zip validation via extended offline validator. Existing `ami/exports/dwca.py` splits into `ami/exports/dwca/` package for manageability as the code ~doubles.

**Tech Stack:** Django 4.2, Python 3.10+ typing, stdlib (`csv`, `zipfile`, `xml.etree.ElementTree`, `tempfile`), `django.utils.text.slugify`, existing `ami.exports.base.BaseExporter` + `ami.exports.dwca_validator`.

**Spec:** `docs/claude/planning/2026-04-21-dwca-april-draft-design.md`
**PR:** #1131 (`feat/dwca-export`)
**Follow-up ticket:** #1262 (CamtrapDP)

---

## File Structure

**New package layout (`ami/exports/dwca/`):**

- `__init__.py` — re-export the public API so external imports (`format_types.py`, tests) keep working unchanged
- `fields.py` — `DwCAField` dataclass + `EVENT_FIELDS`, `OCCURRENCE_FIELDS`, `MULTIMEDIA_FIELDS`, `MOF_FIELDS` catalogues
- `helpers.py` — `_format_event_date`, `_format_time`, `_format_datetime`, `_format_coord`, `_format_duration`, `_get_rank_from_parents`, `get_specific_epithet`, `_get_verification_status`
- `targetscope.py` — `derive_target_taxonomic_scope(project)` LCA helper
- `rows.py` — `iter_multimedia_rows(events_qs, occurrences_qs, project_slug)`, `iter_mof_rows(occurrences_qs, project_slug)`
- `tsv.py` — `write_tsv(filepath, fields, source, project_slug, progress_callback)` (supports queryset OR iterable of mapping-like objects via a small adapter; see Task 5)
- `meta.py` — `generate_meta_xml()` now takes a list of `(tag, row_type, filename, fields)` so the caller composes the archive shape
- `eml.py` — `generate_eml_xml(project, events_qs)` (2.2.0, computed coverage + methods)
- `zip.py` — `create_dwca_zip(files: dict[str, str], meta_xml: str, eml_xml: str)` (`files` maps archive-name → tmp-path; e.g. `{"event.txt": tmp1, "occurrence.txt": tmp2, ...}`)

**Modified files:**
- `ami/exports/format_types.py` — `DwCAExporter.export()` composes the 4-file archive + runs pre-zip validation
- `ami/exports/dwca_validator.py` — add `occurrenceID` cross-reference check + multimedia uniqueness warning
- `ami/exports/tests.py` — update existing `DwCAExportTest` setup + add new extension tests
- `ui/src/data-services/models/export.ts` — add `'dwca'` entry + label
- `docs/claude/dwca-format-reference.md` — document new archive shape

**Unchanged:** `ami/exports/base.py`, `ami/exports/registry.py`, `ami/exports/tests_dwca_validator.py` (new tests go into a new file or extend existing).

---

## Test infrastructure note

The existing `DwCAExportTest` uses `setUpClass` to run the export **once** and share the ZIP across structural assertions (see `ami/exports/tests.py:310-355`). Every new extension test should reuse `self._open_zip()` and assert against the cached export — do NOT run a second export per test. If a new test needs a different project/filter shape, follow the pattern of `test_dwca_export_with_collection_filter` (`ami/exports/tests.py:533`) which creates its own export inside the test method.

Docker test runner (from CLAUDE.md; keepdb for speed):
```bash
docker compose run --rm django python manage.py test ami.exports.tests --keepdb -v 2
```

---

## Task 1: Split `dwca.py` into package (mechanical, safety-net via existing tests)

**Files:**
- Create: `ami/exports/dwca/__init__.py`
- Create: `ami/exports/dwca/fields.py`
- Create: `ami/exports/dwca/helpers.py`
- Create: `ami/exports/dwca/tsv.py`
- Create: `ami/exports/dwca/meta.py`
- Create: `ami/exports/dwca/eml.py`
- Create: `ami/exports/dwca/zip.py`
- Delete: `ami/exports/dwca.py`

- [ ] **Step 1: Verify existing tests pass as baseline**

Run: `docker compose run --rm django python manage.py test ami.exports.tests.DwCAExportTest --keepdb -v 2`
Expected: 10 tests pass.

- [ ] **Step 2: Create `ami/exports/dwca/helpers.py`**

Move these verbatim from `ami/exports/dwca.py` (current lines 146-232): `_format_event_date`, `_format_time`, `_format_datetime`, `_format_coord`, `_format_duration`, `_get_rank_from_parents`, `get_specific_epithet`, `_get_verification_status`. Keep the module-level `logger = logging.getLogger(__name__)`.

- [ ] **Step 3: Create `ami/exports/dwca/fields.py`**

```python
"""DwC-A column catalogues. Each DwCAField ties a term URI, TSV header, and row extractor together so meta.xml cannot drift from the TSV."""

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
    term: str
    header: str
    extract: Callable[[Any, str], str]
    required: bool = False


# Paste current EVENT_FIELDS list verbatim from dwca.py (lines 47-78)
EVENT_FIELDS: list[DwCAField] = [
    # ... (existing content unchanged for now; extended in Task 3)
]

# Paste current OCCURRENCE_FIELDS list verbatim from dwca.py (lines 84-143)
OCCURRENCE_FIELDS: list[DwCAField] = [
    # ... (existing content unchanged for now; extended in Task 4)
]
```

Replace the `...` comments with the actual field list contents. MULTIMEDIA_FIELDS and MOF_FIELDS will be added in later tasks.

- [ ] **Step 4: Create `ami/exports/dwca/tsv.py`**

Move `write_tsv` verbatim from `dwca.py:239-264`. Update its import to use the new `DwCAField` location:
```python
from ami.exports.dwca.fields import DwCAField
```

- [ ] **Step 5: Create `ami/exports/dwca/meta.py`**

Move `generate_meta_xml`, `_append_table`, and the `DWC` constant usage from `dwca.py:272-339`. Import `DwCAField` from `ami.exports.dwca.fields`. **Do not change the signature yet** — Task 6 will generalize it.

- [ ] **Step 6: Create `ami/exports/dwca/eml.py`**

Move `generate_eml_xml` verbatim from `dwca.py:347-410`. Keep it at EML 2.1.1 for now; Task 9 upgrades it.

- [ ] **Step 7: Create `ami/exports/dwca/zip.py`**

Move `create_dwca_zip` verbatim from `dwca.py:418-432`. Keep its current 2-extension signature; Task 6 generalizes it.

- [ ] **Step 8: Create `ami/exports/dwca/__init__.py`**

```python
"""Public surface of the DwC-A export package.

Re-exports keep external imports (format_types.py, tests) working
unchanged while internal code is organized by responsibility.
"""

from ami.exports.dwca.eml import generate_eml_xml
from ami.exports.dwca.fields import (
    DC,
    DWC,
    ECO,
    DwCAField,
    EVENT_FIELDS,
    OCCURRENCE_FIELDS,
)
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
from ami.exports.dwca.meta import generate_meta_xml
from ami.exports.dwca.tsv import write_tsv
from ami.exports.dwca.zip import create_dwca_zip

__all__ = [
    "DC",
    "DWC",
    "ECO",
    "DwCAField",
    "EVENT_FIELDS",
    "OCCURRENCE_FIELDS",
    "create_dwca_zip",
    "generate_eml_xml",
    "generate_meta_xml",
    "get_specific_epithet",
    "write_tsv",
    "_format_coord",
    "_format_datetime",
    "_format_duration",
    "_format_event_date",
    "_format_time",
    "_get_rank_from_parents",
    "_get_verification_status",
]
```

- [ ] **Step 9: Delete old file**

```bash
git rm ami/exports/dwca.py
```

- [ ] **Step 10: Run existing tests to verify no regression**

Run: `docker compose run --rm django python manage.py test ami.exports.tests.DwCAExportTest --keepdb -v 2`
Expected: 10 tests pass, same assertions as before the split.

- [ ] **Step 11: Commit**

```bash
git add ami/exports/dwca/ ami/exports/dwca.py
git commit -m "$(cat <<'EOF'
refactor(exports): split dwca.py into package

Upcoming additions (Humboldt eco: terms, multimedia and MoF
extensions, EML 2.2.0) roughly double the code. Split by
responsibility now so each module has a single clear purpose.

Public API unchanged — re-exported from ami.exports.dwca.__init__.

Co-Authored-By: Claude <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Target taxonomic scope derivation (LCA helper)

**Why:** `eco:targetTaxonomicScope` is derived from `Project.default_filters_include_taxa` via lowest common ancestor. Pure function, easy to test.

**Files:**
- Create: `ami/exports/dwca/targetscope.py`
- Modify: `ami/exports/tests.py` (add test class)

- [ ] **Step 1: Write the failing test**

Add at the end of `ami/exports/tests.py`:

```python
class TargetTaxonomicScopeTest(TestCase):
    """Tests for eco:targetTaxonomicScope derivation from project include taxa."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.project, cls.deployment = setup_test_project(reuse=False)
        create_taxa(cls.project)

    def test_empty_include_taxa_returns_empty_string(self):
        from ami.exports.dwca.targetscope import derive_target_taxonomic_scope

        self.project.default_filters_include_taxa.clear()
        self.assertEqual(derive_target_taxonomic_scope(self.project), "")

    def test_single_taxon_returns_its_name(self):
        from ami.exports.dwca.targetscope import derive_target_taxonomic_scope
        from ami.main.models import Taxon

        taxon = Taxon.objects.filter(projects=self.project).first()
        self.assertIsNotNone(taxon, "Expected at least one taxon on fixture project")
        self.project.default_filters_include_taxa.set([taxon])
        self.assertEqual(derive_target_taxonomic_scope(self.project), taxon.name)

    def test_multiple_taxa_returns_lca_name(self):
        from ami.exports.dwca.targetscope import derive_target_taxonomic_scope
        from ami.main.models import Taxon

        # Find two taxa sharing a parent in parents_json
        taxa = list(Taxon.objects.filter(projects=self.project).exclude(parents_json=[])[:2])
        if len(taxa) < 2:
            self.skipTest("Fixture does not have two taxa with shared ancestry")
        for t in taxa:
            t.save(update_calculated_fields=True)
            t.refresh_from_db()
        self.project.default_filters_include_taxa.set(taxa)

        result = derive_target_taxonomic_scope(self.project)
        # LCA should be some ancestor name, not empty
        self.assertTrue(result, "LCA should resolve to a non-empty ancestor name")
        # And it should be in the ancestry of BOTH taxa
        for t in taxa:
            ancestor_names = [p.name for p in t.parents_json] + [t.name]
            self.assertIn(result, ancestor_names, f"{result} not in ancestry of {t.name}")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose run --rm django python manage.py test ami.exports.tests.TargetTaxonomicScopeTest --keepdb -v 2`
Expected: FAIL — `ModuleNotFoundError: No module named 'ami.exports.dwca.targetscope'`

- [ ] **Step 3: Implement `ami/exports/dwca/targetscope.py`**

```python
"""Derive eco:targetTaxonomicScope from a project's include-taxa filter.

The scope is the lowest common ancestor (LCA) across all taxa in
Project.default_filters_include_taxa. Empty include-list -> empty
string (meta.xml still declares the column; EML notes the gap).

This is the v1 sourcing strategy. v2 will move to a per-Site TaxaList
so each deployment can declare its own expected species pool (the
groundwork for per-taxon absence occurrence rows).
"""

from __future__ import annotations


def derive_target_taxonomic_scope(project) -> str:
    """Return the name of the LCA of the project's include-taxa filter.

    `parents_json` on each Taxon is ordered root-to-leaf (kingdom first).
    The LCA is the deepest (longest) common prefix of the
    `parents_json + [self]` chains across all selected taxa.
    """
    taxa = list(project.default_filters_include_taxa.all())
    if not taxa:
        return ""

    def ancestry(t) -> list[tuple[int, str]]:
        # parents_json entries expose .id and .name; list is root -> leaf
        chain: list[tuple[int, str]] = [(p.id, p.name) for p in (t.parents_json or [])]
        chain.append((t.id, t.name))
        return chain

    chains = [ancestry(t) for t in taxa]
    if any(not c for c in chains):
        return ""

    # Walk positions in lockstep; stop at the first divergence.
    lca_name = ""
    for position in zip(*chains):
        ids = {entry[0] for entry in position}
        if len(ids) != 1:
            break
        lca_name = position[0][1]
    return lca_name
```

- [ ] **Step 4: Run test to verify it passes**

Run: `docker compose run --rm django python manage.py test ami.exports.tests.TargetTaxonomicScopeTest --keepdb -v 2`
Expected: 3 tests pass.

- [ ] **Step 5: Commit**

```bash
git add ami/exports/dwca/targetscope.py ami/exports/tests.py
git commit -m "$(cat <<'EOF'
feat(exports): derive targetTaxonomicScope via LCA of include taxa

Pure helper that walks parents_json chains and returns the deepest
common ancestor name. Empty include-list -> empty string. v1
strategy; v2 will source from a per-Site TaxaList.

Co-Authored-By: Claude <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Add Humboldt eco: terms as columns on event.txt

**Why:** Preserves sampling effort + declares absence-reportability — the scientific contribution of automated monitoring. Flattened onto Event Core rows (GBIF accepts this; simpler than a separate humboldt.txt extension).

**Files:**
- Modify: `ami/exports/dwca/fields.py`
- Modify: `ami/exports/tests.py` (extend `DwCAExportTest`)

- [ ] **Step 1: Write the failing test**

Add to `DwCAExportTest` in `ami/exports/tests.py`:

```python
    def test_event_has_humboldt_eco_columns(self):
        """event.txt should carry the Humboldt eco: columns as flattened columns."""
        expected_columns = {
            "isSamplingEffortReported",
            "samplingEffortValue",
            "samplingEffortUnit",
            "samplingEffortProtocol",
            "isAbsenceReported",
            "targetTaxonomicScope",
            "inventoryTypes",
            "protocolNames",
            "protocolDescriptions",
            "hasMaterialSamples",
            "materialSampleTypes",
        }
        with self._open_zip() as f:
            with zipfile.ZipFile(f, "r") as zf:
                event_data = zf.read("event.txt").decode("utf-8")
                reader = csv.DictReader(StringIO(event_data), delimiter="\t")
                self.assertTrue(
                    expected_columns.issubset(set(reader.fieldnames)),
                    f"event.txt missing Humboldt columns: {expected_columns - set(reader.fieldnames)}",
                )
                rows = list(reader)
                self.assertGreater(len(rows), 0)
                for row in rows:
                    self.assertEqual(row["isSamplingEffortReported"], "true")
                    self.assertEqual(row["isAbsenceReported"], "true")
                    self.assertEqual(row["hasMaterialSamples"], "true")
                    self.assertEqual(row["materialSampleTypes"], "digital images")
                    self.assertEqual(row["inventoryTypes"], "trap or sample")

    def test_event_humboldt_terms_in_meta_xml(self):
        """meta.xml core should declare eco: term URIs for Humboldt columns."""
        with self._open_zip() as f:
            with zipfile.ZipFile(f, "r") as zf:
                meta_xml = zf.read("meta.xml").decode("utf-8")
                self.assertIn("http://rs.tdwg.org/eco/terms/isSamplingEffortReported", meta_xml)
                self.assertIn("http://rs.tdwg.org/eco/terms/isAbsenceReported", meta_xml)
                self.assertIn("http://rs.tdwg.org/eco/terms/targetTaxonomicScope", meta_xml)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose run --rm django python manage.py test ami.exports.tests.DwCAExportTest.test_event_has_humboldt_eco_columns ami.exports.tests.DwCAExportTest.test_event_humboldt_terms_in_meta_xml --keepdb -v 2`
Expected: FAIL — columns missing from event.txt; meta.xml lacks eco: terms.

- [ ] **Step 3: Extend EVENT_FIELDS in `ami/exports/dwca/fields.py`**

Append to `EVENT_FIELDS` (after the existing `DC + "modified"` entry):

```python
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
```

At the top of `fields.py`, add a helper:

```python
def _humboldt_effort_value(event) -> str:
    """Sampling effort value: prefer image count, fall back to nothing."""
    count = getattr(event, "captures_count", None) or 0
    return str(count) if count else ""
```

- [ ] **Step 4: Attach target-scope value to events in the exporter**

Modify `ami/exports/format_types.py` `DwCAExporter.export()`. Before calling `write_tsv` on events, compute the scope once and attach it to each event:

```python
from ami.exports.dwca.targetscope import derive_target_taxonomic_scope

target_scope = derive_target_taxonomic_scope(self.project)
events_list = list(events_qs)
for e in events_list:
    e._target_taxonomic_scope = target_scope
event_count = write_tsv(event_file.name, EVENT_FIELDS, events_list, project_slug)
```

Note: `write_tsv` currently calls `queryset.iterator(chunk_size=500)`. Update its signature to accept either a queryset or a plain iterable (see Task 5, Step 3) — or for this task only, duck-type: try `.iterator()` else iterate directly.

- [ ] **Step 5: Update `write_tsv` to accept plain iterables**

In `ami/exports/dwca/tsv.py`:

```python
def write_tsv(filepath, fields, source, project_slug, progress_callback=None):
    """Write a tab-delimited file. `source` is a Django queryset OR any iterable."""
    headers = [f.header for f in fields]
    records_written = 0
    iterator = source.iterator(chunk_size=500) if hasattr(source, "iterator") else iter(source)
    with open(filepath, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter="\t", quoting=csv.QUOTE_MINIMAL, lineterminator="\n")
        writer.writerow(headers)
        for obj in iterator:
            row = [field.extract(obj, project_slug) for field in fields]
            writer.writerow(row)
            records_written += 1
            if progress_callback and records_written % 500 == 0:
                progress_callback(records_written)
    return records_written
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `docker compose run --rm django python manage.py test ami.exports.tests.DwCAExportTest --keepdb -v 2`
Expected: all tests pass (including the two new ones and the existing 10).

- [ ] **Step 7: Commit**

```bash
git add ami/exports/dwca/fields.py ami/exports/dwca/tsv.py ami/exports/format_types.py ami/exports/tests.py
git commit -m "$(cat <<'EOF'
feat(exports): add Humboldt eco: terms as event.txt columns

Flatten 11 Humboldt Extension terms onto Event Core rows:
sampling-effort structure (reported/value/unit/protocol), absence
reportability, targetTaxonomicScope (LCA-derived), protocol
identifiers, and material-sample declaration.

Carries the scientific contribution of automated monitoring
(provable absence during known sampling windows) into the GBIF
pipeline. GBIF accepts eco: terms on Event rows as the
pragmatic alternative to a separate humboldt.txt extension.

Co-Authored-By: Claude <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Add `associatedMedia` column to occurrence.txt

**Why:** Pipe-separated public URLs of source captures, per the design doc. Redundant with multimedia.txt but convenient for CSV-level consumers.

**Files:**
- Modify: `ami/exports/dwca/fields.py`
- Modify: `ami/exports/format_types.py` (ensure detection + source_image are prefetched)
- Modify: `ami/exports/tests.py`

- [ ] **Step 1: Write the failing test**

Add to `DwCAExportTest`:

```python
    def test_occurrence_has_associated_media_column(self):
        """occurrence.txt should carry associatedMedia as pipe-separated URLs."""
        with self._open_zip() as f:
            with zipfile.ZipFile(f, "r") as zf:
                occ_data = zf.read("occurrence.txt").decode("utf-8")
                reader = csv.DictReader(StringIO(occ_data), delimiter="\t")
                self.assertIn("associatedMedia", reader.fieldnames)
                rows = list(reader)
                # At least one row should have a non-empty associatedMedia value
                non_empty = [r for r in rows if r.get("associatedMedia")]
                self.assertGreater(len(non_empty), 0, "No occurrences have associatedMedia")
                for r in non_empty:
                    # URLs separated by pipe, no trailing pipe
                    self.assertFalse(r["associatedMedia"].endswith("|"))
                    for part in r["associatedMedia"].split("|"):
                        self.assertTrue(part.startswith("http"), f"Not a URL: {part}")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose run --rm django python manage.py test ami.exports.tests.DwCAExportTest.test_occurrence_has_associated_media_column --keepdb -v 2`
Expected: FAIL — column missing.

- [ ] **Step 3: Add field to OCCURRENCE_FIELDS**

In `ami/exports/dwca/fields.py`, append to `OCCURRENCE_FIELDS` (after the last entry):

```python
    DwCAField(
        DWC + "associatedMedia",
        "associatedMedia",
        lambda o, slug: _associated_media(o),
    ),
```

And a helper near the other helpers:

```python
def _associated_media(occurrence) -> str:
    """Pipe-separated distinct public URLs of source captures for this occurrence.

    Ordered by detection timestamp. Uses prefetched detections + source_image;
    the exporter ensures the prefetch chain.
    """
    seen: set[str] = set()
    urls: list[str] = []
    detections = sorted(
        occurrence.detections.all(),
        key=lambda d: (d.timestamp or d.source_image.timestamp),
    )
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
```

- [ ] **Step 4: Ensure the queryset prefetches `detections__source_image`**

In `ami/exports/format_types.py` `DwCAExporter.get_queryset()`, extend the existing prefetch chain:

```python
return (
    Occurrence.objects.valid()
    .filter(project=self.project, event__isnull=False, determination__isnull=False)
    .apply_default_filters(self.project)
    .select_related("determination", "event", "deployment")
    .prefetch_related("detections__source_image")
    .with_detections_count()
    .with_identifications()
)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `docker compose run --rm django python manage.py test ami.exports.tests.DwCAExportTest.test_occurrence_has_associated_media_column --keepdb -v 2`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add ami/exports/dwca/fields.py ami/exports/format_types.py ami/exports/tests.py
git commit -m "$(cat <<'EOF'
feat(exports): add associatedMedia column to occurrence.txt

Pipe-separated distinct source-capture URLs per occurrence, ordered
by detection timestamp. Redundant with multimedia.txt but useful
for tabular consumers.

Co-Authored-By: Claude <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: `multimedia.txt` extension — field catalogue + row generator

**Why:** One file holds both capture images (event-level context) and detection crops (per-occurrence evidence). `occurrenceID` column on crop rows links them back to occurrences; capture rows have it blank.

**Files:**
- Modify: `ami/exports/dwca/fields.py` (add `MULTIMEDIA_FIELDS`)
- Create: `ami/exports/dwca/rows.py` (`iter_multimedia_rows`)
- Modify: `ami/exports/tests.py`

- [ ] **Step 1: Write the failing test**

Add a new test class in `ami/exports/tests.py`. It will fail first because neither the constant nor the generator exists:

```python
class MultimediaExtensionTest(TestCase):
    """Unit tests for multimedia.txt row generator (in isolation from a full export)."""

    def test_field_catalogue_present(self):
        from ami.exports.dwca.fields import MULTIMEDIA_FIELDS

        headers = [f.header for f in MULTIMEDIA_FIELDS]
        for required in [
            "eventID",
            "occurrenceID",
            "type",
            "format",
            "identifier",
            "references",
            "created",
            "license",
            "rightsHolder",
        ]:
            self.assertIn(required, headers)

    def test_iter_multimedia_rows_emits_capture_and_crop_rows(self):
        from ami.exports.dwca.rows import iter_multimedia_rows

        project, deployment = setup_test_project(reuse=False)
        create_captures(deployment=deployment, num_nights=1, images_per_night=4, interval_minutes=1)
        group_images_into_events(deployment)
        create_taxa(project)
        create_occurrences(num=4, deployment=deployment)

        events_qs = project.events.all()
        occurrences_qs = (
            Occurrence.objects.valid()
            .filter(project=project, event__isnull=False, determination__isnull=False)
        )
        rows = list(iter_multimedia_rows(events_qs, occurrences_qs, "test-project"))

        # Expect at least one capture row (occurrenceID blank) and at least one crop row
        capture_rows = [r for r in rows if not r["occurrenceID"]]
        crop_rows = [r for r in rows if r["occurrenceID"]]
        self.assertGreater(len(capture_rows), 0, "Expected capture rows with blank occurrenceID")
        self.assertGreater(len(crop_rows), 0, "Expected detection-crop rows with occurrenceID")

        # Every crop row must have both identifier (crop URL) and references (source URL)
        for r in crop_rows:
            self.assertTrue(r["identifier"], "Crop row missing identifier")
            self.assertTrue(r["references"], "Crop row missing references (source capture URL)")
            self.assertEqual(r["type"], "StillImage")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose run --rm django python manage.py test ami.exports.tests.MultimediaExtensionTest --keepdb -v 2`
Expected: FAIL — `ImportError: cannot import name 'MULTIMEDIA_FIELDS'` and `No module named 'ami.exports.dwca.rows'`.

- [ ] **Step 3: Add `MULTIMEDIA_FIELDS` to `fields.py`**

The multimedia row generator in Task 5, Step 4 yields plain dicts. The field extractors here read from those dicts:

```python
MULTIMEDIA_FIELDS: list[DwCAField] = [
    DwCAField(DWC + "eventID", "eventID", lambda r, slug: r["eventID"], required=True),
    DwCAField(DWC + "occurrenceID", "occurrenceID", lambda r, slug: r.get("occurrenceID", "")),
    DwCAField("http://purl.org/dc/terms/type", "type", lambda r, slug: r.get("type", "StillImage")),
    DwCAField("http://purl.org/dc/terms/format", "format", lambda r, slug: r.get("format", "image/jpeg")),
    DwCAField("http://purl.org/dc/terms/identifier", "identifier", lambda r, slug: r["identifier"], required=True),
    DwCAField("http://purl.org/dc/terms/references", "references", lambda r, slug: r.get("references", "")),
    DwCAField("http://purl.org/dc/terms/created", "created", lambda r, slug: r.get("created", "")),
    DwCAField("http://purl.org/dc/terms/license", "license", lambda r, slug: r.get("license", "")),
    DwCAField("http://purl.org/dc/terms/rightsHolder", "rightsHolder", lambda r, slug: r.get("rightsHolder", "")),
    DwCAField("http://purl.org/dc/terms/creator", "creator", lambda r, slug: r.get("creator", "")),
    DwCAField("http://purl.org/dc/terms/description", "description", lambda r, slug: r.get("description", "")),
]
```

Also export it from `__init__.py` (add to both the import block and `__all__`).

- [ ] **Step 4: Create `ami/exports/dwca/rows.py`**

```python
"""Row generators for DwC-A extension TSVs (multimedia, measurementorfact).

Both generators yield plain dicts so the TSV writer can treat them the
same as Django model instances via the DwCAField extract lambdas.
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
    license = _project_license(events_qs)
    rights_holder = _project_rights_holder(events_qs)

    # Build (event, [occurrences]) pairs up front so we can iterate once.
    occurrences_by_event: dict[int, list] = {}
    for occ in occurrences_qs.select_related("event").prefetch_related(
        "detections__source_image"
    ):
        if occ.event_id is None:
            continue
        occurrences_by_event.setdefault(occ.event_id, []).append(occ)

    for event in events_qs:
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
                    "license": license,
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
                yield {
                    "eventID": eid,
                    "occurrenceID": occ_urn,
                    "type": "StillImage",
                    "format": "image/jpeg",
                    "identifier": crop_url,
                    "references": capture_url,
                    "created": _format_datetime(det.timestamp or (si.timestamp if si else None)),
                    "license": license,
                    "rightsHolder": rights_holder,
                    "creator": "",
                    "description": "Cropped detection from source capture",
                }


def _project_license(events_qs) -> str:
    for e in events_qs:
        if e.project and getattr(e.project, "license", ""):
            return e.project.license
        break
    return ""


def _project_rights_holder(events_qs) -> str:
    for e in events_qs:
        if e.project and getattr(e.project, "rights_holder", ""):
            return e.project.rights_holder
        break
    return ""
```

- [ ] **Step 5: Run test to verify it passes**

Run: `docker compose run --rm django python manage.py test ami.exports.tests.MultimediaExtensionTest --keepdb -v 2`
Expected: both tests pass.

- [ ] **Step 6: Commit**

```bash
git add ami/exports/dwca/fields.py ami/exports/dwca/rows.py ami/exports/dwca/__init__.py ami/exports/tests.py
git commit -m "$(cat <<'EOF'
feat(exports): add multimedia extension field catalogue and row generator

Single multimedia.txt carries both capture-image rows (occurrenceID
blank) and detection-crop rows (occurrenceID linking back to
occurrence.txt). dc:references on crop rows points back to the
source capture URL.

Row generator yields plain dicts so the existing write_tsv +
DwCAField pattern handles both query-backed tables and computed
row streams uniformly.

Co-Authored-By: Claude <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: Generalize meta.xml + zip packaging; wire multimedia.txt into the archive

**Why:** Current `generate_meta_xml` hardcodes two tables; `create_dwca_zip` hardcodes two payload files. Generalize both to accept a list, then add multimedia.txt to the archive.

**Files:**
- Modify: `ami/exports/dwca/meta.py`
- Modify: `ami/exports/dwca/zip.py`
- Modify: `ami/exports/format_types.py`
- Modify: `ami/exports/tests.py`

- [ ] **Step 1: Write the failing test**

Add to `DwCAExportTest`:

```python
    def test_multimedia_txt_in_archive(self):
        with self._open_zip() as f:
            with zipfile.ZipFile(f, "r") as zf:
                self.assertIn("multimedia.txt", zf.namelist())
                data = zf.read("multimedia.txt").decode("utf-8")
                reader = csv.DictReader(StringIO(data), delimiter="\t")
                rows = list(reader)
                self.assertGreater(len(rows), 0, "multimedia.txt has no rows")
                ids = {row["eventID"] for row in rows if row["eventID"]}
                # Every multimedia eventID must exist in event.txt
                event_data = zf.read("event.txt").decode("utf-8")
                event_ids = {r["eventID"] for r in csv.DictReader(StringIO(event_data), delimiter="\t")}
                self.assertTrue(ids.issubset(event_ids), f"Orphaned multimedia eventIDs: {ids - event_ids}")

    def test_meta_xml_declares_multimedia_extension(self):
        with self._open_zip() as f:
            with zipfile.ZipFile(f, "r") as zf:
                meta_xml = zf.read("meta.xml").decode("utf-8")
                # Look for a second <extension> element referencing multimedia.txt
                self.assertIn("multimedia.txt", meta_xml)
                # GBIF Multimedia extension rowType
                self.assertIn("http://rs.gbif.org/terms/1.0/Multimedia", meta_xml)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose run --rm django python manage.py test ami.exports.tests.DwCAExportTest.test_multimedia_txt_in_archive ami.exports.tests.DwCAExportTest.test_meta_xml_declares_multimedia_extension --keepdb -v 2`
Expected: FAIL — multimedia.txt not in archive.

- [ ] **Step 3: Generalize `generate_meta_xml`**

Rewrite `ami/exports/dwca/meta.py`:

```python
"""Generate the DwC-A descriptor (meta.xml).

meta.xml is derived from the field catalogues so TSV columns cannot
drift from declared term URIs. The core/extension list is passed in
so the caller composes the archive shape.
"""

from __future__ import annotations

from xml.etree import ElementTree as ET

from ami.exports.dwca.fields import DwCAField, DWC


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


def _append_table(archive, *, tag, row_type, filename, fields: list[DwCAField], id_tag: str) -> None:
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
```

- [ ] **Step 4: Generalize `create_dwca_zip`**

Rewrite `ami/exports/dwca/zip.py`:

```python
"""Package DwC-A files into a single ZIP."""

import tempfile
import zipfile


def create_dwca_zip(files: dict[str, str], meta_xml: str, eml_xml: str) -> str:
    """Build the archive.

    `files` maps archive-internal-name -> source-temp-path.
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
```

- [ ] **Step 5: Update `DwCAExporter.export()` to produce multimedia.txt**

Replace the body of `DwCAExporter.export()` in `ami/exports/format_types.py`:

```python
def export(self):
    """Export project data as a Darwin Core Archive ZIP."""
    from django.utils.text import slugify

    from ami.exports.dwca import (
        EVENT_FIELDS,
        OCCURRENCE_FIELDS,
        create_dwca_zip,
        generate_eml_xml,
        generate_meta_xml,
        write_tsv,
    )
    from ami.exports.dwca.fields import MULTIMEDIA_FIELDS
    from ami.exports.dwca.rows import iter_multimedia_rows
    from ami.exports.dwca.targetscope import derive_target_taxonomic_scope

    project_slug = slugify(self.project.name)

    def _tmp_txt():
        tf = tempfile.NamedTemporaryFile(delete=False, suffix=".txt", mode="w", encoding="utf-8")
        tf.close()
        return tf.name

    event_path = _tmp_txt()
    occ_path = _tmp_txt()
    multimedia_path = _tmp_txt()

    try:
        events_qs = self.get_events_queryset()
        events_list = list(events_qs)
        target_scope = derive_target_taxonomic_scope(self.project)
        for e in events_list:
            e._target_taxonomic_scope = target_scope

        event_count = write_tsv(event_path, EVENT_FIELDS, events_list, project_slug)
        logger.info(f"DwC-A: wrote {event_count} events")

        occ_count = write_tsv(
            occ_path,
            OCCURRENCE_FIELDS,
            self.queryset,
            project_slug,
            progress_callback=self.update_job_progress,
        )
        logger.info(f"DwC-A: wrote {occ_count} occurrences")

        mm_count = write_tsv(
            multimedia_path,
            MULTIMEDIA_FIELDS,
            iter_multimedia_rows(events_list, self.queryset, project_slug),
            project_slug,
        )
        logger.info(f"DwC-A: wrote {mm_count} multimedia rows")

        if self.total_records:
            self.update_job_progress(occ_count)

        meta_xml = generate_meta_xml([
            {
                "role": "core",
                "row_type": "http://rs.tdwg.org/dwc/terms/Event",
                "filename": "event.txt",
                "fields": EVENT_FIELDS,
            },
            {
                "role": "extension",
                "row_type": "http://rs.tdwg.org/dwc/terms/Occurrence",
                "filename": "occurrence.txt",
                "fields": OCCURRENCE_FIELDS,
            },
            {
                "role": "extension",
                "row_type": "http://rs.gbif.org/terms/1.0/Multimedia",
                "filename": "multimedia.txt",
                "fields": MULTIMEDIA_FIELDS,
            },
        ])
        eml_xml = generate_eml_xml(self.project)

        zip_path = create_dwca_zip(
            {
                "event.txt": event_path,
                "occurrence.txt": occ_path,
                "multimedia.txt": multimedia_path,
            },
            meta_xml,
            eml_xml,
        )

        self.update_export_stats(file_temp_path=zip_path)
        return zip_path
    finally:
        for path in (event_path, occ_path, multimedia_path):
            try:
                os.unlink(path)
            except OSError:
                pass
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `docker compose run --rm django python manage.py test ami.exports.tests.DwCAExportTest --keepdb -v 2`
Expected: all tests pass, including new multimedia assertions and existing referential-integrity checks.

- [ ] **Step 7: Commit**

```bash
git add ami/exports/dwca/meta.py ami/exports/dwca/zip.py ami/exports/format_types.py ami/exports/tests.py
git commit -m "$(cat <<'EOF'
feat(exports): wire multimedia.txt into DwC-A archive

Generalize meta.xml descriptor and zip packager to accept arbitrary
extension lists, then add multimedia.txt as the third table.
Row type http://rs.gbif.org/terms/1.0/Multimedia (GBIF simple
Multimedia extension). Capture-image rows carry blank
occurrenceID; crop rows carry the occurrenceID URN so consumers
can link evidence back to determinations.

Co-Authored-By: Claude <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: `measurementorfact.txt` extension — catalogue, generator, wiring

**Why:** Structured numeric provenance: `classificationScore` per occurrence, `detectionScore` + `boundingBox` per detection. Extension coreid=eventID; `occurrenceID` column populated on both row types (all MoF rows are per-occurrence or per-detection in this PR — per-event rows are deferred).

**Files:**
- Modify: `ami/exports/dwca/fields.py` (add `MOF_FIELDS`)
- Modify: `ami/exports/dwca/rows.py` (`iter_mof_rows`)
- Modify: `ami/exports/format_types.py`
- Modify: `ami/exports/tests.py`

- [ ] **Step 1: Write the failing tests**

Add to `ami/exports/tests.py`:

```python
    def test_measurementorfact_txt_in_archive(self):
        with self._open_zip() as f:
            with zipfile.ZipFile(f, "r") as zf:
                self.assertIn("measurementorfact.txt", zf.namelist())
                data = zf.read("measurementorfact.txt").decode("utf-8")
                reader = csv.DictReader(StringIO(data), delimiter="\t")
                rows = list(reader)
                self.assertGreater(len(rows), 0)
                types = {r["measurementType"] for r in rows}
                self.assertIn("classificationScore", types)
                # Rows must all have populated coreid (=eventID)
                for r in rows:
                    self.assertTrue(r["eventID"], "MoF row missing eventID")
                    self.assertTrue(r["occurrenceID"], "MoF row missing occurrenceID in this PR")

    def test_meta_xml_declares_mof_extension(self):
        with self._open_zip() as f:
            with zipfile.ZipFile(f, "r") as zf:
                meta_xml = zf.read("meta.xml").decode("utf-8")
                self.assertIn("measurementorfact.txt", meta_xml)
                self.assertIn("http://rs.gbif.org/terms/1.0/MeasurementOrFact", meta_xml)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose run --rm django python manage.py test ami.exports.tests.DwCAExportTest.test_measurementorfact_txt_in_archive ami.exports.tests.DwCAExportTest.test_meta_xml_declares_mof_extension --keepdb -v 2`
Expected: FAIL — file not in archive.

- [ ] **Step 3: Add MOF_FIELDS to `fields.py`**

```python
MOF_FIELDS: list[DwCAField] = [
    DwCAField(DWC + "eventID", "eventID", lambda r, slug: r["eventID"], required=True),
    DwCAField(DWC + "occurrenceID", "occurrenceID", lambda r, slug: r.get("occurrenceID", "")),
    DwCAField(DWC + "measurementID", "measurementID", lambda r, slug: r.get("measurementID", "")),
    DwCAField(DWC + "measurementType", "measurementType", lambda r, slug: r["measurementType"], required=True),
    DwCAField(DWC + "measurementValue", "measurementValue", lambda r, slug: r.get("measurementValue", "")),
    DwCAField(DWC + "measurementUnit", "measurementUnit", lambda r, slug: r.get("measurementUnit", "")),
    DwCAField(
        DWC + "measurementDeterminedBy",
        "measurementDeterminedBy",
        lambda r, slug: r.get("measurementDeterminedBy", ""),
    ),
    DwCAField(
        DWC + "measurementRemarks",
        "measurementRemarks",
        lambda r, slug: r.get("measurementRemarks", ""),
    ),
]
```

Export from `__init__.py` (add import and `__all__`).

- [ ] **Step 4: Add `iter_mof_rows` to `rows.py`**

```python
import json


def iter_mof_rows(occurrences_qs, project_slug: str):
    """Yield dicts for measurementorfact.txt rows.

    Per-occurrence:
      - classificationScore (value = occurrence.determination_score, unit = proportion)

    Per-detection:
      - detectionScore (value = detection.detection_score)
      - boundingBox (value = JSON [x1,y1,x2,y2], unit = pixels)
    """
    for occ in occurrences_qs.select_related("determination").prefetch_related(
        "detections__detection_algorithm",
        "detections__classifications__algorithm",
    ):
        eid = _event_id(occ.event, project_slug) if occ.event_id else ""
        occ_urn = _occurrence_id(occ, project_slug)
        if eid and occ.determination_score is not None:
            yield {
                "eventID": eid,
                "occurrenceID": occ_urn,
                "measurementID": f"{occ_urn}:classificationScore",
                "measurementType": "classificationScore",
                "measurementValue": f"{occ.determination_score:.6f}",
                "measurementUnit": "proportion",
                "measurementDeterminedBy": _classifier_name(occ),
                "measurementRemarks": "ML classifier softmax score",
            }
        for det in occ.detections.all():
            det_urn = f"urn:ami:detection:{project_slug}:{det.id}"
            if det.detection_score is not None:
                yield {
                    "eventID": eid,
                    "occurrenceID": occ_urn,
                    "measurementID": f"{det_urn}:detectionScore",
                    "measurementType": "detectionScore",
                    "measurementValue": f"{det.detection_score:.6f}",
                    "measurementUnit": "proportion",
                    "measurementDeterminedBy": det.detection_algorithm.name if det.detection_algorithm else "",
                    "measurementRemarks": "ML detector confidence score",
                }
            if det.bbox:
                yield {
                    "eventID": eid,
                    "occurrenceID": occ_urn,
                    "measurementID": f"{det_urn}:boundingBox",
                    "measurementType": "boundingBox",
                    "measurementValue": json.dumps(det.bbox),
                    "measurementUnit": "pixels",
                    "measurementDeterminedBy": det.detection_algorithm.name if det.detection_algorithm else "",
                    "measurementRemarks": "Bounding box [x1, y1, x2, y2]",
                }


def _classifier_name(occurrence) -> str:
    """Best-effort: name + version of the classifier that produced this determination."""
    best = None
    for det in occurrence.detections.all():
        for cls in det.classifications.all():
            if cls.taxon_id == occurrence.determination_id:
                best = cls
                break
        if best:
            break
    if best and best.algorithm:
        name = best.algorithm.name or ""
        version = getattr(best.algorithm, "version", "") or ""
        return f"{name} {version}".strip()
    return ""
```

- [ ] **Step 5: Wire into `DwCAExporter.export()`**

In `ami/exports/format_types.py`, extend the `export()` method from Task 6, Step 5:

1. Add `from ami.exports.dwca.fields import MOF_FIELDS` and `from ami.exports.dwca.rows import iter_mof_rows`.
2. Create `mof_path = _tmp_txt()`.
3. After the multimedia write, add:
   ```python
   mof_count = write_tsv(
       mof_path,
       MOF_FIELDS,
       iter_mof_rows(self.queryset, project_slug),
       project_slug,
   )
   logger.info(f"DwC-A: wrote {mof_count} measurementOrFact rows")
   ```
4. Add a fourth entry to the `generate_meta_xml` list:
   ```python
   {
       "role": "extension",
       "row_type": "http://rs.gbif.org/terms/1.0/MeasurementOrFact",
       "filename": "measurementorfact.txt",
       "fields": MOF_FIELDS,
   },
   ```
5. Add `"measurementorfact.txt": mof_path,` to the `create_dwca_zip` files dict.
6. Add `mof_path` to the cleanup tuple.

- [ ] **Step 6: Run tests to verify they pass**

Run: `docker compose run --rm django python manage.py test ami.exports.tests.DwCAExportTest --keepdb -v 2`
Expected: all pass, including 2 new MoF assertions.

- [ ] **Step 7: Commit**

```bash
git add ami/exports/dwca/fields.py ami/exports/dwca/rows.py ami/exports/dwca/__init__.py ami/exports/format_types.py ami/exports/tests.py
git commit -m "$(cat <<'EOF'
feat(exports): add measurementorfact.txt extension

Captures ML provenance as structured numeric facts:
classificationScore per occurrence, detectionScore + boundingBox
per detection. Row type http://rs.gbif.org/terms/1.0/MeasurementOrFact,
coreid=eventID, occurrenceID column linking back to the occurrence.

Per-event MoF rows (lux, temperature, moon phase) are not emitted
in this PR; the column layout reserves space for them.

Co-Authored-By: Claude <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: Upgrade EML 2.1.1 → 2.2.0 with computed coverage and methods

**Why:** EML 2.2.0 is the current ratified version and what GBIF expects. Compute geographic/temporal coverage from the actual event data + document sampling protocol explicitly in `methods`.

**Files:**
- Modify: `ami/exports/dwca/eml.py`
- Modify: `ami/exports/format_types.py` (pass events to `generate_eml_xml`)
- Modify: `ami/exports/tests.py`

- [ ] **Step 1: Write the failing test**

Replace the existing `test_eml_xml_valid` in `DwCAExportTest` with an expanded version:

```python
    def test_eml_xml_valid(self):
        """eml.xml should be valid EML 2.2.0 with coverage, methods, and license."""
        with self._open_zip() as f:
            with zipfile.ZipFile(f, "r") as zf:
                eml_xml = zf.read("eml.xml").decode("utf-8")
                root = ET.fromstring(eml_xml)

                # EML 2.2.0 namespace
                self.assertIn("eml-2.2.0", eml_xml)
                ns = {"eml": "https://eml.ecoinformatics.org/eml-2.2.0"}
                dataset = root.find("eml:dataset", ns)
                self.assertIsNotNone(dataset, "eml.xml missing <dataset>")

                # Title matches project name
                title = dataset.find("eml:title", ns)
                self.assertIsNotNone(title)
                self.assertEqual(title.text, self.project.name)

                # Coverage: bounding box + temporal
                coverage = dataset.find("eml:coverage", ns)
                self.assertIsNotNone(coverage, "Missing <coverage>")
                self.assertIsNotNone(coverage.find(".//eml:geographicCoverage", ns))
                self.assertIsNotNone(coverage.find(".//eml:temporalCoverage", ns))

                # Methods section
                methods = dataset.find("eml:methods", ns)
                self.assertIsNotNone(methods, "Missing <methods>")
                method_step = methods.find("eml:methodStep", ns)
                self.assertIsNotNone(method_step)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose run --rm django python manage.py test ami.exports.tests.DwCAExportTest.test_eml_xml_valid --keepdb -v 2`
Expected: FAIL — namespace mismatch, missing `<coverage>` and `<methods>`.

- [ ] **Step 3: Rewrite `ami/exports/dwca/eml.py`**

```python
"""Generate EML 2.2.0 metadata for the DwC-A."""

from __future__ import annotations

from xml.etree import ElementTree as ET

from django.utils import timezone
from django.utils.text import slugify

EML_NS = "https://eml.ecoinformatics.org/eml-2.2.0"
XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"


def generate_eml_xml(project, events=None) -> str:
    """Return the eml.xml body.

    If `events` is provided (iterable of Event), geographic and temporal
    coverage are computed from it. If absent, they're omitted.
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
    sampling_description = ET.SubElement(sampling, "studyExtent")
    _add_text(sampling_description, "description", "See <coverage> for geographic and temporal extent.")
    _add_text(sampling, "samplingDescription", "Automated overnight monitoring with continuous image capture.")
    qc = ET.SubElement(methods, "qualityControl")
    qc_description = ET.SubElement(qc, "description")
    _add_text(
        qc_description,
        "para",
        "Project default filters applied before export: score thresholds, include/exclude taxa "
        "lists, soft-delete exclusion. Only occurrences with at least one detection are included.",
    )
```

- [ ] **Step 4: Pass events into `generate_eml_xml` from the exporter**

In `DwCAExporter.export()`, change:
```python
eml_xml = generate_eml_xml(self.project)
```
to:
```python
eml_xml = generate_eml_xml(self.project, events_list)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `docker compose run --rm django python manage.py test ami.exports.tests.DwCAExportTest --keepdb -v 2`
Expected: all pass, including the rewritten EML test.

- [ ] **Step 6: Commit**

```bash
git add ami/exports/dwca/eml.py ami/exports/format_types.py ami/exports/tests.py
git commit -m "$(cat <<'EOF'
feat(exports): upgrade eml.xml to EML 2.2.0 with coverage and methods

Bumps namespace and schemaLocation to eml-2.2.0. Adds computed
geographicCoverage (bbox from event deployment coordinates),
temporalCoverage (min/max event start), and a methods section
documenting the automated capture + ML pipeline workflow and
the quality-control filters applied at export time.

Co-Authored-By: Claude <noreply@anthropic.com>
EOF
)"
```

---

## Task 9: Extend validator to cover multimedia.txt and MoF; add occurrenceID cross-ref check

**Why:** The new extensions introduce referential semantics (crop rows must point at real occurrenceIDs; MoF rows must too). These invariants aren't caught by normal tests because they're structural.

**Files:**
- Modify: `ami/exports/dwca_validator.py`
- Modify: `ami/exports/tests_dwca_validator.py`

- [ ] **Step 1: Write the failing tests**

Append to `ami/exports/tests_dwca_validator.py`:

```python
def test_validator_detects_orphaned_occurrence_id_on_extension_row(tmp_path):
    """A multimedia row whose occurrenceID isn't in occurrence.txt should error."""
    import csv
    import zipfile
    from ami.exports.dwca_validator import validate_dwca_zip

    zip_path = tmp_path / "bad.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("meta.xml", _MINIMAL_META_WITH_MULTIMEDIA)
        zf.writestr("eml.xml", "<eml/>")
        zf.writestr("event.txt", "eventID\tdecimalLatitude\tdecimalLongitude\nE1\t45\t-73\n")
        zf.writestr("occurrence.txt", "eventID\toccurrenceID\tbasisOfRecord\nE1\tO1\tMachineObservation\n")
        zf.writestr(
            "multimedia.txt",
            "eventID\toccurrenceID\tidentifier\nE1\tO_MISSING\thttp://example.com/a.jpg\n",
        )
    result = validate_dwca_zip(str(zip_path))
    assert not result.ok
    assert any("occurrenceID" in e for e in result.errors)


_MINIMAL_META_WITH_MULTIMEDIA = """<?xml version='1.0' encoding='UTF-8'?>
<archive xmlns="http://rs.tdwg.org/dwc/text/" metadata="eml.xml">
  <core rowType="http://rs.tdwg.org/dwc/terms/Event" encoding="UTF-8" fieldsTerminatedBy="\\t" linesTerminatedBy="\\n" fieldsEnclosedBy="&quot;" ignoreHeaderLines="1">
    <files><location>event.txt</location></files>
    <id index="0"/>
    <field index="0" term="http://rs.tdwg.org/dwc/terms/eventID"/>
    <field index="1" term="http://rs.tdwg.org/dwc/terms/decimalLatitude"/>
    <field index="2" term="http://rs.tdwg.org/dwc/terms/decimalLongitude"/>
  </core>
  <extension rowType="http://rs.tdwg.org/dwc/terms/Occurrence" encoding="UTF-8" fieldsTerminatedBy="\\t" linesTerminatedBy="\\n" fieldsEnclosedBy="&quot;" ignoreHeaderLines="1">
    <files><location>occurrence.txt</location></files>
    <coreid index="0"/>
    <field index="0" term="http://rs.tdwg.org/dwc/terms/eventID"/>
    <field index="1" term="http://rs.tdwg.org/dwc/terms/occurrenceID"/>
    <field index="2" term="http://rs.tdwg.org/dwc/terms/basisOfRecord"/>
  </extension>
  <extension rowType="http://rs.gbif.org/terms/1.0/Multimedia" encoding="UTF-8" fieldsTerminatedBy="\\t" linesTerminatedBy="\\n" fieldsEnclosedBy="&quot;" ignoreHeaderLines="1">
    <files><location>multimedia.txt</location></files>
    <coreid index="0"/>
    <field index="0" term="http://rs.tdwg.org/dwc/terms/eventID"/>
    <field index="1" term="http://rs.tdwg.org/dwc/terms/occurrenceID"/>
    <field index="2" term="http://purl.org/dc/terms/identifier"/>
  </extension>
</archive>
"""
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose run --rm django python -m pytest ami/exports/tests_dwca_validator.py::test_validator_detects_orphaned_occurrence_id_on_extension_row -v`
Expected: FAIL — validator doesn't cross-check occurrenceID yet.

- [ ] **Step 3: Extend validator**

In `ami/exports/dwca_validator.py`, modify `validate_dwca_zip` to additionally:
1. Collect occurrenceID values from the Occurrence extension (if present)
2. For any other extension that declares a `dwc:occurrenceID` field, verify each non-blank value exists in that set

Add this block at the end of the existing loop, right after the existing `_validate_extension` call:

```python
        occurrence_ids = _collect_occurrence_ids(zf, tables)
        for ext in tables[1:]:
            if ext.filename == "occurrence.txt":
                continue
            _validate_occurrence_id_references(zf, ext, occurrence_ids, result)
```

And two helpers at module level:

```python
_OCCURRENCE_ID_TERM = "http://rs.tdwg.org/dwc/terms/occurrenceID"


def _collect_occurrence_ids(zf: zipfile.ZipFile, tables: list[_TableSpec]) -> set[str]:
    for t in tables:
        if t.filename == "occurrence.txt":
            rows = _read_tsv(zf, t.filename, ValidationResult())
            if rows is None:
                return set()
            occ_col = None
            for idx, term in t.field_terms.items():
                if term == _OCCURRENCE_ID_TERM:
                    occ_col = idx
                    break
            if occ_col is None:
                return set()
            return {row[occ_col].strip() for row in rows[1:] if occ_col < len(row) and row[occ_col].strip()}
    return set()


def _validate_occurrence_id_references(
    zf: zipfile.ZipFile,
    ext: _TableSpec,
    occurrence_ids: set[str],
    result: ValidationResult,
) -> None:
    occ_col = None
    for idx, term in ext.field_terms.items():
        if term == _OCCURRENCE_ID_TERM:
            occ_col = idx
            break
    if occ_col is None:
        return
    rows = _read_tsv(zf, ext.filename, result)
    if rows is None:
        return
    missing: set[str] = set()
    for row in rows[1:]:
        if occ_col >= len(row):
            continue
        val = row[occ_col].strip()
        if val and val not in occurrence_ids:
            missing.add(val)
    if missing:
        sample = sorted(missing)[:5]
        result.add_error(
            f"{ext.filename}: {len(missing)} occurrenceID value(s) do not exist in occurrence.txt. "
            f"First: {sample}"
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `docker compose run --rm django python -m pytest ami/exports/tests_dwca_validator.py -v`
Expected: all validator tests pass, including the new one.

- [ ] **Step 5: Commit**

```bash
git add ami/exports/dwca_validator.py ami/exports/tests_dwca_validator.py
git commit -m "$(cat <<'EOF'
feat(exports): validate occurrenceID cross-references between extensions

Any extension that declares a dwc:occurrenceID column must only
contain values that exist in occurrence.txt. Multimedia crop rows
and MoF rows both carry occurrenceID as a back-link; this check
catches drift where the pipeline emits rows pointing at filtered-
out or non-existent occurrences.

Co-Authored-By: Claude <noreply@anthropic.com>
EOF
)"
```

---

## Task 10: Run the validator before zipping; fail fast on structural errors

**Why:** Design says "Fatal errors fail the export and mark `DataExport.status = FAILED`." Best to catch drift before users download broken archives.

**Files:**
- Modify: `ami/exports/format_types.py`
- Modify: `ami/exports/tests.py`

- [ ] **Step 1: Write the failing test**

Add to `DwCAExportTest`:

```python
    def test_validator_runs_on_produced_zip(self):
        """The exporter's own zip should pass its own validator cleanly."""
        from ami.exports.dwca_validator import validate_dwca_zip

        with self._open_zip() as f:
            # Write cached zip to a tempfile the validator can reopen.
            import tempfile
            tf = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
            tf.write(f.read())
            tf.close()
            result = validate_dwca_zip(tf.name)
        self.assertTrue(
            result.ok,
            f"Self-produced DwC-A failed own validator: {result.errors}",
        )
```

- [ ] **Step 2: Add runtime validation step in the exporter**

In `DwCAExporter.export()` in `ami/exports/format_types.py`, right after `zip_path = create_dwca_zip(...)`:

```python
        from ami.exports.dwca_validator import validate_dwca_zip

        validation = validate_dwca_zip(zip_path)
        for warning in validation.warnings:
            logger.warning(f"DwC-A validation warning: {warning}")
        if not validation.ok:
            for err in validation.errors:
                logger.error(f"DwC-A validation error: {err}")
            raise ValueError(
                f"DwC-A archive failed structural validation ({len(validation.errors)} errors). "
                f"First: {validation.errors[0]}"
            )
```

- [ ] **Step 3: Run test to verify it passes**

Run: `docker compose run --rm django python manage.py test ami.exports.tests.DwCAExportTest --keepdb -v 2`
Expected: all pass.

- [ ] **Step 4: Commit**

```bash
git add ami/exports/format_types.py ami/exports/tests.py
git commit -m "$(cat <<'EOF'
feat(exports): validate DwC-A archive structure before returning

Run the offline structural validator against the zip the exporter
just produced. Fatal errors raise, which is caught by the export
framework and flips DataExport.status to FAILED. Warnings log.

Prevents users downloading broken archives where meta.xml, TSV
columns, or cross-references have silently drifted.

Co-Authored-By: Claude <noreply@anthropic.com>
EOF
)"
```

---

## Task 11: UI — register `dwca` as an export type with the April-2026-Draft label

**Why:** Users can't choose the format from the UI until it's in `SERVER_EXPORT_TYPES`. Label must clearly signal "draft" so early testers know what they have.

**Files:**
- Modify: `ui/src/data-services/models/export.ts`

- [ ] **Step 1: Update `SERVER_EXPORT_TYPES` and the label map**

Replace lines 6-36 of `ui/src/data-services/models/export.ts` with:

```typescript
export const SERVER_EXPORT_TYPES = [
  'occurrences_simple_csv',
  'occurrences_api_json',
  'dwca',
] as const

export type ServerExportType = (typeof SERVER_EXPORT_TYPES)[number]

export type ServerExport = any // TODO: Update this type

export class Export extends Entity {
  public readonly job?: Job

  public constructor(entity: ServerExport) {
    super(entity)

    if (this._data.job) {
      this.job = new JobDetails(this._data.job)
    }
  }

  static getExportTypeInfo(key: ServerExportType) {
    const label = {
      occurrences_simple_csv: 'Occurrences (simple CSV)',
      occurrences_api_json: 'Occurrences (API JSON)',
      dwca: 'Darwin Core Archive (DwC-A) — April 2026 Draft',
    }[key]

    return {
      key,
      label,
    }
  }
```

- [ ] **Step 2: Build to verify no TypeScript errors**

Run: `cd ui && yarn build`
Expected: build succeeds with no new errors referencing `export.ts`.

- [ ] **Step 3: Commit**

```bash
git add ui/src/data-services/models/export.ts
git commit -m "$(cat <<'EOF'
feat(ui): expose dwca as a user-selectable export format

Labels the format 'Darwin Core Archive (DwC-A) — April 2026 Draft'
so scientists testing the export know what they're looking at
before GBIF-registration and scheme stabilization.

Co-Authored-By: Claude <noreply@anthropic.com>
EOF
)"
```

---

## Task 12: Update format reference doc

**Files:**
- Modify: `docs/claude/dwca-format-reference.md`

- [ ] **Step 1: Rewrite the "Archive contents" section**

Replace the archive-contents description in `docs/claude/dwca-format-reference.md` with:

```markdown
## Archive contents

```
project_export.zip
├── meta.xml                   DwC-A text-archive descriptor
├── eml.xml                    EML 2.2.0 dataset metadata
├── event.txt                  Core — Event row per AMI Event, with
│                                Humboldt eco: columns flattened in
├── occurrence.txt             Extension — coreid=eventID, one row per
│                                published Occurrence. associatedMedia
│                                column carries pipe-separated capture URLs.
├── multimedia.txt             Extension — coreid=eventID. Two row types:
│                                - capture rows (occurrenceID blank)
│                                - detection-crop rows (occurrenceID populated)
└── measurementorfact.txt      Extension — coreid=eventID. Per-occurrence
                                 classificationScore; per-detection
                                 detectionScore and boundingBox.
```

## Humboldt Extension columns on event.txt

| Column | Term | Source |
|---|---|---|
| isSamplingEffortReported | eco:isSamplingEffortReported | constant `true` |
| samplingEffortValue | eco:samplingEffortValue | `Event.captures_count` |
| samplingEffortUnit | eco:samplingEffortUnit | constant `images` |
| samplingEffortProtocol | eco:samplingEffortProtocol | constant protocol description |
| isAbsenceReported | eco:isAbsenceReported | constant `true` (per-taxon rows deferred) |
| targetTaxonomicScope | eco:targetTaxonomicScope | LCA of `Project.default_filters_include_taxa` |
| inventoryTypes | eco:inventoryTypes | constant `trap or sample` |
| protocolNames | eco:protocolNames | constant `AMI ML detector + classifier pipeline` |
| protocolDescriptions | eco:protocolDescriptions | constant pipeline description |
| hasMaterialSamples | eco:hasMaterialSamples | constant `true` |
| materialSampleTypes | eco:materialSampleTypes | constant `digital images` |
```

- [ ] **Step 2: Commit**

```bash
git add docs/claude/dwca-format-reference.md
git commit -m "$(cat <<'EOF'
docs(exports): update DwC-A format reference for April 2026 draft

Documents the four-file archive shape, Humboldt eco: columns on
event.txt, and the source of each constant/derived value.

Co-Authored-By: Claude <noreply@anthropic.com>
EOF
)"
```

---

## Self-Review

After all 12 tasks are implemented, run the full test suite and confirm:

```bash
docker compose -f docker-compose.ci.yml run --rm django python manage.py test ami.exports --keepdb -v 2
```

Expected: existing 10 DwC-A tests pass, plus the new tests:
- 3 in `TargetTaxonomicScopeTest`
- 2 in `MultimediaExtensionTest`
- 7 net-new in `DwCAExportTest` (humboldt cols, humboldt meta.xml, associatedMedia, multimedia in archive, multimedia meta.xml, MoF in archive, MoF meta.xml, validator self-check — replaced/modified eml test)
- 1 in `tests_dwca_validator.py`

Also manually inspect a sample zip produced by a real project (`docker compose exec django python manage.py shell` → create + run a DwCAExporter), unzip it, and spot-check:
- `event.txt` has Humboldt columns populated
- `multimedia.txt` has both capture and crop rows
- `measurementorfact.txt` has classificationScore rows
- `eml.xml` references `eml-2.2.0` and has non-empty `<coverage>` / `<methods>`
- `meta.xml` declares four tables

## Deferred (follow-up PRs / tracked elsewhere)

The following items from the design doc are intentionally not in this plan and are documented as follow-ups in the PR body or tickets:

- `is_blank` / `contains_humans` source-image filters (fields don't exist in the model yet; design doc flags this as a WG requirement but implementation depends on upstream work)
- Per-taxon absence occurrence rows (pending `Site.primary_taxa_list` design)
- Device model additions (`device_type`, `attractant_type`, `light_wavelength`) → handled by CamtrapDP PR (#1262)
- CamtrapDP native export → #1262
- Sensitive-taxa coordinate generalization
- Reverse-geocoding for country / state / locality
- `coordinateUncertaintyInMeters` (needs Deployment field)
- Online GBIF-API validator CI
- IPT publishing + DOI minting
- PR-body multimedia/bbox discussion comment (write after Task 7 merges, not part of the code plan)

---

## Execution choice

Plan complete and saved to `docs/claude/planning/2026-04-21-dwca-implementation-plan.md`. Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?
