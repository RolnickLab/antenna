# Captures list: `processed` / `has_detections` COUNT strategies

**Created:** 2026-05-29 (PR #1326). **Status:** reference — records a strategy that
was prototyped, benchmarked, and deliberately *not* shipped.

## Context

The captures list (`SourceImageViewSet`, `ami/main/api/views.py`) supports two
existence filters:

- `?processed=true|false` — capture has *any* `Detection` row, including the null
  markers (`NULL_DETECTIONS_FILTER = Q(bbox__isnull=True) | Q(bbox=[])`) that record
  a "processed, found nothing" result.
- `?has_detections=true|false` — capture has a *real* detection (bounding box
  present). Null markers excluded.

Both translate to an `EXISTS` / `NOT EXISTS` subquery against `main_detection`. The
**page of rows** is cheap (the `LIMIT` prunes early), but the **pagination COUNT**
has no `LIMIT`, so `NOT EXISTS` becomes an anti-join over the whole source-image
table.

## What shipped (PR #1326)

- `?processed=` / `?has_detections=` filters.
- Sortable `last_processed` column (correlated subquery: most recent detection
  `created_at`).
- Index `det_srcimg_created_idx` on `Detection(source_image, -created_at)`
  (migration `0088`) — supports the `last_processed` **sort**.
- The pagination COUNT uses the **default DRF count** (the plain anti-join). No
  custom count strategy.

## The strategy that was NOT shipped: count by subtraction

Prototype (reverted): a `SourceImagePagination` whose `get_count` computed the
existence-filter count without the anti-join:

```
total           = COUNT(*) over the project/event/deployment/collection-scoped captures
processed_count  = COUNT(DISTINCT source_image_id) off main_detection, scoped to the same captures
                   (has_detections: also .exclude(NULL_DETECTIONS_FILTER))

processed=true   -> processed_count
processed=false  -> total - processed_count
```

Both counts are exact. The cost scales with the number of *detection* rows rather
than the processed/unprocessed ratio, so it is symmetric (fast in both directions).
Implementation notes if it is ever revived:

- DRF sets `paginator.request` *after* `get_count()` runs, so `paginate_queryset`
  must stash `request` + `view` first.
- The base queryset (scoped, but *without* the processed/has_detections predicate)
  was rebuilt in the view by applying only `DjangoFilterBackend` — *not* the
  ordering backend, which would reference the absent `last_processed` annotation.
- The detection-side count used `Detection.objects.filter(source_image__in=base.values("pk"))`.
  This is an `IN (subquery)` semi-join; its plan is less predictable than a direct
  `source_image__project_id=` join (see cold-spike below).

## Why it was reverted

The original justification was a **12.8s** COUNT for `processed=false` on the
929k-capture project. Deploy-time benchmarking on the Serbia dev box (hardware
comparable to production) showed that number does not reproduce there.

### Benchmarks

Local dev box (cold, low RAM, 8 GB source-image table not cached) — the numbers
that originally motivated subtraction:

| project | filter | default anti-join | subtraction |
|---|---|---|---|
| 18 / 929k (local) | processed=false | **12.8s** | ~1.7s |
| 18 / 929k (local) | processed=true | 4.8s | ~1.7s |
| 18 / 929k (local) | has_detections=false | 11.5s | ~1.9s |
| 18 / 929k (local) | has_detections=true | 3.5s | 0.2s |

Serbia dev box (cold), real data — the numbers that changed the decision:

| project | filter | default anti-join | subtraction |
|---|---|---|---|
| 18 / 929k | processed=false | **1.38s** | 0.58s |
| 18 / 929k | processed=true | 1.52s | 0.58s |
| 20 / 105k | processed=true | 0.44s | **7.71s cold** / 0.01s warm |
| 20 / 105k | processed=false | 0.27s | 0.04s |

Counts matched exactly across both approaches (subtraction is correct):
project 18 → 17938 / 910996; project 20 → 8517 / 96574 (processed),
8476 / 96615 (has_detections).

### Findings

1. **The 12.8s was environment-dependent, not algorithmic.** `EXPLAIN (ANALYZE)`
   for `processed=false` on project 18 (Serbia):

   ```
   Finalize Aggregate (actual time=1541..1567)
     -> Parallel Hash Right Anti Join (rows=303665)
          -> Parallel Seq Scan on main_detection (rows=455239)
          -> Parallel Hash
               -> Parallel Seq Scan on main_sourceimage (Filter: project_id = 18)
   Execution Time: 1609 ms
   ```

   The anti-join seq-scans the wide source-image table. Serbia's RAM / OS cache /
   parallel workers do it in ~1.6s; the local box did it in 12.8s cold. Serbia ≈
   production, so the real-world cost is far smaller than the local measurement.

2. **`det_srcimg_created_idx` is not used by the COUNT** — the anti-join plan
   ignores it. It only helps the `last_processed` sort. So the index already in the
   PR does nothing for the count either way.

3. **Subtraction has its own cold-plan risk.** On the *smaller* project 20 the
   detection-side `IN (subquery)` distinct spiked to 7.71s on first disk touch
   (cold seq scan of `main_detection`), settling to sub-second warm — *slower* than
   the 0.44s default for that case. `EXPLAIN` (warm) = 634ms via a nested-loop +
   pkey memoize + distinct.

Net: subtraction is a modest, real win on the largest project (0.58 vs 1.38s) and
would protect a cold / memory-pressured environment, but it adds a custom paginator
+ base-queryset rebuild + a second query and an unpredictable cold-plan, for a
benefit that is small on production-class hardware. Not worth it for this PR.

## General direction

The durable fix for "COUNT is slow on huge filtered lists" is not per-filter
bespoke counting — it is an **estimated-count paginator** (ticket #1328): use the
PostgreSQL planner's row estimate (`EXPLAIN (FORMAT JSON)` → `Plan["Plan Rows"]`,
<15ms, ~3% accurate where it matters) with an exact-count fallback below a
threshold. That handles *any* filter, not just existence filters. Subtraction
(exact, existence-filters-only) remains a possible fast path to layer underneath it
if exactness is required. See also the annotation-strip count trick in
`ProjectPagination.get_count` and PR #1317.
