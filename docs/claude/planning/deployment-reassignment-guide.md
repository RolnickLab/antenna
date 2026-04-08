# Deployment Reassignment Guide

Moving deployments (stations) and all their associated data from one project to another.

## Overview

A "deployment reassignment" transfers one or more Deployment records and every piece of data hanging off them to a different Project. The physical data in S3 does not move — only database references change.

This guide covers the full relationship map, edge cases, and a validation checklist. An automated management command (`move_project_data`) implements these steps.

## Complete Relationship Map

### Tier 1 — Models with direct `project` ForeignKey (must update `project_id`)

| Model | on_delete | Notes |
|---|---|---|
| **Deployment** | SET_NULL | Primary target of the move |
| **Event** | SET_NULL | Linked to deployment; also has own project FK |
| **SourceImage** | SET_NULL | Linked to deployment; also has own project FK |
| **Occurrence** | SET_NULL | Linked to deployment; also has own project FK |
| **Job** | CASCADE | Linked to deployment; also has own project FK |

### Tier 2 — Models with indirect project access (no `project_id` column, no update needed)

| Model | Access path | Notes |
|---|---|---|
| **Detection** | `source_image.project` | Follows SourceImage automatically |
| **Classification** | `detection.source_image.project` | Follows Detection chain |
| **Identification** | `occurrence.project` | Follows Occurrence automatically |

### Tier 3 — Shared/linked resources (may need cloning or re-linking)

| Resource | Relationship | Reassignment strategy |
|---|---|---|
| **S3StorageSource** | FK on Deployment (`data_source`) | Clone if `project_id` points to source project; update deployment FK |
| **Device** | FK on Deployment | Clone if `project_id` = source project; or set NULL (shared) |
| **Site** | FK on Deployment (`research_site`) | Clone if `project_id` = source project; or set NULL (shared) |
| **SourceImageCollection** | M2M with SourceImage, FK to Project | Split: remove moved images from source collection; optionally create mirror collection in target project |
| **Tag** | FK to Project (CASCADE) | Not deployment-scoped — usually not moved |
| **TaxaList** | M2M to Project | Add target project to M2M if relevant lists exist |
| **Taxon** | M2M to Project (`projects`) | Add target project to M2M for taxa referenced by moved occurrences |
| **ProcessingService** | M2M to Project | Add target project to M2M |
| **ProjectPipelineConfig** | FK to Project (through model for Pipeline↔Project) | Clone configs for target project |

### Tier 4 — Target project setup (create if new)

| Resource | Action |
|---|---|
| **Project** | Create with owner, name, description |
| **UserProjectMembership** | Copy relevant members |
| **ProjectPipelineConfig** | Clone from source project |
| **ProcessingService** links | Add to target project M2M |

## Edge Cases

### Mixed SourceImageCollections

Collections can contain images from multiple deployments. When moving deployments:

1. **Identify mixed collections** — collections in the source project containing images from both moving and staying deployments.
2. **Strategy options:**
   - **Remove moved images** from source collection (images lose collection membership).
   - **Clone collection** in target project containing only the moved images.
   - **Both** — remove from source AND create in target (recommended).
3. Collections with `project_id` pointing to source project that ONLY contain moved images can be reassigned directly.

### Shared Devices, Sites, S3StorageSources

These resources have a nullable `project` FK:
- If `project_id IS NULL` → already shared, no action needed.
- If `project_id = source_project` → either clone for target project or set NULL to share.
- If `project_id = some_other_project` → leave as-is.

**Recommendation:** Clone rather than nullify, to maintain clear ownership.

### Cached/Denormalized Fields

After moving, these must be recalculated:
- `Deployment.events_count`, `captures_count`, `occurrences_count`, `detections_count`, `taxa_count`
- `Project` summary statistics
- `Event` cached counts
- Call `update_calculated_fields()` on affected deployments and both projects.

### Taxa M2M

Occurrences reference Taxa via `determination`. The Taxon↔Project M2M (`taxon.projects`) controls which taxa appear in a project's taxonomy browser. After moving occurrences, add their referenced taxa to the target project's M2M.

### Jobs

Jobs have both `project` and `deployment` FKs. Historical jobs should be moved with their deployment to maintain audit trail. Pipeline references within jobs don't need changing (pipelines are shared objects).

## Validation Checklist

After a reassignment, verify:

### Row Count Integrity
- [ ] Total rows across source + target = original total (no data lost or duplicated)
- [ ] Per-deployment counts match pre-move snapshot for: Events, SourceImages, Occurrences, Detections, Classifications, Identifications, Jobs

### FK Integrity
- [ ] All Events for moved deployments have `project_id` = target project
- [ ] All SourceImages for moved deployments have `project_id` = target project
- [ ] All Occurrences for moved deployments have `project_id` = target project
- [ ] All Jobs for moved deployments have `project_id` = target project
- [ ] No orphaned records (events/images/occurrences with NULL project that shouldn't be)

### Indirect Relationships
- [ ] Detections accessible via `source_image__project` = target project
- [ ] Classifications accessible via `detection__source_image__project` = target project
- [ ] Identifications accessible via `occurrence__project` = target project

### Shared Resources
- [ ] Moved deployments point to correct S3StorageSource (cloned or shared)
- [ ] Moved deployments point to correct Device (cloned or shared)
- [ ] Moved deployments point to correct Site (cloned or shared)
- [ ] Source project's remaining deployments still point to valid resources

### Collections
- [ ] No SourceImageCollection in source project contains images from moved deployments
- [ ] If collections were cloned to target, they contain the correct images

### ML Configuration
- [ ] Target project has appropriate ProjectPipelineConfigs
- [ ] Target project linked to appropriate ProcessingServices

### Cached Fields
- [ ] `update_calculated_fields()` called on all moved deployments
- [ ] Both source and target project stats are accurate

### Taxa
- [ ] All taxa referenced by moved occurrences' `determination` are linked to target project M2M

## Future: Organization-Level Object

When an org-level model is added, deployment reassignment becomes simpler:
- Projects under the same org can share devices, sites, S3 sources, taxa, and pipeline configs natively.
- The reassignment reduces to updating `project_id` on the core models.
- Cross-org moves would still require the full cloning strategy.

## Related Files

- Management command: `ami/main/management/commands/move_project_data.py`
- Models: `ami/main/models.py`, `ami/ml/models/`, `ami/jobs/models.py`
- Filters: `ami/main/models_future/filters.py`
