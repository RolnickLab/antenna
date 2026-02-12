# Export System — API & Operations Reference

See also: `docs/claude/export-framework.md` for internal architecture and adding new formats.

## API Endpoint

`/api/v2/exports/` — `ExportViewSet` (`ami/exports/views.py:13`)

### Methods

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v2/exports/` | Create export, enqueue async Celery job |
| GET | `/api/v2/exports/` | List exports (scoped to active project via `ProjectMixin`) |
| GET | `/api/v2/exports/{id}/` | Retrieve single export (job progress, file URL, record count) |
| PUT/PATCH | `/api/v2/exports/{id}/` | Update export (admin-only) |
| DELETE | `/api/v2/exports/{id}/` | Delete export and its file from storage |

Permissions: `ObjectPermission` (`ami/base/permissions.py`). Researcher role can create and delete. Admin can update. Basic members and non-members cannot create.

### Creating an Export (POST)

**Required fields:**
- `project` (int) — Project PK
- `format` (string) — One of: `"occurrences_simple_csv"`, `"occurrences_api_json"`, `"dwca"`

**Optional fields:**
- `filters` (object) — Filter criteria applied to occurrences
  - `collection_id` (int) — Restrict to occurrences whose detections link to images in this `SourceImageCollection`

**Validation** (`views.py:30-86`):
1. Format checked against `ExportRegistry.get_supported_formats()`
2. If `collection_id` provided, validates existence and project ownership
3. Object-level permission check on unsaved instance before persisting
4. Creates `DataExportJob` and enqueues via Celery

**Response:** 201 with serialized `DataExport` including nested `job` object.

### Response Fields

Defined in `DataExportSerializer` (`ami/exports/serializers.py:30`):

```
id, user, project, format, filters, filters_display,
job {id, name, project, progress, result},
file_url, record_count, file_size, file_size_display,
created_at, updated_at
```

- `file_url` — null until export completes, then absolute URL to file
- `file_size_display` — human-readable (e.g. "2.4 MB")
- `filters_display` — auto-populated with human names (e.g. collection name)
- `job.progress` — tracks export stages with percentage

### Polling for Completion

Exports run asynchronously. Poll `GET /api/v2/exports/{id}/` and check:
- `job.progress` for stage updates
- `file_url` becomes non-null when export is ready for download

## Registered Formats

Registered in `ami/exports/registry.py:28-30`, implemented in `ami/exports/format_types.py`:

| Key | Class | Output | Description |
|-----|-------|--------|-------------|
| `occurrences_simple_csv` | `CSVExporter` (:149) | `.csv` | Tabular occurrence data with detection fields |
| `occurrences_api_json` | `JSONExporter` (:39) | `.json` | Full API serialization of occurrences |
| `dwca` | `DwCAExporter` (:192) | `.zip` | Darwin Core Archive with event.txt + occurrence.txt + meta.xml + eml.xml |

## Filter System

All exporters inherit `OccurrenceCollectionFilter` from `BaseExporter.get_filter_backends()` (`base.py:42-45`).

**OccurrenceCollectionFilter** (`ami/main/api/views.py:981-998`):
- Accepts `collection_id` or `collection` query param
- Filters: `queryset.filter(detections__source_image__collections=collection_id).distinct()`
- No-op when param is absent — unfiltered exports work unchanged

**How filters are applied in Celery context** (`ami/exports/utils.py`):
- `generate_fake_request()` creates a mock DRF Request with filter values as query params
- `apply_filters()` runs each filter backend's `filter_queryset()` against the exporter's queryset
- Called in `BaseExporter.__init__()` so `self.queryset` is already filtered before `export()` runs

## DwC-A Specifics

The DwC-A exporter produces two data files linked by `eventID`:

- **event.txt** — Events derived from filtered occurrences (`get_events_queryset()` at `format_types.py:211`)
- **occurrence.txt** — Filtered occurrences with Darwin Core terms

Events are not fetched independently — they're derived from `self.queryset.values_list("event_id").distinct()` to maintain referential integrity when filters are active.

Field definitions: `ami/exports/dwca.py` — `EVENT_FIELDS` (:26), `OCCURRENCE_FIELDS` (:57).
See `docs/claude/dwca-format-reference.md` for Darwin Core term mappings.

## Job Integration

`DataExportJob` (`ami/jobs/models.py:682-716`):
1. Adds "Exporting data" progress stage
2. Calls `job.data_export.run_export()`
3. Adds "Uploading snapshot" stage with file URL
4. Finalizes job as SUCCESS

`DataExport` has a OneToOne relation to `Job` via `job.data_export` (`models.py:841`).

## File Lifecycle

1. Exporter writes to temp file during `export()`
2. `DataExport.save_export_file()` uploads to `exports/` in default_storage (S3/MinIO)
3. `file_url` saved on model
4. On `DataExport` deletion: `pre_delete` signal (`ami/exports/signals.py:13`) removes file from storage
