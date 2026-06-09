# docs/claude Index

Searchable index of agent-oriented docs in this repository. Search this file first
(`grep -i "keyword" docs/claude/INDEX.md`) before exploring the codebase from scratch.
Add a line here whenever a new doc is created; remove or move lines when docs are
archived.

## Reference (stable, load on demand)

| File | Description |
|---|---|
| `reference/canonical-patterns.md` | Existing helpers/patterns to reuse before writing new ones, with file:line refs (SingleParamSerializer, ProjectMixin, permissions, schemas, fixtures). Keywords: reuse, helpers, conventions, DRF |
| `reference/query-patterns.md` | DB model relationship table, composite indexes, prefetch/select_related patterns, full custom QuerySet method catalog, query anti-patterns. Keywords: N+1, indexes, ORM, performance |
| `reference/api-stats-pattern.md` | How to add aggregate/leaderboard/chart endpoints (`/<entity>/stats/<kind>/`): GenericViewSet + @action, pure querysets in models_future. Keywords: stats, charts, aggregation |
| `reference/monitoring-async-jobs.md` | Monitoring/debugging async_api (NATS JetStream) jobs: ORM, REST, consumer state, Redis counters, worker logs. Keywords: NATS, async, jobs, monitoring |
| `reference/worktree-testing.md` | Testing git-worktree changes against the main Docker stack: bind-mount route vs duplicate-stack route, caveats, cleanup. Keywords: worktree, docker compose, override |
| `reference/react-form-to-drf-values.md` | How form values travel from React Hook Form through the API into DRF serializers (empty string vs null vs undefined). Keywords: forms, serializers, frontend |
| `reference/captures-processed-count-strategies.md` | COUNT strategies for the captures `processed`/`has_detections` annotations (PR #1326). Keywords: captures, counts, performance |
| `reference/hierarchical-rollup-query-performance.md` | Per-taxon rollup counts on `GET /api/v2/taxa/` — query patterns and pitfalls. Keywords: taxa, rollup, counts |

## Architecture notes

| File | Description |
|---|---|
| `processing-lifecycle.md` | ASYNC_API job processing lifecycle, end to end. Keywords: NATS, dispatch, lifecycle |
| `job-dispatch-modes.md` | The job dispatch modes (sync/Celery/async_api) and how they differ. Keywords: dispatch, jobs |

## Debugging runbooks

| File | Description |
|---|---|
| `debugging/chaos-scenarios.md` | Fault-injection runbook for async_api jobs: Redis/NATS chaos, retry-path validation, `chaos_monkey` command. Keywords: chaos, Redis, NATS, retry |
| `debugging/row-lock-contention-reproduction.md` | Reproducing `jobs_job` row-lock contention on a local stack. Keywords: locks, postgres, contention |

## Planning (point-in-time; may be superseded by merged code)

| File | Description |
|---|---|
| `planning/stats-list-pattern.md` | Deferred list/paginator pattern for stats endpoints — companion to api-stats-pattern.md |
| `planning/celery-queue-split-rollout.md` | Rollout plan for the Celery queue split (`feat/celery-queue-split`) |
| `planning/2026-05-28-captures-processed-filter-design.md` | Design: captures "Processed / Not processed" filter |
| `planning/2026-05-28-captures-processed-filter-plan.md` | Implementation plan (checkbox tasks) for the captures processed filter |

## Archive / session snapshots

| File | Description |
|---|---|
| `archive/pr-1296-occurrence-stats-migration.md` | Plan: migrate top-identifiers to /occurrences/stats/ (PR #1296) |
| `sessions/pr-1296-anna-original-body.md` | Snapshot of the original PR #1296 body, kept for reference |

## Related agent docs outside docs/claude/

| File | Description |
|---|---|
| `.agents/AGENTS.md` (symlinked as `CLAUDE.md`) | Main agent instructions: rules, checklists, invariants, commands |
| `.agents/DATABASE_SCHEMA.md` | Visual ERD (Mermaid) organized by domain layers |
| `.agents/USER_PERMISSION_ROLES.md` | Permission roles reference |
| `ui/CLAUDE.md` | Frontend conventions (i18n, types, mutations, naming, active lint rules) |
