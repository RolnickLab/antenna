# Follow-up: CachedCountField drift reconciliation + periodic task + dashboard

**Status:** planned (split out of PR #1301 on 2026-05-15)
**Depends on:** PR #1301 (denormalized `SourceImageCollection` counts + `CachedCountField` marker) merged.

## Why this is a separate PR

#1301 ships the perf win (denormalized columns, signals, ML-path recompute,
`CachedCountField` marker, per-connection dedup scheduler). The generic
drift-reconciliation layer was removed from #1301 because it was not
production-wired and shipping it half-done is worse than not shipping it:

- The reconcile Celery task had **no beat schedule** — `CELERY_BEAT_SCHEDULER`
  is `django_celery_beat.schedulers:DatabaseScheduler` (`config/settings/base.py:413`),
  so periodic tasks live in the DB. #1301 added no `PeriodicTask` registration,
  so the "safety net" never actually ran.
- `reconcile_cached_counts` counted `checked` only for rows that **already
  drifted**, contradicting the `IntegrityCheckResult` contract
  (`ami/main/checks/schemas.py`: `checked` = rows inspected). A clean sweep
  reported `checked=0`, indistinguishable from "didn't run".
- Task default was `project_id=None, dry_run=False` → a full-table,
  repair-mode, per-row-subquery sweep across every `CachedCountField` model
  (incl. `SourceImage`, millions of rows). Dangerous default if naively
  scheduled.

Removed from #1301 (recover from git history at branch
`perf/sourceimagecollection-cached-counts` pre-2026-05-15):
- `ami/main/checks/cached_counts.py` (`discover_cached_count_fields`,
  `find_stale_cached_counts`, `reconcile_cached_counts`)
- `reconcile_cached_counts_task` in `ami/main/tasks.py`
- `TestCachedCountsIntegrityCheck` in `ami/main/tests.py`

The `CachedCountField` marker, `discover`-via-`_meta.get_fields()` approach,
and the design doc (`docs/superpowers/specs/2026-05-14-cached-counts-update-method-design.md`)
stay in #1301 — the follow-up builds on the marker.

## Scope of the follow-up

1. **Reconcile module** — restore `find_stale_cached_counts` /
   `reconcile_cached_counts`. Fix `checked` to increment per row inspected
   (in the iteration, not the drift branch). Keep `dry_run` and `project_id`
   scoping.
2. **Safe task defaults** — `reconcile_cached_counts_task` defaults to
   `dry_run=True`; repair mode must be explicit. Require either `project_id`
   or an explicit `model` for the repair path; refuse a full-table unscoped
   repair without an explicit `force=True`.
3. **Periodic task registration** — data migration creating the
   `django_celery_beat` `PeriodicTask` (dry-run mode, reasonable cadence,
   per-project fan-out rather than one unscoped sweep). Document how to
   enable repair mode per environment.
4. **Surface results** — dashboard / log destination for reconcile output
   (checked / fixed / drift detail). Decide: admin page, structured logs to
   the existing logging sink, or a lightweight status model. Drift events
   should be visible without grepping worker logs.
5. **Tests** — restore the integrity-check tests; add one asserting
   `checked` reflects rows inspected on a no-drift sweep (the bug the old
   `test_reconcile_no_drift_returns_zero_checked` baked in).

## Open questions

- Cadence + scoping: per-project nightly vs. one global weekly sweep. Per-row
  subquery recompute on `SourceImage` at prod scale is expensive — likely
  needs the bulk-subquery UPDATE path (`Project.update_related_calculated_fields`)
  rather than row-by-row `update_calculated_fields` for the big models.
- Whether reconcile should auto-repair or only alert + require a manual
  trigger for repair (safer; drift usually signals a missing signal/hook
  that should be fixed at the source, not papered over).

## Reconciler compute strategy: read-only vs upsert vs invalidate

We already have the read/write split on the eager path:
`SourceImageCollection.get_source_image_counts()` is pure-compute (one
aggregate, no writes); `update_calculated_fields(save=True)` is the
side-effecting upsert. That split is correct for the **signal** path but the
pure-compute read is the wrong primitive for a **sweep** — the removed
reconciler iterated rows calling it via `.iterator()`, which is N subquery
aggregates. Three named approaches, ranked:

1. **Set-based diff (eager fields, chosen).** One GROUP BY producing the true
   counts for every row in a single pass — this query already exists as the
   `0086_backfill_sourceimagecollection_counts` SQL. Reconcile = run it,
   compare to stored columns (`WHERE sc.x IS DISTINCT FROM c.x` to detect,
   `UPDATE ... WHERE` to repair only divergent rows). O(passes), not O(rows).
   Precedent: `Project.update_related_calculated_fields()` keeps a
   bulk-subquery UPDATE for `SourceImage.detections_count` rather than
   looping. **Implication:** the per-model "true value" query is the single
   source of truth; backfill, reconcile, and (where cheap) the signal path
   should all derive from it, closing the migration/runtime predicate-drift
   gap flagged in the takeaway review.

2. **Lazy invalidation (expensive fields, considered — see below).** Mark
   stale on a write criterion; recompute on read or on a prioritized sweep.
   Named pattern: *write-invalidate* / *cache-aside* with *TTL* or
   *generation/version stamping*. Not warranted for the cheap count columns
   (eager signal recompute is one aggregate per affected row), but it is the
   right path for future expensive caches.

3. **Generic per-row loop (diagnostic only).** Lowest-common-denominator,
   works for any `CachedCountField` model, slow at scale. Survives only as a
   scoped / `dry_run` diagnostic, never an unscoped repair sweep.

## Design space for future expensive cached fields (considered, not in scope)

Counts are cheap to recompute eagerly. Some cached values will not be — e.g.
a stored `best_machine_prediction_score` / `best_machine_prediction_taxon_id`
on `Occurrence` (today a queryset annotation, `with_best_machine_prediction`,
not a column). When a cached value is expensive, eager write-through stops
being viable and the field needs a **freshness signal**. Named options:

- **NULL-sentinel staleness.** Nullable column where `NULL` = "not computed /
  stale, recompute before trusting". Zero extra schema; this is *already* the
  de-facto contract for `Deployment.*_count` / `Event.*_count`
  (`blank=True, null=True`). Limitation: conflates "computed and genuinely
  empty" with "stale". Fine for counts (`NULL` ≠ `0`) and for FK/score caches
  (`NULL` = unknown). The "stale bit = set it to None" intuition is exactly
  this pattern.

- **Freshness-timestamp companion.** A sibling `<field>_computed_at`
  datetime; staleness = `computed_at IS NULL OR computed_at <= source_changed_at`
  (TTL or watermark). Precedent already in the codebase:
  `Event.calculated_fields_updated_at` (`models.py:1161`) gates recompute via
  `Q(calculated_fields_updated_at__isnull=True) | Q(...__lte=last_updated)`
  (`models.py:1346`). Preferred for expensive fields: enables TTL,
  oldest-first reconcile prioritization, and observability ("how stale is
  this?"). This is the "value + stale bit, two-part field" idea — the second
  part is a freshness timestamp, not a boolean.

- **Aggregates / rollup table (or materialized view).** For very expensive
  cross-table rollups, store the value out of the hot row entirely: a FK from
  the entity to a summary row, or a DB **materialized view** refreshed on a
  schedule. Data-warehouse name: *aggregate table* / *summary table*; the
  DB-maintained variant is a *materialized view* (`REFRESH MATERIALIZED
  VIEW`). Trades write-amplification for refresh latency; reconcile becomes
  "refresh the view" rather than per-row diff.

**Naming pathway (so future work has somewhere to land, no build now):**
keep `CachedCountField(IntegerField)` as the *eager write-through scalar*
marker. Reserve a sibling concept for *lazy / invalidatable* caches that
carry a freshness signal — a class such as `LazyCachedField` /
`InvalidatableCachedField`, distinguished by an associated `computed_at`
companion (or documented NULL-sentinel contract). The discovery mechanism
stays one `_meta.get_fields()` + `isinstance` sweep; the **marker class
hierarchy tells the reconciler which strategy applies**: eager → set-based
diff (approach 1); lazy → check freshness/NULL, then recompute or merely
invalidate (approach 2); rollup-backed → refresh the aggregate. One
enumeration, per-class strategy. This keeps #1301's marker the right shape
and leaves a clear, named path to the expensive cases without widening the
current PR.
