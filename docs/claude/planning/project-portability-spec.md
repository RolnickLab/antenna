# Project Portability: Export/Import with UUIDs and Natural Keys

**Date:** 2026-03-26
**Status:** Draft — pending research and validation
**Authors:** Michael, Claude

## Motivation

Antenna projects need to be portable between Django environments for two primary use cases:

1. **Instance migration** — Moving projects from one Antenna deployment to another (e.g., self-hosted → managed, or between collaborating institutions). ID clashes between instances must be handled.
2. **Production → dev/staging** — Cloning real project data into development environments for testing. The target DB can be wiped first, so ID clashes are less of a concern.

A secondary goal is to improve user-facing exports (CSV, JSON, Darwin Core) by establishing stable, human-readable identifiers across the system.

## Design Overview

Three interconnected changes:

1. **UUID fields** on all models — stable cross-instance identifiers
2. **Organization model** — lightweight namespace for projects
3. **Export/import management commands** — serialize and restore full project graphs
4. **Natural key methods** — for Django serialization and human-readable exports

## 1. UUID Fields

### Principle: integer PKs stay internal, UUIDs are external identity

Every model in the export graph gets:

```python
uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
```

Integer PKs remain the primary key. This is deliberate:

- Django's FK system, joins, and indexing are optimized for integers
- All existing queries, admin URLs, Celery task arguments, and internal references continue unchanged
- Integer PKs are 8 bytes; UUIDs are 16 bytes — this matters on tables with millions of rows and FK-heavy joins (Detection, Classification)
- Changing PK type on large tables with existing FK references is a dangerous, multi-step migration

### When to use which

| Context | Use |
|---|---|
| Database ForeignKey fields | Integer PK |
| Database joins, indexes, internal queries | Integer PK |
| Django admin URLs | Integer PK |
| Celery task arguments | Integer PK |
| Export/import serialization | UUID |
| User-facing CSV/JSON exports | UUID |
| Darwin Core `occurrenceID`, `eventID`, etc. | UUID |
| Cross-instance data matching | UUID |
| Future external API identifiers | UUID (via DRF `lookup_field`) |

### DB constraints

- `UNIQUE` constraint on `uuid` — enforced at database level
- `db_index=True` — implicit from `unique=True`
- `default=uuid.uuid4` — auto-generated on creation
- `editable=False` — immutable once set
- Backfill migration generates UUIDs for all existing rows

### Models receiving UUID fields, with known use cases

Each model's UUID serves export/import portability. The table below documents additional known use cases beyond that baseline.

**Project-scoped (included in project exports):**

| Model | Known UUID use cases |
|---|---|
| **Organization** (new) | Namespace for projects across instances. Future: org-level API access, multi-tenant routing. |
| **Project** | Cross-instance project identity. Enables "this is the same project on staging and prod" matching. Future: project-level API tokens scoped to UUID. |
| **Deployment** | Deployment identity across instances and external systems. Deployments represent physical monitoring stations — the same station may be referenced in publications, field logs, and partner databases. A UUID gives it a stable external reference. Darwin Core: maps to `locationID`. |
| **Event** | Temporal capture session identity. Darwin Core: maps to `eventID`. Events can be referenced in publications ("the June 14-15 2023 capture session at Kuujjuaq"). |
| **SourceImage** | Image identity across instances. When the same S3 bucket is accessible from multiple Antenna instances, UUID prevents duplicate processing. Also useful for cross-referencing images in external annotation tools (Label Studio, CVAT). |
| **Detection** | Detection identity for ML pipeline reproducibility. When comparing results across pipeline versions or instances, UUID lets you track "this exact bounding box crop" across systems. Crop images can be regenerated from `(source_image, bbox)` but the UUID tracks the detection record itself. |
| **Classification** | Classification identity for audit trails. Each classification is an immutable record of "algorithm X said taxon Y with score Z for detection D." UUID enables cross-referencing classification provenance across instances. |
| **Occurrence** | **Primary external-facing identifier.** Darwin Core: maps to `occurrenceID` — must be globally unique and persistent. Published to GBIF. Referenced in research papers, datasets, and partner databases. This is the most important UUID in the system. |
| **Identification** | Human review audit trail. Darwin Core: maps to `identificationID`. Each identification records a human expert's taxonomic opinion. UUID enables tracking identification history across instance migrations. |
| **Device** | Hardware identity. The same physical AMI trap may be deployed across projects and tracked across institutions. UUID lets you say "this is the same physical device" even when it moves between projects. |
| **Site** | Research site identity. Same site may appear in multiple projects and external databases. Darwin Core: related to `locationID` and `locality`. |
| **S3StorageSource** | Storage configuration identity. When migrating instances, the UUID confirms "this export references the same S3 bucket configuration." |
| **SourceImageCollection** | Collection identity for reproducible subsets. Collections define curated image sets for specific processing jobs. UUID enables referencing "process this exact collection" across instances. |
| **Tag** | Tag identity within a project. Tags are project-scoped labels applied to taxa. UUID ensures tag references survive export/import. |
| **TaxaList** | Curated taxa list identity. TaxaLists are shared across projects and define taxa subsets for filtering. UUID enables consistent list references. |
| **Job** | Job identity for audit and reproducibility. Historical record of "pipeline X was run on deployment Y at time Z." UUID enables cross-referencing job provenance across instances. |
| **DataExport** | Export record identity. Less critical — primarily for audit trail of what was exported when. |
| **Pipeline** | **Critical for ML service coordination.** Pipelines are currently matched between Antenna and external processing services by **slug** (`get_or_create(slug=results.pipeline)`). This creates collision risk: two different pipelines with the same slug (e.g., `panama_moths_2024`) on different processing services can clash, causing half of a job's images to be processed by the wrong pipeline. UUID provides unambiguous pipeline identity across Antenna instances and processing services. The slug remains the human-readable label; the UUID becomes the coordination identifier. |
| **Algorithm** | **Critical for ML reproducibility.** Algorithms are currently matched by `(name, version)` from processing service `/info` responses. Same collision risk as pipelines — two different model checkpoints shipped as the same `(name, version)` by different services. UUID provides unambiguous algorithm identity for tracking which exact model produced which detections/classifications. Essential for scientific reproducibility. |
| **ProcessingService** | Service endpoint identity. Less critical since services are instance-local, but UUID helps when migrating processing service configurations between instances. |
| **ProjectPipelineConfig** | Through-model for Pipeline↔Project M2M. UUID useful for config identity in export/import. |

**Shared/global (referenced in exports but not project-scoped):**

| Model | Known UUID use cases |
|---|---|
| **Taxon** | Taxonomy identity. Matched by `name` on import (taxa are shared across projects). UUID useful for Darwin Core `taxonID` and cross-referencing with external taxonomic databases. Note: taxonomy names can change (synonymization, reclassification), so `name` as natural key has known limitations. |
| **User** | User identity. Matched by `email` on import. UUID useful for anonymized exports where email should not be exposed but user identity needs to be preserved. |

## 2. Organization Model

Lightweight namespace for projects. No permissions model yet — that's a separate design.

```python
class Organization(BaseModel):
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True)
    description = models.TextField(blank=True, default="")
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)

# On Project:
organization = models.ForeignKey(
    Organization, null=True, blank=True, on_delete=models.SET_NULL,
    related_name="projects",
)
```

- Projects without an org continue to work (nullable FK)
- The org `slug` participates in the project's natural key for export: `(org_slug, project_name)`
- Single migration: add Organization model + add FK to Project

## 3. Natural Keys

### Purpose

Natural keys serve three roles:
1. **Django serialization** (`dumpdata --natural-foreign`) — FK references as human-readable tuples instead of opaque integers
2. **User-facing exports** — meaningful identifiers in CSV/JSON output
3. **Import deduplication** — matching existing records on the target instance

### Natural key definitions

Each model implements `natural_key()` (instance method) and `get_by_natural_key()` (manager classmethod).

**Models with strong natural keys (existing unique constraints):**

| Model | Natural key | DB constraint |
|---|---|---|
| Organization | `(slug,)` | `UNIQUE(slug)` |
| Project | `(org_slug_or_none, name)` | Needs `UNIQUE(organization, name)` |
| Taxon | `(name,)` | `UNIQUE(name)` |
| Event | `(deployment_uuid, group_by)` | `UNIQUE(deployment, group_by)` |
| SourceImage | `(deployment_uuid, path)` | `UNIQUE(deployment, path)` |
| Pipeline | `(name, version)` | `UNIQUE(name, version)` |
| Algorithm | `(name, version)` | `UNIQUE(name, version)` |
| User | `(email,)` | `UNIQUE(email)` |
| Tag | `(name, project_uuid)` | `UNIQUE(name, project)` |

**Models with domain-level natural keys (application-enforced, need DB constraints):**

| Model | Natural key | Current enforcement |
|---|---|---|
| Detection | `(source_image, bbox)` for real detections; `(source_image, algorithm, bbox=NULL)` for null detections | App-level `.filter().first()` in `pipeline.py:454-464` |
| Classification | `(detection, algorithm, taxon, score)` | App-level `.filter().first()` in `pipeline.py:681-686` |
| Deployment | `(project, name)` | No constraint (names can collide within a project) |
| Device | `(project, name)` | No constraint |
| Site | `(project, name)` | No constraint |

**Models without natural keys (UUID is the identity):**

| Model | Why no natural key |
|---|---|
| Occurrence | Grouped by event + determination, but multiple occurrences of the same species in the same event are valid |
| Identification | A user can identify the same occurrence multiple times (withdraw and re-identify) |
| SourceImageCollection | Name is not unique |
| TaxaList | Name is not unique |
| Job | Transient processing records |
| S3StorageSource | Configuration record, no unique domain identifier |
| DataExport | Transient output records |
| ProcessingService | Configuration record |
| ProjectPipelineConfig | Through model |

For these, the `natural_key()` method returns `(uuid,)` and `get_by_natural_key()` looks up by UUID.

### Missing unique constraints to add

These should be added as part of this work to align the DB with the domain logic:

1. `Project`: `UNIQUE(organization, name)` — prevents duplicate project names within an org
2. `Deployment`: `UNIQUE(project, name)` — prevents duplicate deployment names within a project
3. `Device`: `UNIQUE(project, name)` — same
4. `Site`: `UNIQUE(project, name)` — same
5. `Detection`: Composite unique constraint for deduplication (needs research — see below)
6. `Classification`: Composite unique constraint (needs research — see below)

## 4. Export Command: `export_project`

### Usage

```bash
# Export a single project
python manage.py export_project --project 23 --output nunavik-export.json

# Export with options
python manage.py export_project --project 23 --output nunavik/ --split-models
```

### Output format

Single JSON file (or directory with one file per model type for large projects):

```json
{
  "format_version": "1.0",
  "exported_at": "2026-03-26T12:00:00Z",
  "antenna_version": "x.y.z",
  "source_instance": "antenna.example.org",
  "organization": {
    "uuid": "...", "name": "...", "slug": "..."
  },
  "project": {
    "uuid": "...", "name": "...", "fields": { ... }
  },
  "shared_references": {
    "taxa": [
      { "natural_key": ["Lepidoptera"], "uuid": "..." },
      ...
    ],
    "users": [
      { "natural_key": ["user@example.org"], "uuid": "..." },
      ...
    ],
    "pipelines": [
      { "natural_key": ["Quebec & Vermont moths", "2023"], "uuid": "..." },
      ...
    ],
    "algorithms": [
      { "natural_key": ["moth_detector", "1.0"], "uuid": "..." },
      ...
    ]
  },
  "models": {
    "main.deployment": [
      { "uuid": "...", "fields": { "name": "Kuujjuaq", "project": "<project_uuid>", ... } },
      ...
    ],
    "main.event": [ ... ],
    "main.sourceimage": [ ... ],
    "main.detection": [ ... ],
    "main.classification": [ ... ],
    "main.occurrence": [ ... ],
    "main.identification": [ ... ],
    ...
  }
}
```

### FK serialization rules

- **Project-scoped FKs** (Deployment → Project, Event → Deployment, etc.): Serialized as target object's UUID
- **Shared/global references** (Classification → Taxon, Identification → User, Detection → Algorithm): Serialized as natural key tuple. On import, matched by natural key; if not found, created or errored depending on type.
- **Self-referential FKs** (Taxon → parent Taxon): Natural key `(name,)`
- **Nullable FKs**: Serialized as `null`

### Export ordering (FK dependency graph)

Same ordering as `move_project_data`:

1. Organization
2. Project (+ members, default filter taxa)
3. S3StorageSource
4. Device, Site
5. Deployment
6. Event
7. SourceImage
8. Detection
9. Classification
10. Occurrence
11. Identification
12. SourceImageCollection (+ M2M image links)
13. Job
14. Tag, TaxaList
15. ProjectPipelineConfig
16. DataExport

### What is NOT exported

- **Source image files** — remain in S3/MinIO. SourceImage records preserve their `path` field; the target instance must configure its own S3StorageSource to access the same (or copied) bucket.
- **Detection crop images** — can be regenerated from source images + bounding boxes.
- **Celery task state** — transient; jobs are exported as historical records only.
- **User passwords/tokens** — users are referenced by email; authentication is instance-local.
- **Django permissions/groups** — recreated by `create_roles_for_project()` on import.

## 5. Import Command: `import_project`

### Usage

```bash
# Import into clean database (prod → dev)
python manage.py import_project nunavik-export.json

# Import with conflict handling (instance migration)
python manage.py import_project nunavik-export.json --on-conflict=skip

# Dry run
python manage.py import_project nunavik-export.json --dry-run
```

### Import process

1. **Parse and validate** — check format_version, antenna_version compatibility
2. **Resolve shared references** by natural key:
   - Taxon → `(name,)` — match existing or create
   - User → `(email,)` — match existing only (do not create users)
   - Pipeline → `(name, version)` — match existing or create
   - Algorithm → `(name, version)` — match existing or create
3. **Create Organization** — match by slug or create
4. **Create Project** — match by `(org_slug, name)` or create
5. **Create project-scoped objects** in FK dependency order, building a `uuid → new_pk` mapping as each object is created
6. **Wire FK references** — all FKs in the export are UUIDs; resolve each to the new PK via the mapping
7. **Restore M2M relationships** — project members, collection images, taxa lists, etc.
8. **Post-import**: call `update_calculated_fields()` on deployments, events; call `update_related_calculated_fields()` on project; call `create_roles_for_project()` for permission groups

### Conflict handling (`--on-conflict`)

When a UUID from the export already exists in the target database:

| Mode | Behavior |
|---|---|
| `error` (default) | Abort import with an error message listing conflicting UUIDs |
| `skip` | Skip the conflicting record; use the existing object's PK in the FK mapping |
| `update` | Update the existing record's fields from the export data |

### Validation and reporting

Same pattern as `move_project_data`:
- Pre-import: dry-run mode showing what would be created
- Post-import: row counts per model type, FK integrity checks, cached field verification

## 6. Integration with Existing Export Framework

The existing `ami/exports/` app produces occurrence CSVs and JSONs for end users. These are enhanced to use the new UUID and natural key infrastructure:

### CSV export additions

New columns in `OccurrenceTabularSerializer`:

| Column | Source |
|---|---|
| `occurrence_uuid` | `occurrence.uuid` |
| `event_uuid` | `occurrence.event.uuid` |
| `deployment_uuid` | `occurrence.deployment.uuid` |
| `detection_uuid` | Best detection's UUID |
| `determination_uuid` | `occurrence.determination.uuid` (Taxon) |

Existing human-readable columns (`deployment_name`, `taxon_name`, etc.) remain unchanged — these are already natural-key-like.

### Darwin Core mapping

UUID fields map directly to Darwin Core terms:

| Antenna field | Darwin Core term |
|---|---|
| `occurrence.uuid` | `occurrenceID` |
| `event.uuid` | `eventID` |
| `taxon.name` | `scientificName` |
| `taxon.rank` | `taxonRank` |
| `deployment.name` | `locationID` or `locality` |
| `detection.bbox` | Could map to annotation extensions |
| `identification.uuid` | `identificationID` |
| `identification.user.email` | `identifiedBy` |

### No structural changes to the export framework

The `BaseExporter`, `ExportRegistry`, and `DataExport` model remain unchanged. Only the serializers get new fields. New export formats (Darwin Core Archive) can be added as new registered exporters.

---

## Areas Requiring Further Research and Validation

### Internal: Existing Data and Models

1. **Detection uniqueness constraint feasibility**
   - The current deduplication logic uses `(source_image, bbox)` for real detections and `(source_image, algorithm, bbox=NULL)` for null detections. This is two different composite keys depending on whether `bbox` is null.
   - **Research needed:** Can this be expressed as a single DB-level constraint? PostgreSQL supports partial unique indexes (`CREATE UNIQUE INDEX ... WHERE bbox IS NOT NULL` and a separate one `WHERE bbox IS NULL`), but Django's `UniqueConstraint` with `condition` may be needed. Audit existing data for violations before adding constraints.
   - **Validate:** Run a query to check for duplicate `(source_image_id, bbox)` pairs in the Detection table. If violations exist, they need to be cleaned up first.

2. **Classification uniqueness constraint feasibility**
   - Current dedup uses `(detection, taxon, algorithm, score)`. Including `score` (a float) in a unique constraint is unusual and may have precision issues.
   - **Research needed:** Is `score` truly part of the identity, or is it `(detection, algorithm, taxon)` with the score being an attribute? If the same algorithm classifies the same detection as the same taxon twice with different scores, is that a duplicate or two valid records?
   - **Validate:** Query for duplicate `(detection_id, algorithm_id, taxon_id)` triples to understand the data.

3. **Deployment name uniqueness**
   - We want `UNIQUE(project, name)` on Deployment, but names may already collide within projects.
   - **Validate:** `SELECT project_id, name, COUNT(*) FROM main_deployment GROUP BY project_id, name HAVING COUNT(*) > 1`
   - Same validation needed for Device and Site.

4. **Project name uniqueness within organization**
   - Adding `UNIQUE(organization, name)` requires handling the case where `organization` is NULL (multiple NULL org projects with the same name are allowed by PostgreSQL's unique constraint semantics, which treats NULLs as distinct).
   - **Research needed:** Do we want a `UNIQUE(name) WHERE organization IS NULL` partial constraint too?

5. **UUID backfill migration performance**
   - Adding a UUID column with `default=uuid4` to tables with millions of rows (SourceImage: ~10M, Detection: ~1M, Classification: ~1M) will lock the table during migration.
   - **Research needed:** Test migration time on a staging copy. Consider a phased approach: add nullable column → backfill in batches → set NOT NULL + unique.

6. **Occurrence identity**
   - Occurrences are currently created by grouping detections within an event. The same species can have multiple occurrences in the same event.
   - **Research needed:** Is there any domain-level identity for occurrences beyond the auto-generated PK? How do other platforms handle this? (See GBIF section below.)

7. **Existing `DataExport` output consumers**
   - Adding UUID columns to CSV exports changes the schema that downstream consumers (researchers' scripts, R/Python notebooks) expect.
   - **Research needed:** Are there documented consumers? Should UUID columns be opt-in via a parameter?

### External: Biodiversity Data Standards and Platforms

8. **GBIF (Global Biodiversity Information Facility)**
   - GBIF uses Darwin Core Archive (DwC-A) as its interchange format — a zip of CSV files with a `meta.xml` descriptor.
   - `occurrenceID` must be a globally unique, persistent identifier. GBIF recommends URIs (e.g., `urn:catalog:institution:collection:id`). UUIDs satisfy this but are not human-friendly.
   - **Research needed:** Review GBIF's [Publishing Data Guide](https://www.gbif.org/publishing-data) and [Darwin Core Archive specification](https://dwc.tdwg.org/text/). Understand how they handle: dataset versioning, record updates/deletions, identifier persistence across re-publications, and the relationship between `occurrenceID`, `catalogNumber`, and `institutionCode`.
   - **Specific question:** GBIF assigns its own `gbifID` to every record. How does that interact with the publisher's `occurrenceID`? Is the publisher's ID used for deduplication on re-upload?

9. **iNaturalist**
   - iNaturalist uses integer IDs in its API (`observation_id`, `taxon_id`) but also exposes UUIDs for observations (`observation.uuid`).
   - Their export format (DwC-A for GBIF) maps `observation.uuid` to `occurrenceID`.
   - **Research needed:** How does iNaturalist handle observation identity across their API, their GBIF export, and their CSV export? Do they use UUIDs internally or only externally? What does their identifier lifecycle look like when an observation is merged or deleted?

10. **BOLD (Barcode of Life Data System)**
    - BOLD uses `processID` as the primary identifier for specimen records.
    - **Research needed:** How does BOLD handle data portability between institutions? What identifier scheme do they use for cross-system references? How do they handle specimen records that appear in both BOLD and GBIF?

11. **Darwin Core identifier conventions**
    - DwC defines `occurrenceID`, `eventID`, `locationID`, `identificationID`, `taxonID` — all expected to be persistent, unique identifiers.
    - **Research needed:** What is the recommended format? Plain UUIDs? URIs with a namespace prefix (e.g., `urn:antenna:occurrence:uuid`)? How do major publishers format these?
    - **Specific question:** Should we mint URIs like `https://antenna.example.org/occurrences/{uuid}` that could theoretically resolve to the occurrence, or just use plain UUIDs?

12. **Camera trap data standards (Camtrap DP)**
    - [Camtrap DP](https://camtrap-dp.tdwg.org/) is a community-developed exchange format for camera trap data, built on Frictionless Data Packages.
    - It defines `deploymentID`, `mediaID`, `observationID` fields.
    - **Research needed:** How does Camtrap DP handle identifiers? Is it compatible with our model structure? Could Antenna export Camtrap DP format as an additional export type?

### External: Non-Biodiversity Applications with Portable Data

13. **Notion / Confluence (knowledge bases)**
    - Notion exports as Markdown + CSV with internal UUIDs as page identifiers. Import reconstructs the link graph from UUIDs.
    - **Relevant pattern:** They solve the same FK-remapping problem when importing into a different workspace. Their approach: every block has a UUID, all references use UUIDs, import creates fresh internal IDs but preserves UUID-based cross-references.

14. **GitLab / GitHub (project migration)**
    - GitLab's project export (`gitlab-export.tar.gz`) contains JSON files per model type (issues, merge requests, notes, labels) with internal IDs. Import remaps all IDs to fresh sequences.
    - **Relevant pattern:** They handle the "shared references" problem (users, labels) by matching on natural keys (username, label name) and creating placeholders when matches fail.
    - **Research needed:** How does GitLab handle cross-project references in imported data? How do they version their export format for backwards compatibility?

15. **Basecamp / Linear / Jira (project management)**
    - Jira's project export uses an XML format with internal IDs. Import into a different instance requires an ID remapping step. Jira also supports "project key" as a natural key for cross-references.
    - **Relevant pattern:** Jira distinguishes between "project-scoped" data (issues, comments) and "global" data (users, custom field definitions). Only project-scoped data is exported; global data must pre-exist on the target instance.

16. **WordPress (site migration)**
    - WordPress export (WXR format) uses slugs and GUIDs (`<guid>` tags) for post identity. Import matches by GUID to detect duplicates.
    - **Relevant pattern:** Media files are referenced by URL in the export. The importer can optionally download and re-host media, or leave the URLs pointing to the original site. This is analogous to our S3 source image handling.

17. **Django's own `dumpdata`/`loaddata` with natural keys**
    - Django's contrib apps (auth, contenttypes, sites) are the canonical example of natural keys in Django.
    - `ContentType` natural key: `(app_label, model)`. `Permission` natural key: `(codename, app_label, model)`.
    - **Research needed:** Review how Django handles natural key ordering in `dumpdata`. The `--natural-primary` flag serializes the PK itself as a natural key, while `--natural-foreign` serializes FK references. We want `--natural-foreign` but NOT `--natural-primary` (we want UUIDs for PKs in the export, natural keys for FK references to shared objects).

### Implementation Risks and Open Questions

18. **Schema evolution between Antenna versions**
    - If the export format includes field-level data, schema changes between versions break import.
    - **Decision needed:** How strict is version compatibility? Options: (a) exact version match required, (b) format_version-based compatibility with documented breaking changes, (c) field-level schema included in export for self-describing archives.

19. **Large project export performance**
    - Projects with millions of source images and detections will produce multi-GB JSON files.
    - **Decision needed:** Stream-based export (JSONL) vs. single JSON blob? Split by model type into separate files? Compression?

20. **Taxonomy divergence between instances**
    - Taxon natural key is `(name,)`, but two instances might have the same taxon name with different parent hierarchies or ranks.
    - **Decision needed:** On import, if a taxon name matches but the parent chain differs, is that a conflict? Should we include parent info in the natural key?

21. **Partial re-import / incremental sync**
    - The `--on-conflict=skip` mode enables incremental sync, but what about records that were deleted on the source after the previous export?
    - **Decision needed:** Is deletion sync in scope? Probably not for v1, but worth noting.
