# List-endpoint perf — continuation plan

**Date:** 2026-05-11
**Status (2026-05-12 update):**
- **PR-A (collection list subquery rewrite)** — superseded. The subquery shape benchmarked mixed on the row SELECT, and the paginator-COUNT win is invisible because the UI does not paginate collections. Replaced by a denormalize-counts-as-columns approach on its own branch (`perf/sourceimagecollection-cached-counts`).
- **PR-B1 (captures list `.only()` + data_source preload)** — in flight as PR #1300, scope renamed to "Speed up the captures list view".
- **PR-B2 / PR-C / PR-D / PR-E** — queued, see sections below.

**Companions:**
- [`2026-05-11-newrelic-post-upgrade-findings.md`](2026-05-11-newrelic-post-upgrade-findings.md) — prod NR data (DB visibility, top N+1s, conn-pool incident)
- [`2026-05-11-list-endpoint-perf-analysis.md`](2026-05-11-list-endpoint-perf-analysis.md) — root-cause SQL analysis for the same three endpoints (read first; this plan refers to its §1/§2/§3)
- [PR #1274](https://github.com/RolnickLab/antenna/pull/1274) — `OccurrenceViewSet` N+1 fix; merged 2026-05-11 23:46 UTC. Use as the template for solution shape *and* validation methodology

## What this plan is

A sequenced action plan for the **three list-endpoint hot paths** the analysis doc identified, plus the **one detail-endpoint hot path** the NR data surfaced post-merge. Numbered in suggested PR order. Each PR is independently mergeable.

Local-testable. Reuses PR #1274 measurement tooling.

## State at start of this plan

**Already in flight (this branch):**
- `SourceImageCollectionQuerySet.with_source_images_count` / `with_source_images_with_detections_count` / `with_source_images_processed_count` rewritten as correlated `Subquery(Count())` annotations (`ami/main/models.py:4074-4117`). Same fix shape as `SourceImageQuerySet.with_occurrences_count` (models.py:1865) and `with_taxa_count` (models.py:1893) — which were already using subqueries and carried `@TODO update the SourceImageCollectionQuerySet to use the same approach` (now removed).
- SQL verified via Django shell:
  - Annotated list: 3 independent scalar subqueries on `main_sourceimage` + the M2M through table only. No cartesian blowup.
  - Paginator count: collapsed to `SELECT COUNT(*) FROM main_sourceimagecollection WHERE project_id = ?`. No JOIN, no GROUP BY.
- `ami.main.tests -k SourceImageCollection` passes (9/9).

This is **planning-doc §1 option C + D** delivered as one change. Option A (gate behind `with_counts`) is not pursued because `capture-set-columns.tsx:101` uses `source_images_count` as a sort field — gating would break the list page without coordinated frontend work.

## Sequenced PRs

### PR-A — `SourceImageCollectionViewSet.list` subquery rewrite *(in flight)*

- Status: code written, unit tests pass, SQL verified. Needs query-count regression guard before commit.
- Effort: small. No migration. No API shape change. No frontend change.
- Risk: low — same pattern already in use on `SourceImageQuerySet`.
- Estimated payoff: planning doc measured ~13s of DB time/30min on this endpoint with 9 calls. Subquery rewrite eliminates the cartesian blowup; expected p99 drop from 10.5s → <2s based on the planner's ability to use the FK index per subquery.
- **Test before merge** (mirrors PR #1274 regression guard):
  - Add `TestSourceImageCollectionListQueryCount` to `ami/main/tests.py` using `CaptureQueriesContext` + `@override_settings(CACHALOT_ENABLED=False)`. Run `/captures-set/?project=X&limit=25`; assert query count ≤ small constant regardless of page size. Three variants: cold list, list with `?with_counts=1`, list with sort by `source_images_count`.
  - Local end-to-end: `docker compose run --rm django python manage.py test ami.main.tests -k Collection --keepdb` (already passing).
  - Local SQL inspection: `EXPLAIN ANALYZE` against demo DB for both shapes; confirm planner uses `main_sourceimagecollection_images_sourceimagecollection_id_idx` for each subquery.

### PR-B — `SourceImageViewSet.list` SELECT trim + paginator JOIN fix

References: `ami/main/api/views.py:475-583`. Planning doc §2.

- Two sub-changes, both small and zero-risk:
  1. **B1: Trim the SELECT** (§2.A). Replace the unconditional `select_related("event", "deployment")` with `.only("id", "path", "timestamp", "deployment_id", "deployment__name", "event_id", "event__start", …)`. Match exactly what `SourceImageListSerializer` reads. Halves row width.
  2. **B2: Drop the paginator JOIN** (§2.B). The endpoint currently scopes by `deployment__project` which forces the paginator's `COUNT(*)` to join `main_deployment`. `main_sourceimage` has a direct `project_id` FK — switching the project filter to `project=project` (or adding `.filter(project=project)` before the deployment-scoped filters in `get_queryset`) lets the paginator skip the JOIN.
- Effort: small. No migration.
- Risk: low. `.only()` is reversible; needs an audit of `SourceImageListSerializer` field access (model methods that touch un-loaded columns will trigger lazy loads → re-introducing N+1 silently).
- Skipped from §2: **C — composite index `(project_id, timestamp DESC)`** on `main_sourceimage`. Real win at scale but requires a `CONCURRENTLY` migration on a large table. Park for a follow-up PR with measured before/after; not urgent if B1+B2 land first.
- **Test before merge**:
  - Add `TestSourceImageListQueryCount` already exists from PR #1274 — extend it with `select_related` and `paginator-count` assertions. The existing test passes at 4 queries for `with_detections=true&with_counts=true`; should not regress.
  - Cold-row width check via Django shell: `print(SourceImage.objects.filter(project_id=X).only(...)[0].__dict__)` — verify only-fields are loaded, no `_deferred_fields` cascade in serializer access.

### PR-C — `SourceImageViewSet.retrieve` audit *(NEW from NR data)*

References: `ami/main/api/views.py:548-574`. **Not covered in the planning doc.**

- NR observed **571 DB calls / 1.5s** on a single `/captures/<id>/` request (newrelic-post-upgrade-findings §2). Likely culprits:
  1. **`prefetch_detections(queryset, project)` on retrieve** (views.py:561) — runs the same `filtered_detections` Prefetch the list uses, but on a detail object. The nested Prefetch attaches `occurrence` + `occurrence__determination` to every detection. With ~100s of detections per high-traffic image, the inner `Max("occurrence__detections__classifications__score")` subquery can fire per row.
  2. **`add_adjacent_captures()`** (views.py:637-688) — wires four subqueries (next, previous, index, total) into the queryset. Cheap per subquery but adds 4 to the floor count.
  3. **`with_occurrences_count()` + `with_taxa_count()`** annotations (views.py:567-572) applied on `with_counts_default=True` for retrieve.
- Effort: medium. Likely needs an audit pass like PR #1274's: ([what does the serializer actually read?]→[which prefetches/annotations are required?]→[remove the rest]).
- Approach: mirror PR #1274 exactly:
  - Create `ami/main/models_future/source_image.py` with `prefetch_detections_for_detail()` (only nested relations the detail serializer reads).
  - Add `SourceImageQuerySet.with_detail_prefetches()`.
  - Wire `get_queryset` to call it for the retrieve action; remove the bespoke `prefetch_detections` reuse-on-retrieve.
  - Add `_require_prefetch()` strict gate on any model methods the detail serializer calls that depend on prefetched detections.
- **Test before merge**:
  - Add `TestSourceImageRetrieveQueryCount` — single-row fetch should be a small constant of queries (target ≤10) regardless of detection count.
  - Synthetic test with 1 / 50 / 500 detections per image; assert query count does **not** scale with detection count.

### PR-D — `SourceImageCollectionViewSet.populate` / `add` and other endpoint shape

Out of scope for this plan. Mentioning to flag: those write paths (views.py:767, 813) call `collection.images.count()` and `collection.images.add(...)` synchronously. If we move to denormalized count columns (planning doc §1.B as a longer-term direction), those write paths become the natural maintenance points. Not blocking PR-A.

### PR-E — `ProjectViewSet.charts` (out of critical path)

Planning doc §3. NR shows 7.6s tail with 36 queries — aggregate-bound, not N+1. Three fix candidates in the planning doc. **A (cachalot pinning)** is the right first step: chart freshness on the order of minutes is acceptable, and the existing cachalot infrastructure already covers it. Separate ticket.

## Comparison vs PR #1274 approach

| Concern | PR #1274 (Occurrence list) | PR-A (Collection list) | PR-B (SourceImage list) | PR-C (SourceImage retrieve) |
|---|---|---|---|---|
| **Problem shape** | True N+1 (1.6 extra queries/row) | Annotation-aggregate cartesian (1 big query × 4 tables) | Wide-row + paginator JOIN | Suspected N+1 on detail |
| **Solution shape** | Strict prefetch factories + `_require_prefetch` gate | Correlated `Subquery(Count())` | `.only()` + filter rewrite | Likely same as #1274 (prefetch factory + strict gate) |
| **New module needed?** | Yes (`models_future/occurrence.py`) | No | No | Yes (`models_future/source_image.py`) |
| **API shape change?** | List `detection_images` capped at 1 (was unbounded) | None | None | TBD |
| **Migration?** | None | None | None (C in §2 adds one, deferred) | None |
| **Tests** | `TestOccurrenceListQueryCount`, `TestOccurrenceDetailQueryCount`, `TestOccurrencePrefetchHelpersEdgeCases` | `TestSourceImageCollectionListQueryCount` (new) | Extend existing `TestSourceImageListQueryCount` | `TestSourceImageRetrieveQueryCount` (new) |
| **Local benchmark** | `scripts/benchmark_occurrences_list.sh` | Reuse with `--endpoint=/captures-set/` parametrization | Same; already has it | Same with `--endpoint=/captures/<id>/` |

**Key takeaway**: only PR-C (and possibly a §1.B follow-up) needs PR #1274's `_require_prefetch` strict-contract machinery. PR-A and PR-B are smaller SQL-shape changes that don't need a new helper module — the QuerySet rewrite is the whole fix.

## Local validation methodology

For every PR in this plan:

1. **Cold query count regression test.** Pattern (mirrors `ami/main/tests.py::TestOccurrenceListQueryCount`):
   ```python
   from django.test.utils import CaptureQueriesContext
   from django.db import connection
   from django.test import override_settings

   @override_settings(CACHALOT_ENABLED=False)
   def test_<endpoint>_list_query_count(self):
       # warmup (load app, perm cache)
       self.client.get(f"{URL}?limit=5")
       self.client.get(f"{URL}?limit=5")
       with CaptureQueriesContext(connection) as ctx:
           response = self.client.get(f"{URL}?limit=25")
       self.assertLess(len(ctx.captured_queries), N)
   ```
   `@override_settings(CACHALOT_ENABLED=False)` is critical — cachalot otherwise hides the N+1 on warm DB.

2. **SQL shape inspection.** Django shell:
   ```python
   qs = <model>.objects.<chain>(...)
   print(str(qs.query))            # annotated list SQL
   from django.db import connection
   qs.count()
   print(connection.queries[-1]['sql'])  # paginator count SQL
   ```

3. **Local stack DB benchmark.** Against the demo project (`create_demo_project`):
   ```bash
   docker compose exec django python manage.py shell -c "
   from django.test.utils import CaptureQueriesContext
   from django.db import connection
   from django.test.client import Client
   c = Client()
   c.force_login(<user>)
   with CaptureQueriesContext(connection) as ctx:
       r = c.get('/api/v2/captures-set/?project=1&limit=25')
   print(f'{len(ctx.captured_queries)} queries, {r.status_code}')
   "
   ```

4. **EXPLAIN ANALYZE on a real-data DB copy** (where available — staging arbutus-2026 has the production schema and realistic row counts). Confirms the planner picks the FK index per subquery on PR-A and confirms the paginator drops the JOIN on PR-B.

5. **A/B concurrent load** (only for PRs likely to affect saturation behavior — PR-A and PR-B). Reuse PR #1274's `scripts/benchmark_occurrences_list.sh` with `--endpoint` switched. The pattern: 10/40 concurrent × limit=25/100, p50/p95/p99/max + per-status error counts. Run against `arctia.dev` or equivalent staging.

## Open follow-ups (won't block this plan)

- **Tracked separately**: `SourceImageViewSet.retrieve` — file ticket and reference NR data + this plan's PR-C row.
- **Tracked separately**: `ProjectViewSet.charts` cachalot pinning — planning doc §3.
- **Maybe revisit**: composite index `main_sourceimage(project_id, timestamp DESC)` after PR-B is in prod for a week. If `SourceImageViewSet.list` p95 is still above target (~1s), the index is the next lever.
- **From PR #1274's deferred list**: expose `?detection_images_limit=N` query param on `OccurrenceViewSet` — relevant once tracking-merged occurrences are common. Cross-reference: that PR caps at 1 (list) / 100 (detail) which works today.

## Why this plan, not a single mega-PR

- PR-A is **already coded**; merging it alone is a clean small win.
- PR-B is **independent of PR-A** (different endpoint, different DB tables). Bundling adds review surface for no shipping speedup.
- PR-C **needs new infrastructure** (`models_future/source_image.py`) and an audit pass; lumping it with PR-A/B would push the easy wins behind the hard one.
- PR #1274's audit-then-fix sequencing is the proven pattern. Apply it three times rather than once, each scoped to a single endpoint family.
