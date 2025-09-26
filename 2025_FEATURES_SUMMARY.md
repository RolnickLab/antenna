# Features Merged to Main in 2025 - Antenna Repository

This document summarizes the major features and enhancements that were merged to the main branch of the RolnickLab/antenna repository during 2025.

## Major Features Added

### 1. Tagging System for Taxa (May 2025)
**Migration:** `0061_tag_taxon_tags.py` (2025-05-15)
- Added a comprehensive tagging system for taxonomic classification
- Created `Tag` model with project-specific tags
- Added many-to-many relationship between `Taxon` and `Tag` models
- Tags are project-scoped with unique constraints per project
- Enables flexible labeling and categorization of taxa beyond standard taxonomic hierarchy

### 2. Project Feature Flags System (July-September 2025)
**Migrations:** `0062_project_feature_flags.py`, `0067_alter_project_feature_flags.py`, `0070_alter_project_feature_flags.py`, `0073_alter_project_feature_flags.py`
- Implemented a flexible feature flags system using Pydantic schemas
- Key feature flags include:
  - `tags`: Enable/disable tagging functionality per project
  - `auto_process_manual_uploads`: Automatically process uploaded images
  - `reprocess_existing_detections`: Allow reprocessing of existing detections
  - `default_filters`: Show default filters form in UI
- Evolved from hardcoded defaults to using `get_default_feature_flags()` function
- Allows gradual rollout and project-specific feature enablement

### 3. Project Draft Mode (September 2025)
**Migration:** `0072_project_draft.py` (2025-09-12)
- Added `draft` boolean field to Project model
- Enables projects to be marked as work-in-progress
- Supports staging workflows before making projects fully active

### 4. Enhanced Project Default Filters (August 2025)
**Migration:** `0065_project_default_filters_exclude_taxa_and_more.py` (2025-08-11)
- Added sophisticated default filtering capabilities:
  - `default_filters_include_taxa`: Taxa included by default in occurrence filters
  - `default_filters_exclude_taxa`: Taxa excluded by default (e.g., "Not a Moth")
  - `default_filters_score_threshold`: Default confidence score threshold (0.5)
  - `session_time_gap_seconds`: Time gap for session definition (2 hours default)
  - `default_processing_pipeline`: Default ML pipeline for image processing

### 5. Data Export System (April 2025)
**Migration:** `ami/exports/migrations/0001_initial.py` (2025-04-02)
- Created new `exports` Django app for data export functionality
- Added `DataExport` model to track export requests and files
- Support for multiple export formats:
  - `occurrences_api_json`: API-compatible JSON format
  - `occurrences_simple_csv`: Simplified CSV format
- Integration with job system for asynchronous export processing
- Tracks export metadata including record count and file size

### 6. Taxon Enhancement Features (September 2025)
**Migration:** `0074_taxon_cover_image_credit_taxon_cover_image_url_and_more.py` (2025-09-17)
- Added visual enhancements to taxa:
  - `cover_image_url`: URL for taxon cover images
  - `cover_image_credit`: Attribution for cover images
  - `fieldguide_id`: Integration with external field guide systems
- Supports rich visual presentation of taxonomic information

### 7. Enhanced ML Pipeline Configuration (March 2025)
**Migrations:** `0020_projectpipelineconfig_alter_pipeline_projects.py`, `0021_pipeline_default_config.py`
- Replaced simple many-to-many relationship with sophisticated `ProjectPipelineConfig` model
- Added per-project pipeline configuration capabilities
- Introduced `default_config` for pipelines using Pydantic schemas
- Enables fine-tuned ML processing settings per project-pipeline combination

### 8. Algorithm Management Improvements (February 2025)
**Migration:** `0017_alter_algorithm_unique_together.py` (2025-02-12)
- Added unique constraint on algorithm name and version
- Prevents duplicate algorithm registrations
- Improves ML model lifecycle management

### 9. Enhanced Taxonomic Classification Support (January-February 2025)  
**Migrations:** `0046_add_taxon_common_name_placeholder.py`, various taxonomy updates
- Added common name support for taxa (`common_name_en` field)
- Enhanced taxonomic rank system with additional levels:
  - Added SUPERFAMILY, SUBFAMILY, TRIBE, SUBTRIBE ranks
  - Maintained existing KINGDOM, PHYLUM, CLASS, ORDER, FAMILY, GENUS, SPECIES, UNKNOWN
- Improved taxonomic hierarchy representation

### 10. Project Permissions and Management Enhancements
**Multiple migrations throughout 2025**
- Expanded project permission system with granular controls:
  - Deployment management (create, update, delete)
  - Collection management (create, update, delete, populate)
  - Storage management (create, update, delete)
  - Site and device management
  - Job management (create, run, delete, retry, cancel)
  - Data export permissions
  - Private data access controls

## Technical Infrastructure Improvements

### Job System Enhancements
- Extended job types to include data export functionality
- Added job parameters support via JSON fields
- Improved job tracking and management

### Model Architecture
- Introduction of `models_future` package for modular model organization
- Planning for migration to more structured model organization
- Improved separation of concerns in the codebase

### Database Schema Evolution
- Multiple merge migrations to handle parallel development branches
- Squashed migrations for better performance and maintenance
- Consistent use of Django's migration system for schema changes

## Summary

2025 was a significant year for the Antenna platform, with major additions focused on:

1. **User Experience**: Tagging system, draft projects, enhanced filtering
2. **Data Management**: Comprehensive export system, improved taxonomic data
3. **ML Operations**: Enhanced pipeline configuration, algorithm management
4. **System Flexibility**: Feature flags, project-specific configurations
5. **Visual Enhancements**: Taxon cover images, field guide integration

These features collectively enhance the platform's capability to handle complex biodiversity monitoring projects with flexible configuration, robust data export, and improved user workflows.