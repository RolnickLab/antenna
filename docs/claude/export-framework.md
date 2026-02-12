# Export Framework Technical Reference

## Architecture Overview

The export system uses a registry pattern where format-specific exporters register themselves and are dispatched by `DataExport.run_export()`.

### Key Files

| File | Purpose |
|------|---------|
| `ami/exports/base.py` | `BaseExporter` ABC - all exporters inherit from this |
| `ami/exports/registry.py` | `ExportRegistry` - maps format strings to exporter classes |
| `ami/exports/format_types.py` | Concrete exporters: `JSONExporter`, `CSVExporter`, `DwCAExporter` |
| `ami/exports/models.py` | `DataExport` model - tracks export jobs, files, stats |
| `ami/exports/utils.py` | `apply_filters()`, `get_data_in_batches()`, `generate_fake_request()` |
| `ami/exports/views.py` | `ExportViewSet` - API endpoint for creating/listing exports |
| `ami/exports/serializers.py` | `DataExportSerializer` - validates format, filters |
| `ami/exports/signals.py` | Deletes exported file when `DataExport` is deleted |
| `ami/exports/dwca.py` | DwC-A field definitions, XML generators, TSV writer |

### Flow

```
1. User POST /api/v2/exports/ with {format, filters, project}
2. DataExportSerializer validates format against ExportRegistry
3. DataExport created, Job created (job_type_key="data_export")
4. Celery task calls DataExport.run_export()
5. run_export() calls DataExport.get_exporter() → ExportRegistry lookup
6. Exporter.__init__() builds queryset with filters
7. Exporter.export() writes temp file, returns path
8. DataExport.save_export_file() uploads to default_storage (S3/MinIO)
9. file_url saved to DataExport model
```

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

## Internals

### BaseExporter (ami/exports/base.py)

```python
class BaseExporter(ABC):
    file_format = ""           # e.g. "json", "csv", "zip"
    serializer_class = None    # DRF serializer for data transformation
    filter_backends = []       # DRF filter backends

    def __init__(self, data_export):
        # Sets self.data_export, self.job, self.project
        # Builds self.queryset using get_queryset() + apply_filters()
        # Sets self.total_records = queryset.count()

    @abstractmethod
    def export(self) -> str:
        """Must return path to temp file."""

    @abstractmethod
    def get_queryset(self):
        """Must return a Django QuerySet."""

    def get_filter_backends(self):
        return [OccurrenceCollectionFilter]  # default

    def update_export_stats(self, file_temp_path):
        """Updates record_count and file_size on DataExport."""

    def update_job_progress(self, records_exported):
        """Updates Job progress stage."""
```

### ExportRegistry (ami/exports/registry.py)

```python
ExportRegistry.register("format_name")(ExporterClass)
ExportRegistry.get_exporter("format_name")  # → ExporterClass
ExportRegistry.get_supported_formats()       # → ["occurrences_api_json", "occurrences_simple_csv", "dwca"]
```

### DataExport Model (ami/exports/models.py)

Key fields:
- `user` FK → User (who triggered)
- `project` FK → Project (scoped to project)
- `format` CharField (registry key)
- `filters` JSONField (e.g. `{"collection_id": 5}`)
- `filters_display` JSONField (precomputed human-readable)
- `file_url` URLField (final download URL)
- `record_count` PositiveIntegerField
- `file_size` PositiveBigIntegerField

Key methods:
- `run_export()` - orchestrates the full export pipeline
- `save_export_file(temp_path)` - uploads to storage, returns URL
- `generate_filename()` - `{project_slug}_export-{pk}.{ext}`
- `get_exporter()` - cached exporter instance

### Filter System

All exporters inherit `OccurrenceCollectionFilter` from `BaseExporter.get_filter_backends()` (`base.py:42-45`).

**OccurrenceCollectionFilter** (`ami/main/api/views.py:981-998`):
- Accepts `collection_id` or `collection` query param
- Filters: `queryset.filter(detections__source_image__collections=collection_id).distinct()`
- No-op when param is absent — unfiltered exports work unchanged

**How filters are applied in Celery context** (`ami/exports/utils.py`):
- `generate_fake_request()` creates a mock DRF Request with filter values as query params
- `apply_filters()` runs each filter backend's `filter_queryset()` against the exporter's queryset
- Called in `BaseExporter.__init__()` so `self.queryset` is already filtered before `export()` runs

### DwC-A Specifics

The DwC-A exporter produces two data files linked by `eventID`:

- **event.txt** — Events derived from filtered occurrences (`get_events_queryset()` at `format_types.py:211`)
- **occurrence.txt** — Filtered occurrences with Darwin Core terms

Events are not fetched independently — they're derived from `self.queryset.values_list("event_id").distinct()` to maintain referential integrity when filters are active.

Field definitions: `ami/exports/dwca.py` — `EVENT_FIELDS` (:26), `OCCURRENCE_FIELDS` (:57).
See `docs/claude/dwca-format-reference.md` for Darwin Core term mappings.

### Job Integration

`DataExportJob` (`ami/jobs/models.py:682-716`):
1. Adds "Exporting data" progress stage
2. Calls `job.data_export.run_export()`
3. Adds "Uploading snapshot" stage with file URL
4. Finalizes job as SUCCESS

`DataExport` has a OneToOne relation to `Job` via `job.data_export` (`models.py:841`).

### File Lifecycle

1. Exporter writes to temp file during `export()`
2. `DataExport.save_export_file()` uploads to `exports/` in default_storage (S3/MinIO)
3. `file_url` saved on model
4. On `DataExport` deletion: `pre_delete` signal (`ami/exports/signals.py:13`) removes file from storage

### Adding a New Export Format

1. Create exporter class extending `BaseExporter`
2. Set `file_format` (file extension)
3. Implement `get_queryset()` and `export()`
4. Register: `ExportRegistry.register("format_key")(YourExporter)`
5. The format automatically appears in the API's valid choices

### Utilities (ami/exports/utils.py)

- `generate_fake_request()` - creates a DRF Request for serializer context (needed because exports run in Celery, not in HTTP request context)
- `apply_filters(queryset, filters, filter_backends)` - applies DRF filter backends using fake request with filter query params
- `get_data_in_batches(queryset, serializer_class, batch_size=100)` - yields batches of serialized data using queryset.iterator()
