# Query Patterns & Database Schema Reference

Extracted from CLAUDE.md. Database schema quick reference, index usage, prefetch patterns, and the custom QuerySet method catalog. The visual ERD is in `.agents/DATABASE_SCHEMA.md`.

## Database Schema Quick Reference

### Core Model Relationships

| Model | App | Key ForeignKeys | Reverse Relations | M2M | Important Indexes |
|-------|-----|-----------------|-------------------|-----|-------------------|
| **Project** | main | owner→User | deployments, events, occurrences, captures, jobs, pipelines, sites, devices, tags | members→User | [-priority, created_at] |
| **Deployment** | main | project→Project, research_site→Site, device→Device, data_source→S3StorageSource | events, captures, occurrences, jobs | - | [name] |
| **Event** | main | project→Project, deployment→Deployment | captures, occurrences | - | **UNIQUE**(deployment, group_by), [group_by], [start] |
| **SourceImage** | main | deployment→Deployment(**CASCADE**), event→Event, project→Project | detections | collections→Collection | **UNIQUE**(deployment, path), [deployment,timestamp], [event,timestamp] |
| **Detection** | main | source_image→SourceImage(**CASCADE**), occurrence→Occurrence, detection_algorithm→Algorithm | classifications | - | [frame_num, timestamp] |
| **Classification** | main | detection→Detection, taxon→Taxon, algorithm→Algorithm, category_map→CategoryMap | derived_classifications | - | [-created_at, -score] |
| **Occurrence** | main | determination→Taxon, event→Event, deployment→Deployment, project→Project | detections, identifications | - | **INDEX**(determination,project,event,score), **INDEX**(determination,project,event) |
| **Identification** | main | user→User, taxon→Taxon, occurrence→Occurrence(**CASCADE**), agreed_with_identification→Identification(self), agreed_with_prediction→Classification | - | - | [-created_at] |
| **Taxon** | main | parent→Taxon(self), synonym_of→Taxon(self) | direct_children, occurrences, classifications, identifications | projects→Project, tags→Tag | **UNIQUE**(name), [ordering, name] |
| **Device** | main | project→Project | deployments | - | [name] |
| **Site** | main | project→Project | deployments | - | [name] |
| **SourceImageCollection** | main | project→Project(**CASCADE**) | jobs | images→SourceImage | - |
| **Tag** | main | project→Project(**CASCADE**) | taxa | - | **UNIQUE**(name, project) |
| **Pipeline** | ml | - | jobs, project_pipeline_configs | algorithms→Algorithm, projects→Project(through), processing_services→ProcessingService | **UNIQUE**(name,version) |
| **Algorithm** | ml | category_map→CategoryMap | pipelines(M2M), classifications | - | **UNIQUE**(name,version) |
| **ProcessingService** | ml | - | - | projects→Project, pipelines→Pipeline | - |
| **ProjectPipelineConfig** | ml | project→Project(**CASCADE**), pipeline→Pipeline(**CASCADE**) | - | - | **UNIQUE**(pipeline, project) |
| **Job** | jobs | project→Project(**CASCADE**), deployment→Deployment(**CASCADE**), pipeline→Pipeline, source_image_collection→Collection, source_image_single→SourceImage | - | - | [-created_at] |
| **User** | users | - | projects(owner), user_projects(members M2M), identifications, exports | - | **UNIQUE**(email) |
| **DataExport** | exports | user→User(**CASCADE**), project→Project(**CASCADE**) | job(OneToOne) | - | [-created_at] |

**Legend:** Bold text indicates important constraints/behaviors. **CASCADE** = cascading deletes, **UNIQUE** = unique constraint, **INDEX** = composite index.

**Visual ERD:** See `DATABASE_SCHEMA.md` for a Mermaid entity-relationship diagram organized by domain layers.

### Query Optimization Guide

#### Critical Indexes for Performance

**Occurrence Queries** - Use these indexed fields:
```python
# Primary composite index - ALWAYS use when filtering by score
(determination_id, project_id, event_id, determination_score)

# Secondary composite index - for non-score queries
(determination_id, project_id, event_id)

# IMPORTANT: Always filter by project_id first when possible for best performance
Occurrence.objects.filter(project=project, determination__in=taxa_ids)
```

**SourceImage Queries** - Use these indexed fields:
```python
# For deployment timeline queries
(deployment, timestamp)  # ← Composite index

# For event-based queries
(event, timestamp)  # ← Composite index

# For lookups by path (UNIQUE constraint = very fast)
(deployment, path)  # ← Exact match lookups are O(1)
```

**Event Queries** - Use these indexed fields:
```python
# UNIQUE constraint - perfect for lookups
(deployment, group_by)

# For temporal queries
[group_by], [start]
```

**Taxon Queries** - Use these indexed fields:
```python
# For name lookups (UNIQUE = very fast)
name  # ← Exact match lookups

# For ordered listings
[ordering, name]  # ← Composite index
```

#### Essential Prefetch/Select_Related Patterns

**Occurrences with all related data:**
```python
# Comprehensive occurrence query with all relationships
Occurrence.objects.select_related(
    'determination',  # Taxon FK
    'determination__parent',  # Parent taxon
    'event',
    'deployment',
    'project'
).prefetch_related(
    'detections__classifications__taxon',
    'detections__classifications__algorithm',
    'detections__source_image',
    'identifications__user',
    'identifications__taxon'
)
```

**SourceImages with detections:**
```python
# Efficient source image query with nested relationships
SourceImage.objects.select_related(
    'deployment',
    'deployment__research_site',
    'deployment__device',
    'event',
    'project'
).prefetch_related(
    'detections__classifications__taxon__parent',
    'detections__occurrence',
    'collections'
)
```

**Jobs with pipeline info:**
```python
# Job query with all ML pipeline data
Job.objects.select_related(
    'project',
    'pipeline',
    'deployment',
    'source_image_collection'
).prefetch_related(
    'pipeline__algorithms',
    'pipeline__processing_services'
)
```

**Deployments with statistics:**
```python
# Deployment with denormalized counts (already cached in model fields)
# These fields are auto-updated: events_count, occurrences_count,
# captures_count, detections_count, taxa_count
Deployment.objects.select_related('research_site', 'device', 'project')
# No need to annotate counts - use the cached fields directly
```

**Taxa with hierarchy:**
```python
# Taxon queries with parent chain
Taxon.objects.select_related('parent', 'parent__parent')

# For full tree traversal, use the custom manager method
Taxon.objects.tree(root=root_taxon, filter_ranks=DEFAULT_RANKS)
```

#### Custom QuerySet Methods (Always Use These)

**Occurrence QuerySet Methods:**
```python
# Apply ALL project default filters (taxa lists, score thresholds, etc.)
Occurrence.objects.apply_default_filters(project, request)

# Add first_appearance and last_appearance timestamp annotations
Occurrence.objects.with_timestamps()

# Prefetch all identification data efficiently
Occurrence.objects.with_identifications()

# Filter by score threshold using indexed determination_score field
Occurrence.objects.filter_by_score_threshold(project, request)

# Get only valid occurrences (with at least one detection)
Occurrence.objects.valid()

# Annotate with detection count
Occurrence.objects.with_detections_count()

# Get unique taxa for a project (distinct determination values)
Occurrence.objects.unique_taxa(project)
```

**SourceImage QuerySet Methods:**
```python
# Apply project default filters (REQUIRED for proper visibility)
SourceImage.objects.apply_default_filters(project, request)

# Annotate with occurrence count
SourceImage.objects.with_occurrences_count()

# Annotate with distinct taxa count
SourceImage.objects.with_taxa_count()
```

**Event QuerySet Methods:**
```python
# Annotate with taxa count for project (respects filters)
Event.objects.with_taxa_count(project, request)

# Annotate with occurrence count for project
Event.objects.with_occurrences_count(project, request)
```

**Taxon QuerySet Methods:**
```python
# Filter taxa visible to user (by project membership)
Taxon.objects.visible_for_user(user)

# Apply project's include/exclude taxa lists
Taxon.objects.filter_by_project_default_taxa(project, request)

# Annotate with occurrence count for specific project
Taxon.objects.with_occurrence_counts(project)
```

**Taxon Manager Methods (use on Taxon.objects):**
```python
# Build hierarchical tree structure
Taxon.objects.tree(root=root_taxon, filter_ranks=DEFAULT_RANKS)

# Build tree of just names (lightweight)
Taxon.objects.tree_of_names(root=root_taxon)

# Get root taxon
Taxon.objects.root()

# Bulk update all cached parent chains
Taxon.objects.update_all_parents()

# Auto-create genus parents for species-level taxa
Taxon.objects.add_genus_parents()

# Bulk update display names
Taxon.objects.update_display_names(queryset)
```

**Pipeline QuerySet Methods:**
```python
# Get only enabled pipelines for a project
Pipeline.objects.enabled(project)

# Get only pipelines with healthy/online processing services
Pipeline.objects.online(project)
```

**Project QuerySet Methods:**
```python
# Filter projects where user is a member
Project.objects.filter_by_user(user)

# Filter projects visible to user (respects draft status and membership)
Project.objects.visible_for_user(user)
```

**SourceImageCollection QuerySet Methods:**
```python
# Annotate with total image count
SourceImageCollection.objects.with_source_images_count()

# Annotate with images that have detections count
SourceImageCollection.objects.with_source_images_with_detections_count()

# Annotate with count of images processed by specific algorithm
SourceImageCollection.objects.with_source_images_processed_by_algorithm_count(algorithm_id)

# Annotate with occurrence count (respects threshold)
SourceImageCollection.objects.with_occurrences_count(threshold, project)

# Annotate with taxa count
SourceImageCollection.objects.with_taxa_count(threshold, project)
```

#### Common Query Anti-Patterns to Avoid

**❌ DON'T: Query without project filter on Occurrence**
```python
# This will be slow and may return data user shouldn't see
Occurrence.objects.filter(determination=taxon)
```

**✅ DO: Always filter by project first**
```python
# Fast and respects permissions
Occurrence.objects.filter(project=project, determination=taxon)
```

**❌ DON'T: Use apply_default_filters in loops**
```python
# This is inefficient - applies filters per iteration
for project in projects:
    occurrences = Occurrence.objects.apply_default_filters(project, request)
```

**✅ DO: Batch queries or use prefetch**
```python
# Better - get all data in one query then filter in Python if needed
occurrences = Occurrence.objects.filter(project__in=projects).select_related('project')
```

**❌ DON'T: Access cached fields after bulk creation**
```python
# Cached counts won't be set for bulk_create
SourceImage.objects.bulk_create(images)
for img in images:
    print(img.detections_count)  # ← This will be None or stale
```

**✅ DO: Use custom QuerySet annotations or refresh from DB**
```python
# Either refresh individual instances
img.refresh_from_db()

# Or use annotate for bulk operations
images = SourceImage.objects.annotate(det_count=Count('detections'))
```

