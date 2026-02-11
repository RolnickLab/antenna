# Export Framework Technical Reference

## Architecture Overview

The export system uses a registry pattern where format-specific exporters register themselves and are dispatched by `DataExport.run_export()`.

### Key Files

| File | Purpose |
|------|---------|
| `ami/exports/base.py` | `BaseExporter` ABC - all exporters inherit from this |
| `ami/exports/registry.py` | `ExportRegistry` - maps format strings to exporter classes |
| `ami/exports/format_types.py` | Concrete exporters: `JSONExporter`, `CSVExporter` |
| `ami/exports/models.py` | `DataExport` model - tracks export jobs, files, stats |
| `ami/exports/utils.py` | `apply_filters()`, `get_data_in_batches()`, `generate_fake_request()` |
| `ami/exports/views.py` | `DataExportViewSet` - API endpoint for creating/listing exports |
| `ami/exports/serializers.py` | `DataExportSerializer` - validates format, filters |
| `ami/exports/signals.py` | Deletes exported file when `DataExport` is deleted |

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
ExportRegistry.get_supported_formats()       # → ["occurrences_api_json", "occurrences_simple_csv"]
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

### Important Notes

- Exports run as Celery tasks, so no real HTTP request is available
- The `generate_fake_request()` utility creates a mock DRF request for serializer context (needed for HyperlinkedModelSerializer URLs)
- Filters are passed as query params on the fake request
- Default filter backend is `OccurrenceCollectionFilter` (filters by collection_id)
- The export file is written to a temp file, then uploaded to default_storage (S3/MinIO)
- On DataExport deletion, the signal handler deletes the file from storage
