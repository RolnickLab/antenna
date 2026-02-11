# Plan: Add DwC-A (Darwin Core Archive) Export Format

## Why

AMI projects produce biodiversity occurrence data (species observations from automated insect monitoring stations). To make this data discoverable and citable in the global biodiversity research community, it needs to be published to GBIF (Global Biodiversity Information Facility). GBIF's standard ingestion format is the Darwin Core Archive (DwC-A).

**Roadmap:**
1. **This PR** — Static DwC-A export: user triggers an export, downloads a ZIP file. Validates against GBIF's data validator. Serves as the foundation for all downstream GBIF integration.
2. **Near follow-up** — Enrich the archive with additional DwC extensions (multimedia, measurement/fact) and a more complete EML metadata profile. Apply project default filters to the export.
3. **Eventual** — Automated publishing: either push archives to a hosted GBIF IPT (Integrated Publishing Toolkit) server, or implement the IPT's RSS/DwC-A endpoint protocol directly within Antenna so it can act as its own IPT, serving a feed that GBIF crawls on a schedule.

## Context

The export framework already exists (`ami/exports/`) with JSON and CSV formats registered via a simple registry pattern. Adding a new format requires: an exporter class, field mappings, and a one-line registration. The `DataExport` model and async job infrastructure handle storage, progress tracking, and file serving.

**Decisions made:**
- **Event-core architecture** (events as core, occurrences as extension) — This matches AMI's data model (monitoring sessions containing species observations) and is the recommended GBIF pattern for sampling-event datasets, which enables richer ecological analysis than occurrence-only archives.
- **URN format for IDs**: `urn:ami:event:{project_slug}:{id}`, `urn:ami:occurrence:{project_slug}:{id}` — Globally unique, stable, and human-readable. The project slug provides namespacing across AMI instances.
- **Coordinates from Deployment lat/lon only** (text locality fields like country/stateProvince deferred) — Deployments store coordinates; reverse geocoding for text fields is a separate concern.
- **`basisOfRecord` = `"MachineObservation"`** — GBIF's standard term for automated/sensor-derived observations, distinct from `HumanObservation`.
- **No DRF serializer** — DwC fields are flat extractions, not nested API representations. Direct TSV writing is simpler and faster.
- **Taxonomy from `parents_json`** — Avoids N+1 parent chain queries by walking the pre-computed `parents_json` list on each Taxon.

## Implementation Steps

### Step 1: Create DwC-A exporter class

**File:** `ami/exports/format_types.py` (add to existing file)

Create `DwCAExporter(BaseExporter)` with:
- `file_format = "zip"`
- `export()` method that orchestrates the full pipeline:
  1. Write `event.txt` (tab-delimited) from Event queryset
  2. Write `occurrence.txt` (tab-delimited) from Occurrence queryset
  3. Generate `meta.xml`
  4. Generate `eml.xml`
  5. Package all into a ZIP, return temp file path

**Querysets:**
- Events: `Event.objects.filter(project=self.project)` with `select_related('deployment', 'deployment__research_site')`
- Occurrences: `Occurrence.objects.valid().filter(project=self.project)` with `select_related('determination', 'event', 'deployment')` and `.with_timestamps().with_detections_count()`

**Override `get_filter_backends()`** to return backends appropriate for events+occurrences (or empty list if collection filtering doesn't apply to events).

### Step 2: Define DwC field mappings

**File:** `ami/exports/dwca.py` (new file)

Contains:
- `EVENT_FIELDS`: ordered list of `(dwc_term_uri, header_name, getter_function)` tuples
- `OCCURRENCE_FIELDS`: same structure
- Helper functions to extract taxonomy hierarchy from `determination.parents_json` (walk the `list[TaxonParent]` for kingdom, phylum, class, order, family, genus)
- `get_specific_epithet(name)` - split binomial to get second word
- `generate_meta_xml(event_fields, occurrence_fields, event_filename, occurrence_filename)` - builds the XML string
- `generate_eml_xml(project, events_queryset)` - builds minimal EML metadata from project info

**Event field mapping (event.txt):**

| Column | DwC Term | Source |
|--------|----------|--------|
| 0 | eventID | `urn:ami:event:{project_slug}:{event.id}` |
| 1 | eventDate | `event.start`/`event.end` as ISO date interval |
| 2 | eventTime | time portion of `event.start` |
| 3 | year | from `event.start` |
| 4 | month | from `event.start` |
| 5 | day | from `event.start` |
| 6 | samplingProtocol | `"automated light trap with camera"` (constant, could be project-level setting later) |
| 7 | sampleSizeValue | `event.captures_count` |
| 8 | sampleSizeUnit | `"images"` |
| 9 | samplingEffort | duration formatted |
| 10 | locationID | `deployment.name` |
| 11 | decimalLatitude | `deployment.latitude` |
| 12 | decimalLongitude | `deployment.longitude` |
| 13 | geodeticDatum | `"WGS84"` |
| 14 | datasetName | `project.name` |
| 15 | modified | `event.updated_at` ISO format |

**Occurrence field mapping (occurrence.txt):**

| Column | DwC Term | Source |
|--------|----------|--------|
| 0 | eventID | same URN as core (foreign key) |
| 1 | occurrenceID | `urn:ami:occurrence:{project_slug}:{occurrence.id}` |
| 2 | basisOfRecord | `"MachineObservation"` |
| 3 | occurrenceStatus | `"present"` |
| 4 | scientificName | `determination.name` |
| 5 | taxonRank | `determination.rank` (lowercase) |
| 6 | kingdom | from `determination.parents_json` |
| 7 | phylum | from `determination.parents_json` |
| 8 | class | from `determination.parents_json` |
| 9 | order | from `determination.parents_json` |
| 10 | family | from `determination.parents_json` |
| 11 | genus | from `determination.parents_json` |
| 12 | specificEpithet | second word of species name |
| 13 | vernacularName | `determination.common_name_en` |
| 14 | taxonID | `determination.gbif_taxon_key` (if available) |
| 15 | individualCount | `detections_count` |
| 16 | identificationVerificationStatus | "verified" if identifications exist, else "unverified" |
| 17 | modified | `occurrence.updated_at` ISO format |

### Step 3: Register the exporter

**File:** `ami/exports/registry.py`

Add: `ExportRegistry.register("dwca")(DwCAExporter)`

This is all that's needed for it to appear in the API's valid format choices.

### Step 4: Override `generate_filename()` behavior

The `DataExport.generate_filename()` uses `exporter.file_format` for the extension. Since `file_format = "zip"`, the filename will be `{project_slug}_export-{pk}.zip` which is correct.

No changes needed to `DataExport` model.

### Step 5: Write tests

**File:** `ami/exports/tests.py` (add to existing)

- Test that `DwCAExporter` is registered and retrievable
- Test that export produces a valid ZIP with expected files (event.txt, occurrence.txt, meta.xml, eml.xml)
- Test that event.txt has correct headers and row count matches events
- Test that occurrence.txt has correct headers and row count matches valid occurrences
- Test that meta.xml is valid XML with correct core/extension structure
- Test that all occurrence eventIDs reference existing event eventIDs (referential integrity)
- Test taxonomy hierarchy extraction from `parents_json`

### Step 6: Update documentation

**File:** `docs/claude/dwca-format-reference.md` (already created, update with final field mappings)

## Key Files to Modify

| File | Action |
|------|--------|
| `ami/exports/dwca.py` | **New** - DwC field mappings, meta.xml/eml.xml generators, taxonomy helpers |
| `ami/exports/format_types.py` | **Modify** - Add `DwCAExporter` class |
| `ami/exports/registry.py` | **Modify** - Register `"dwca"` format |
| `ami/exports/tests.py` | **Modify** - Add DwC-A tests |

## Key Files to Read (not modify)

| File | Why |
|------|-----|
| `ami/exports/base.py` | BaseExporter interface |
| `ami/exports/models.py` | DataExport model, run_export() flow |
| `ami/exports/utils.py` | get_data_in_batches(), generate_fake_request() |
| `ami/main/models.py:1025` | Event model fields |
| `ami/main/models.py:2808` | Occurrence model fields |
| `ami/main/models.py:3329` | TaxonParent pydantic model (parents_json schema) |
| `ami/main/models.py:3349` | Taxon model fields |
| `docs/claude/reference/example_dwca_exporter.md` | Reference DwC-A implementation |

## Design Decisions

1. **No DRF serializer for DwC-A** - Unlike JSON/CSV exporters that use DRF serializers via `get_data_in_batches()`, the DwC-A exporter writes TSV directly. DwC fields are simple extractions, not nested API representations. This avoids the overhead of serializer instantiation per record.

2. **Direct queryset iteration** - Use `queryset.iterator(chunk_size=500)` for memory efficiency, writing rows directly to the TSV file.

3. **Taxonomy from parents_json** - Walk the `parents_json` list (which contains `{id, name, rank}` dicts) to extract kingdom/phylum/class/order/family/genus. This avoids N+1 queries on the Taxon parent chain.

4. **meta.xml generated from field definitions** - The same field list used for writing TSV columns also drives meta.xml generation, ensuring they stay in sync.

5. **Minimal eml.xml** - Start with project name, description, and owner. Can be enriched later with geographic bounding box, temporal coverage, etc.

6. **Scope for follow-up** - Species checklist (taxon.txt) and multimedia extension (multimedia.txt) are explicitly out of scope for this PR, as stated in the task.

## Verification

1. Run existing export tests to ensure no regression: `docker compose run --rm django python manage.py test ami.exports`
2. Run new DwC-A tests
3. Manual test: create a DwC-A export via the API or admin, download the ZIP, inspect contents
4. Validate with GBIF Data Validator: https://www.gbif.org/tools/data-validator
