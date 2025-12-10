# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Guidelines

**IMPORTANT - Cost Optimization:**
Every call to the AI model API incurs a cost and requires electricity. Be smart and make as few requests as possible. Each request gets subsequently more expensive as the context increases.

**Efficient Development Practices:**
- Add learnings and gotchas to this file to avoid repeating mistakes and trial & error
- Ignore line length and type errors until the very end; use command line tools to fix those (black, flake8)
- Always prefer command line tools to avoid expensive API requests (e.g., use git and jq instead of reading whole files)
- Use bulk operations and prefetch patterns to minimize database queries

**Performance Optimization:**
- django-cachalot handles automatic query caching - don't add manual caching layers on top
- Focus on optimizing cold queries first before adding caching
- When ordering by annotated fields, pagination COUNT queries include those annotations - use `.values('pk')` to strip them
- For large tables (>10k rows), consider fuzzy counting using PostgreSQL's pg_class.reltuples

**Git Commit Guidelines:**
- Do NOT include "Generated with Claude Code" in commit messages
- ALWAYS include "Co-Authored-By: Claude <noreply@anthropic.com>" at the end of commit messages

## Project Overview

Antenna is an Automated Monitoring of Insects ML Platform. It's a collaborative platform for processing and reviewing images from automated insect monitoring stations, maintaining metadata, and orchestrating multiple machine learning pipelines for analysis.

**Tech Stack**: Django 4.2 + DRF backend, React 18 + TypeScript frontend, Celery task queue, PostgreSQL database, MinIO S3-compatible storage, FastAPI ML processing services.

## Critical Configuration Patterns

### Timezone Handling

- **USE_TZ = False**: Django settings explicitly disable timezone support - all times are in local time, not UTC. This affects all datetime handling across the application and requires timezone information to be stored separately for each deployment.

### Project-Specific Filtering System

- **apply_default_filters()**: Sophisticated filtering system used throughout the codebase for Occurrence queries. Always use `Occurrence.objects.apply_default_filters(project, request)` instead of manual filtering. Respects `apply_defaults=false` query parameter to bypass filtering entirely.

- **build_occurrence_default_filters_q()**: Core filtering utility in `ami/main/models_future/filters.py` that combines score thresholds and hierarchical taxa inclusion/exclusion. Essential for maintaining consistent filtering across all occurrence-related queries.

- **Hierarchical taxa filtering**: Uses `parents_json` field for recursive taxonomy traversal. When filtering taxa, always include both direct matches and descendants via `parents_json__contains`.

## Deprecated Code Patterns

**IMPORTANT**: Avoid these deprecated patterns when working with the codebase.

- **Classification threshold parameters**: Deprecated in favor of project default filters system. Remove `classification_threshold` parameters from method signatures and use `apply_default_filters()` instead.

- **Job progress fields**: `stages`, `errors`, and `logs` fields in Job model are deprecated - use the logs relationship instead.

## Non-Standard Model Patterns

These patterns are specific to this codebase and may differ from typical Django conventions:

- **Project ownership**: Projects auto-add their owner to members via `ensure_owner_membership()` method in save(). Never manually manage owner membership.

- **Calculated fields**: Many models use `update_calculated_fields()` methods that must be called when related data changes. Always call these after bulk operations.

- **Event grouping**: Images are grouped into Events using `group_images_into_events()` function with 120-minute default gaps. Events are identified by `YYYY-MM-DD` format in `group_by` field.

## Development Commands

### Docker Compose (Primary Development Environment)

Start all services:
```bash
docker compose up -d
docker compose logs -f django celeryworker ui
```

Stop all services:
```bash
docker compose down
```

### Debugging with VS Code

Enable remote debugging with debugpy for Django and Celery services:

```bash
# One-time setup: copy the override example file
cp docker-compose.override-example.yml docker-compose.override.yml

# Start services (debugpy will be enabled automatically)
docker compose up

# In VS Code, attach debugger:
# - "Attach: Django" for web server debugging (port 5678)
# - "Attach: Celeryworker" for task debugging (port 5679)
# - "Attach: Django + Celery" for simultaneous debugging
```

**How it works:**
- The `docker-compose.override.yml` file sets `DEBUGGER=1` environment variable
- Start scripts (`compose/local/django/start` and `compose/local/django/celery/worker/start`) detect this and launch with debugpy
- VS Code launch configurations in `.vscode/launch.json` connect to the exposed ports
- The override file is git-ignored for local customization

**Disable debugging:**
```bash
rm docker-compose.override.yml
docker compose restart django celeryworker
```

### Backend (Django)

Run tests:
```bash
docker compose run --rm django python manage.py test
```

Run specific test pattern:
```bash
docker compose run --rm django python manage.py test -k pattern
```

Run tests with debugger on failure:
```bash
docker compose run --rm django python manage.py test -k pattern --failfast --pdb
```

Speed up test development (reuse database):
```bash
docker compose run --rm django python manage.py test --keepdb
```

Run pytest (alternative test runner):
```bash
docker compose run --rm django pytest --ds=config.settings.test --reuse-db
```

Django shell:
```bash
docker compose exec django python manage.py shell
```

Create superuser:
```bash
docker compose run --rm django python manage.py createsuperuser
```

Create demo project with synthetic data:
```bash
docker compose run --rm django python manage.py create_demo_project
```

Generate OpenAPI schema:
```bash
docker compose run --rm django python manage.py spectacular --api-version 'api' --format openapi --file ami-openapi-schema.yaml
```

### Frontend (React + TypeScript)

Located in `ui/` directory. Run locally (requires matching Node version):
```bash
cd ui
nvm install  # Install Node version from .nvmrc
yarn install
yarn start   # Development server on port 3000
```

Build production bundle:
```bash
cd ui
yarn build
```

Run tests:
```bash
cd ui
yarn test
```

Lint and format:
```bash
cd ui
yarn lint
yarn format
```

### ML Processing Services

Start example processing service:
```bash
docker compose -f processing_services/example/docker-compose.yml up -d
```

Register in Antenna UI as: `http://ml_backend_example:2000`

## Architecture

### High-Level Structure

```
SOURCE IMAGES (uploaded to S3/MinIO)
        ↓
   DEPLOYMENTS (monitoring stations)
        ↓
   EVENTS (temporal grouping)
        ↓
   JOBS (ML processing tasks → Celery)
        ↓
PROCESSING SERVICE (FastAPI backend)
        ↓
   DETECTIONS (bounding boxes)
        ↓
   CLASSIFICATIONS (species labels)
        ↓
   OCCURRENCES (validated observations)
        ↓
UI GALLERY (real-time updates)
```

### Core Django Apps

1. **ami.main** - Domain models and core workflow
   - `Project`: Top-level organizational unit with multiple deployments
   - `Deployment`: Monitoring station (device + site + location)
   - `Event`: Temporal grouping of images (e.g., nightly capture session)
   - `SourceImage`: Raw image from monitoring station
   - `Detection`: Bounding box from ML pipeline
   - `Classification`: Species label assigned to detection
   - `Occurrence`: Validated observation combining detections/classifications
   - `Taxon`: Species taxonomy with hierarchical ranks

2. **ami.ml** - ML orchestration
   - `Pipeline`: Named ML workflow (e.g., detector + classifier)
   - `Algorithm`: Individual ML model
   - `ProcessingService`: Remote/local ML backend endpoint
   - `ProjectPipelineConfig`: Per-project ML configuration

3. **ami.jobs** - Asynchronous job management
   - `Job`: Tracks ML processing jobs with real-time progress
   - `JobProgress`: Nested progress tracking with stages (Pydantic model)

4. **ami.users** - Authentication with token-based auth (djoser)

5. **ami.exports** - Data export to various formats

### ML Pipeline Flow

When a user triggers ML processing:

1. `Job` created with selected `Pipeline` and image IDs
2. Celery task queued (`ami.jobs.tasks.run_job`)
3. Worker calls `pipeline.filter_processed_images()` to skip already-processed images
4. `pipeline.process_images()` sends batch request to `ProcessingService` API endpoint
5. Processing service returns `PipelineResultsResponse` (Pydantic schema)
6. Results saved to database via `pipeline.save_results()`
7. UI polls job status for real-time progress updates

Key files:
- `ami/ml/models/pipeline.py` - Core pipeline orchestration logic
- `ami/ml/orchestration/pipelines.py` - Pipeline selection logic
- `ami/ml/tasks.py` - Celery tasks for ML processing
- `ami/jobs/models.py` - Job and progress tracking
- `ami/ml/schemas.py` - Pydantic schemas for API contract with processing services

### Processing Service Integration

Processing services are FastAPI applications that implement the AMI ML API contract:

**Endpoints:**
- `GET /info` - Returns available pipelines, algorithms, and category maps
- `GET /livez` - Liveness check
- `GET /readyz` - Readiness check (may trigger model loading)
- `POST /process` - Process images with specified pipeline

**API Contract:**
- Request: `PipelineRequest` with image URLs, existing detections, config overrides
- Response: `PipelineResultsResponse` with detections, classifications, metadata

**Health Checks:**
- Cached status with 3 retries and exponential backoff (0s, 2s, 4s)
- Celery Beat task runs periodic checks (`ami.ml.tasks.check_processing_services_online`)
- Status stored in `ProcessingService.last_checked_live` boolean field
- UI shows red/green indicator based on cached status

Location: `processing_services/` directory contains example implementations

### Celery Task Queue

**Broker & Result Backend:** RabbitMQ

**Key Tasks:**
- `ami.jobs.tasks.run_job` - Main ML processing workflow
- `ami.ml.tasks.process_source_images_async` - Batch image processing
- `ami.ml.tasks.create_detection_images` - Generate cropped images from detections
- `ami.ml.tasks.check_processing_services_online` - Periodic health checks (Beat)
- `ami.ml.tasks.remove_duplicate_classifications` - Cleanup task

**Monitoring:** Flower UI available at http://localhost:5555

### Frontend Architecture

**Stack:** React 18 + TypeScript + Vite + TanStack React Query + Tailwind CSS

**Key Directories:**
- `ui/src/pages/` - Page components mapped to routes
- `ui/src/components/` - Reusable React components
- `ui/src/data-services/hooks/` - React Query hooks for API calls
- `ui/src/data-services/models/` - TypeScript interfaces

**State Management:** TanStack React Query handles all server state (caching, refetching, optimistic updates)

**API Proxy:** In development, Vite proxies `/api` requests to Django backend (configured via `API_PROXY_TARGET` env var)

### Permissions & Visibility

- **django-guardian** provides object-level permissions
- Draft projects only visible to owner, members, and superusers
- Custom QuerySet methods: `.visible_for_user()`, `.filter_by_user()`
- Token-based authentication via djoser
- Frontend checks permissions via API endpoints

### Database Notes

- PostgreSQL with ArrayField support (used for storing detection metadata)
- Pydantic models stored in JSONB fields via django-pydantic-field
- Custom managers and QuerySets for filtering by user permissions

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

## Common Development Patterns

### Adding a New API Endpoint

1. Define serializer in `ami/<app>/api/serializers.py`
2. Add ViewSet in `ami/<app>/api/views.py`
3. Register route in `config/api_router.py`
4. Add React Query hook in `ui/src/data-services/hooks/`

### Adding a New ML Pipeline

1. Implement FastAPI service in `processing_services/` (see `example/` for reference)
2. Start service and register endpoint URL in Antenna UI
3. System auto-fetches pipeline configs from `/info` endpoint
4. Link `ProjectPipelineConfig` to enable for specific projects

### Working with Celery Tasks

- Tasks defined in `<app>/tasks.py` files
- Import and call with `.delay()` for async: `run_job.delay(job_id)`
- Use `@shared_task` decorator for all tasks
- Check Flower UI for debugging: http://localhost:5555

### Running a Single Test

```bash
# Run specific test class
docker compose run --rm django python manage.py test ami.main.tests.test_models.ProjectTestCase

# Run specific test method
docker compose run --rm django python manage.py test ami.main.tests.test_models.ProjectTestCase.test_project_creation

# Run with pattern matching
docker compose run --rm django python manage.py test -k test_detection
```

### Pre-commit Hooks

Install pre-commit to run linting/formatting before commits:
```bash
pip install pre-commit
pre-commit install
```

Hooks run: black (Python formatter), eslint (JS/TS linter), prettier (JS/TS formatter)

### Non-Docker Development Commands

For local development outside Docker:

**Python formatting and linting:**
```bash
black .                          # Format code (119 char line length)
isort --profile=black .          # Sort imports
mypy .                           # Type checking (Django and DRF plugins configured)
flake8 .                         # Linting
pylint ami/                      # Additional linting with Django-specific plugins
```

**Frontend:**
```bash
cd ui
npm run build                    # Production build
```

## Testing Conventions

- **Test settings**: Use `--ds=config.settings.test` for pytest. Tests use in-memory database with `--reuse-db` option for faster iteration.

- **Media storage**: Tests automatically configure temporary media storage via `media_storage` fixture.

- **Factory pattern**: Use `UserFactory()` and other factories from `ami/*/tests/factories.py` for test data creation instead of manual model instantiation.

## Important File Locations

- `ami/main/models.py` (~3700 lines) - Core domain models
- `ami/main/models_future/filters.py` - Core filtering utilities (build_occurrence_default_filters_q)
- `ami/ml/models/pipeline.py` - ML pipeline orchestration
- `ami/ml/orchestration/processing.py` - Image processing workflow
- `ami/utils/requests.py` - HTTP utilities with retry logic
- `config/settings/base.py` - Django settings
- `config/celery_app.py` - Celery configuration
- `docker-compose.yml` - Local development stack
- `ui/src/pages/` - React page components
- `processing_services/README.md` - Guide for adding custom ML pipelines

## Known Technical Debt & Areas for Improvement

1. **Model File Size** - `ami/main/models.py` is very large (~3700 lines) containing model definitions, business logic, processing orchestration, and helper functions. Consider splitting into separate modules.

2. **Processing Logic Extraction** - Functions like `process_single_source_image()` and `group_images_into_events()` should be moved from models to dedicated service modules (e.g., `ami/ml/orchestration/`, `ami/main/services/`).

3. **Test Coverage** - Many complex methods lack comprehensive tests. Priority areas include ML pipeline orchestration and occurrence determination logic.

4. **Documentation** - Limited inline documentation for complex business logic, especially around filtering and determination calculations.

5. **API Design** - Some functions have too many responsibilities and could benefit from refactoring into smaller, more focused units.

## Local URLs

- Primary UI: http://localhost:4000
- API Browser: http://localhost:8000/api/v2/
- Django Admin: http://localhost:8000/admin/
- OpenAPI Docs: http://localhost:8000/api/v2/docs/
- MinIO UI: http://minio:9001
- Flower (Celery): http://localhost:5555

**Default Credentials:**
- Email: `antenna@insectai.org`
- Password: `localadmin`

## Hosts File Configuration

Add to `/etc/hosts` for local MinIO access:
```
127.0.0.1 minio
127.0.0.1 django
```

This allows the same image URLs to work in both browser and backend containers.
