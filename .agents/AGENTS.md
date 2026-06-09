# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Guidelines

**IMPORTANT - Cost Optimization:**
Every call to the AI model API incurs a cost and requires electricity. Be smart and make as few requests as possible. Each request gets subsequently more expensive as the context increases.

**Efficient Development Practices:**
- Add learnings and gotchas to this file to avoid repeating mistakes and trial & error
- Check `docs/claude/INDEX.md` for existing reference docs, runbooks, and plans before exploring the codebase from scratch
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

## Pull Request Conventions

These conventions keep PR titles and descriptions readable for the whole team — product, QA, ops, and engineers who have not seen the diff. The PR template lives at `.github/pull_request_template.md`; the rules below are the parts treated as mandatory.

### Title: lead with the user-facing effect

A title states what the change does for a user, operator, or system, in plain language. It should make sense to someone who has not opened the diff.

- **Effect first, mechanism second.** Push the "how" (serializers, querysets, cache internals, env var names) into the body.
  - Avoid: `emit storage URL direct from serializer when cache is warm`
  - Prefer: `Store and serve full URLs instead of hitting the web server`
- **Bare sentence-case imperative.** Concrete verb first (Add, Allow, Speed up, Filter, Require, Improve, Stop, Show). No Conventional-Commit prefix (`feat:` / `fix:` / `chore:`) in the title, no code or module names, and no ticket number (reference it in the body with `Closes #N`).
- **Capture the whole PR's purpose, not just the most visible change.** When a PR establishes a pattern, framework, or cleanup that later work builds on, name that intent rather than titling the PR after the one example that demonstrates it. A second clause is fine: "Add cancel button to jobs & establish the pattern for future buttons".

### Body: a Summary and a List of Changes are mandatory

Every PR body opens with:

1. **`## Summary`** — a short, plain-language paragraph stating the purpose of the change and its effect for the user, operator, or system. Written so the whole team can read it; implementation detail belongs in `## Detailed Description` below.
2. **`### List of Changes`** — a numbered list or a table. Each change has, at minimum, a plain user-effect description. Optionally add a column for the technical/implementation detail, plus any other helpful columns (affected area, risk, migration). Lead with the user-effect; do not reduce it to a bare list of class or method names.

### Examples

Real titles from this repository, drafted mechanism-first and then rewritten to lead with the effect:

| Drafted (mechanism) | Rewritten (effect) |
|----|----|
| `perf(api): rewrite collection counts as subqueries; trim capture list SELECT` | Speed up the captures list view |
| `perf(thumbnails): emit storage URL direct from serializer when cache is warm` | Option for thumbnails: store and serve full URLs instead of hitting the server |
| `feat(projects): wire session_time_gap_seconds into event grouping` | Allow users to customize the time gap between sessions |
| `fix(jobs): ack NATS after results-stage SREM; defer task_failure for in-flight async jobs` | Prevent jobs from hanging in STARTED state with no progress |
| `fix(newrelic): make app_name env-var-driven (drop from ini)` | Allow distinguishing data from different deployments in New Relic |

A few patterns worth copying:

- **Name the framework, not the demo.** `feat(post-processing): admin scaffolding precursor (pydantic schema, form base, parameterized template)` became *Framework for admins to trigger and review post-processing methods* — the title captures the capability, not the one example that exercises it.
- **Don't ship the branch-name auto-title.** `gh pr create` pre-fills the title from the branch slug, so titles like `Feat/taxa-covers` or `Fix/celery workers` slip through. Rewrite them: the latter became *Fix background tasks from disappearing*.

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

## Domain Invariants & Correctness Rules

Silent-bug classes that reviewers have caught repeatedly. None of these are visible in a diff — check for them explicitly.

- **One feature extractor per similarity/clustering query.** Any query over classification features or embeddings MUST constrain to a single algorithm (feature extractor), otherwise the results are random noise. If a cross-algorithm query is intentional, document it with an inline comment.
- **`timezone.now()` vs `datetime.now()`**: use `django.utils.timezone.now()` for "now" timestamps. Use `datetime.now()` only when deliberately working with a deployment's local capture time, with a comment saying so.
- **ML-backend schema boundary**: schemas in `ami/ml/schemas.py` define the contract with external processing services. They must not reference Antenna-side concepts (projects, users, permissions) — the processing service never knows about them.
- **Raise, don't return sentinels.** Failure paths raise exceptions (or surface DRF 4xx via serializer validation) — never return an empty/None "success" response on error.
- **No `assert` in production code.** Assertions are stripped under `python -O`. Raise explicit exceptions.
- **Model change ⇒ migration in the same PR.** Run `python manage.py makemigrations --check --dry-run` before pushing (CI enforces this). A missing migration discovered mid-branch that belongs to main gets its own PR branched from main.

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

### Testing worktree changes against main stack

Two routes — bind-mount worktree subdirs into the main stack (code-only changes, keeps real data) or run a duplicate stack from the worktree (full isolation, fresh empty volumes). Procedures, caveats, and cleanup steps: `docs/claude/reference/worktree-testing.md`.

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
- Status stored in `ProcessingService.last_seen_live` boolean field
- Async/pull-mode services update status via `mark_seen()` when they register pipelines
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

## Database Schema & Query Patterns

Full reference moved to dedicated docs — load on demand:

- `docs/claude/reference/query-patterns.md` — model relationship table, composite indexes, prefetch/select_related patterns, the full custom QuerySet method catalog, and query anti-patterns.
- `.agents/DATABASE_SCHEMA.md` — visual ERD (Mermaid) organized by domain layers.

Always-on rules (the most common review findings in this repo's history):

- **Always filter by `project` first** on Occurrence/SourceImage/Event queries — the composite indexes lead with it, and it enforces visibility.
- **Use the custom QuerySet methods** (`apply_default_filters()`, `with_taxa_count()`, `visible_for_user()`, etc.) instead of reimplementing filters — see the catalog in query-patterns.md.
- **Never materialize unbounded querysets** (`list(qs)`, Python-side aggregation over rows). Use SQL-side `aggregate()`, annotations, or subqueries — production projects have >100k occurrences.
- **No queries inside loops.** Batch with `__in`, `prefetch_related`, or subqueries.

## Definition of Done — Checklists

These map 1:1 to the most frequent review findings across this repo's history. Run through the matching checklist before opening a PR.

### Any new or changed API endpoint / queryset

- [ ] Permissions: viewset sets `require_project` explicitly (`ProjectMixin`, `ami/base/views.py`); object access goes through `get_object()` / `check_object_permissions()` — never a raw pk lookup.
- [ ] Permission matrix test: member / non-member / anonymous / superuser (template: `ami/main/tests.py:1532`).
- [ ] Default filters: occurrence-related querysets go through `apply_default_filters(project, request)`. Grep call sites of the filter the new code path *should* be using and confirm it does — this bug class is invisible in the diff.
- [ ] No PII in serializers: nested user serializers expose name/image only — never `email`.
- [ ] Every query param parsed via `SingleParamSerializer` (`ami/base/serializers.py`) or `url_boolean_param` (`ami/utils/fields.py`) so invalid input returns 400, not 500. Test the `?param=abc` case.
- [ ] Aggregation happens in SQL. Add an `assertNumQueries` test with a **multi-row** fixture — single-row fixtures cannot catch N+1 (example: `ami/ml/tests.py:1006`). Use strict `==` counts in assertions.
- [ ] Reuse existing patterns before writing new ones — see `docs/claude/reference/canonical-patterns.md`.

### Any model change

- [ ] Migration included in this PR (`makemigrations --check --dry-run` passes).
- [ ] `update_calculated_fields()` called after bulk operations that affect cached counts.
- [ ] No `print()` or debug code in migrations.

### Frontend change

- [ ] Follow `ui/CLAUDE.md` (loads automatically when editing files under `ui/`).

### Before requesting review (any PR)

- [ ] Self-review the full diff: no WIP debris (commented-out code, stale `noqa`/TODOs, duplicated conditions, typos).
- [ ] Linters pass with the repo's pinned configs (pre-commit hooks; `cd ui && yarn lint` for frontend).
- [ ] PR title and description follow the conventions above — and are refreshed if scope changed during review.
- [ ] Feature spans FE+BE? Agree on the API contract (fields, nesting, lookup keys) in the issue *before* implementing. Mid-review contract renegotiation is the main cause of months-long PRs in this repo.

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

### E2E Testing & Monitoring Async Jobs

Run an end-to-end ML job test:
```bash
docker compose run --rm django python manage.py test_ml_job_e2e \
  --project 18 --dispatch-mode async_api --collection 142 --pipeline "global_moths_2024"
```

For monitoring running jobs (Django ORM, REST API, NATS consumer state, Redis counters, worker logs, etc.), see `docs/claude/reference/monitoring-async-jobs.md`.

### Chaos testing async_api jobs (Redis/NATS fault injection)

Unit tests for the async result handler do not exercise `autoretry_for`, real Celery retry backoff, or the NATS redelivery boundary. For changes to `ami/jobs/tasks.py::process_nats_pipeline_result` or `ami/ml/orchestration/async_job_state.py`, follow the fault-injection runbook in `docs/claude/debugging/chaos-scenarios.md` against a live local stack.

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

**Agent reference docs (load on demand):**

- `docs/claude/INDEX.md` - Index of all agent docs (reference, runbooks, plans)
- `docs/claude/reference/canonical-patterns.md` - Existing helpers/patterns to reuse, with file:line refs
- `docs/claude/reference/query-patterns.md` - DB schema table, indexes, prefetch patterns, QuerySet method catalog
- `.agents/DATABASE_SCHEMA.md` - Visual ERD (Mermaid)
- `.agents/USER_PERMISSION_ROLES.md` - Permission roles reference
- `ui/CLAUDE.md` - Frontend conventions (i18n, types, mutations, naming, active lint rules)

## Automated Review Bots (CodeRabbit, Copilot)

- Bots flag lint rules that are **not in this repo's configs** (e.g. Stylelint rules — this repo has no Stylelint config). Check the actual config (`ui/.eslintrc.json`, `ui/.prettierrc.json`, `setup.cfg`) before "fixing" a bot finding.
- Bots are sometimes wrong. Verify empirically (library source, quick test) before implementing a suggestion; push back in the thread with evidence instead of blindly applying it.
- CodeRabbit skips reviews on PRs with more than ~150 changed files — another reason to split large PRs.

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
