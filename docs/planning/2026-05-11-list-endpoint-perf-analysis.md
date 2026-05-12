# List endpoint perf analysis — 2026-05-11

**Status:** observations + fix hypotheses, no PR yet.
**Source:** New Relic prod data, 30 min window after PR #1299 (NR agent 12.1.0 + tuned `function_trace`) and PR #1274 (Occurrence N+1 fix) shipped.

## tl;dr

`OccurrenceViewSet.list` is fixed (p95 dropped from ~35s in a prior incident to **0.93s**, DB share dropped from ~100% to 32%). Three remaining list-endpoint hot paths surfaced:

1. **`SourceImageCollectionViewSet.list`** — unconditional `COUNT(DISTINCT) FILTER (...)` annotations on a 4-table join. Two queries × ~5s each per page. p95 **10.58s**. Highest leverage.
2. **`SourceImageViewSet.list`** — wide SELECT pulling all `main_deployment` + `main_event` columns into every row; paginator COUNT(*) does the same JOIN. p95 **4.47s**.
3. **`ProjectViewSet.charts`** — full-table aggregates over `main_sourceimage` with `EXTRACT(HOUR|MONTH FROM timestamp)`. p95 **7.58s**. Lower frequency (~2/15 min), separate fix shape.

None of these are N+1 in the same sense as `OccurrenceViewSet.list` was; they're each a small number of expensive single queries.

## 1. SourceImageCollectionViewSet.list — annotation explosion

### Observation

NR captured the SQL via `record_sql = raw`. Each list request issues two queries:

**Query A (annotation, 6.14s top, ~1.5s typical):**
```sql
SELECT main_sourceimagecollection.*,
       COUNT(DISTINCT main_sourceimagecollection_images.sourceimage_id) AS source_images_count,
       COUNT(DISTINCT main_sourceimagecollection_images.sourceimage_id)
         FILTER (WHERE main_detection.bbox IS NOT NULL AND main_detection.bbox <> '...')
         AS source_images_with_detections_count,
       COUNT(DISTINCT main_sourceimagecollection_images.sourceimage_id)
         FILTER (WHERE main_detection.id IS NOT NULL)
         AS source_images_processed_count
FROM main_sourceimagecollection
LEFT JOIN main_sourceimagecollection_images
  ON main_sourceimagecollection.id = main_sourceimagecollection_images.sourceimagecollection_id
LEFT JOIN main_sourceimage
  ON main_sourceimagecollection_images.sourceimage_id = main_sourceimage.id
LEFT JOIN main_detection
  ON main_sourceimage.id = main_detection.source_image_id
WHERE project_id = %s
GROUP BY main_sourceimagecollection.id
LIMIT ?;
```

**Query B (paginator COUNT, 3.97s top, ~0.7s typical):**
```sql
SELECT COUNT(*) FROM (
  SELECT main_sourceimagecollection.id
  FROM main_sourceimagecollection
  LEFT JOIN main_sourceimagecollection_images ...
  LEFT JOIN main_sourceimage ...
  LEFT JOIN main_detection ...
  WHERE project_id = %s
  GROUP BY ?
) subquery;
```

Same 4-table join done twice. The 3 `COUNT(DISTINCT) FILTER (...)` aggregates walk every detection in every image in every collection in the project.

Sum across 9 calls in 30 min: **13.25s** of pure Query-A time. The same window had **6** `main_sourceimage.timestamp/select` calls @ avg 2.16s (those belong to `ProjectViewSet.charts` — see §3) — i.e. the collection-list endpoint, despite low call count, contributes meaningful DB load.

### Root cause

In `ami/main/api/views.py:715-719`:

```python
queryset = (
    SourceImageCollection.objects.all()
    .with_source_images_count()
    .with_source_images_with_detections_count()
    .with_source_images_processed_count()
    .prefetch_related("jobs")
)
```

The three count annotations are applied **unconditionally on the class-level `queryset`**, before `get_queryset()` runs. List requests pay even when the caller doesn't ask for counts.

Compare: in the same view (`SourceImageCollectionViewSet.get_queryset`, views.py:737-758), `with_occurrences_count` and `with_taxa_count` are correctly gated by `?with_counts=1`. The three image-counts predate that gating and were missed.

Annotation definitions live in `ami/main/models.py:4074-4101` (`SourceImageCollectionQuerySet.with_source_images_*`); the property fallbacks at `models.py:4201-4213` return `None` if pre-population missed.

### Fix candidates (ordered by reversibility)

**A. Gate the three count annotations behind `with_counts` (smallest change).**

Move the three `.with_*()` calls out of the class-level `queryset` and into the `if with_counts:` block in `get_queryset()`. Frontend consumers that today rely on the counts being free will need to pass `?with_counts=1`.

Risk: silently changes API shape for any caller that reads `source_images_count` without `with_counts`. They'd start getting `None`. Audit callers first.

**B. Replace annotation with denormalized columns on `SourceImageCollection`.**

Add three integer columns (`source_images_count`, `source_images_with_detections_count`, `source_images_processed_count`) updated by signal on `SourceImageCollection_images.through.{add,remove}` and `Detection.{create,delete}`. Same shape as `Deployment.captures_count` and friends already present on `Deployment` (see `models.py` `Deployment` model fields).

Risk: signal-based denormalization drifts under bulk ops. Need a periodic reconcile management command. Higher effort but cleanest read-path.

**C. Replace LEFT JOIN aggregates with correlated `Subquery(...)` annotations.**

```python
images_subquery = SourceImage.objects.filter(
    collections=OuterRef("pk")
).order_by()
annotate(
    source_images_count=Subquery(images_subquery.values("collections").annotate(c=Count("id")).values("c")),
    ...
)
```

PostgreSQL planner can index-scan each subquery against `main_sourceimagecollection_images` independently, avoiding the cartesian blowup of 3 distinct-count aggregates. Easier than B, less invasive than A.

**D. Fix the paginator JOIN (Query B) regardless of A/B/C.**

Even if the annotation goes, DRF's paginator currently issues `SELECT COUNT(*) FROM (<full annotated queryset>)`. Override `paginator.get_count` or use `qs.values_list("id").count()` style to bypass the annotated aggregate. This is independent of the annotation question.

### Recommended path

A + D for the immediate p95 drop; B as the longer-term cleanup. C is a fallback if A breaks the frontend in audit.

## 2. SourceImageViewSet.list — wide select + paginator

### Observation

Top main_sourceimage SQL last 30 min (NR datastore spans):

**Query A (list rows, 2.38s top, ~1.1s typical):**
```sql
SELECT
  main_sourceimage.<18 cols>,
  main_deployment.<25 cols>,
  main_event.<13 cols>
FROM main_sourceimage
LEFT JOIN main_deployment ON main_sourceimage.deployment_id = main_deployment.id
LEFT JOIN main_event ON main_sourceimage.event_id = main_event.id
WHERE ...
ORDER BY timestamp;
```

**Query B (paginator COUNT, 1.12s):**
```sql
SELECT COUNT(*)
FROM main_sourceimage
INNER JOIN main_deployment ON main_sourceimage.deployment_id = main_deployment.id
WHERE main_deployment.project_id = %s;
```

### Root cause

Three contributing factors, listed in order of suspected impact:

1. **`select_related("event", "deployment")` is unconditional** (views.py:539). Pulls full row of both tables every time. `SourceImageListSerializer` doesn't read most of those columns.
2. **Paginator JOIN is unnecessary.** `main_sourceimage` has `project_id` directly (`models.py` `SourceImage.project = ForeignKey(Project)`). The paginator joins to `main_deployment` only because the filter uses `deployment__project=...`. Filter could go via `project=...` instead.
3. **`order_by("timestamp")` without `(project_id, timestamp)` composite index.** `timestamp` alone is indexed (`models.py` `SourceImage.timestamp = DateTimeField(db_index=True)`), but a Project-scoped `ORDER BY timestamp` cannot use it efficiently.

### Fix candidates

**A. Trim the SELECT:** `queryset.only("id", "path", "timestamp", "deployment_id", "deployment__name", "event_id", "event__start", ...)` matching only the fields the list serializer reads. Halve the row width.

**B. Override `get_queryset` count path** for list — at minimum filter by `project=project` directly, not `deployment__project=project`. The DRF paginator then drops the JOIN.

**C. Add composite index** on `main_sourceimage(project_id, timestamp DESC)` via migration. Lets `ORDER BY timestamp` use an index range-scan for a project-filtered list.

A + B are zero-risk and recover most of the latency. C requires a migration (large table — `CONCURRENTLY` recommended).

## 3. ProjectViewSet.charts — full-scan aggregates

### Observation

Time-correlated to the `charts` action, not `SourceImageViewSet.list`:

```sql
-- 3.31s top
SELECT (timestamp)::date, EXTRACT(HOUR FROM timestamp), COUNT(*)
FROM main_sourceimage
WHERE project_id = %s AND timestamp IS NOT NULL
GROUP BY 1, 2 ORDER BY 1, 2;

-- 2.95s top
SELECT EXTRACT(MONTH FROM timestamp), COUNT(*)
FROM main_sourceimage
WHERE project_id = %s AND timestamp IS NOT NULL
GROUP BY 1 ORDER BY 1;
```

Source: `ami/main/charts.py:40,89,117`. The endpoint feeds the project dashboard's capture-heatmap and monthly-distribution charts.

### Root cause

Full-table aggregate over `main_sourceimage` filtered only by `project_id`. No index can usefully accelerate `EXTRACT(HOUR FROM timestamp)` because the function is applied per row.

### Fix candidates

**A. Cache the chart payload.** Cachalot is already enabled; can pin chart endpoints with a longer TTL (chart values change on capture ingest, not on user interaction). Lowest effort, highest user-facing win.

**B. Materialized aggregates.** Roll up per-(project, date, hour) into a denormalized table updated nightly. Reads are O(displayed range), not O(all captures).

**C. Functional index on `(project_id, date_trunc('hour', timestamp))`.** Useful if A and B are both off the table; less effective than B for the monthly aggregate.

A first — chart freshness on the order of minutes is fine for these views.

## What still won't surface in NR

- **Datastore spans aren't tagged with `transaction.name`** in the async-Django + Python agent path (`Span.trace.id` also null on Transaction events). Span→Transaction attribution is by `timestamp` correlation only. Documented blocker; see internal NR proposal.
- **Cachalot internals aren't auto-instrumented.** If chart caching (§3 A) is applied, cache hit/miss rate won't appear in NR. Would need an import-hook.

## Proposed sequencing

1. PR for §1.A + §1.D (gate annotations, drop paginator JOIN) — lowest risk, biggest p95 drop on the list page.
2. PR for §2.A + §2.B (trim SELECT, fix count filter) — independent.
3. Decision on §1.B (denormalized columns) before any other annotation-heavy view ships.
4. §3 in a separate ticket; not in the critical path.

## Verification protocol

For each PR, after merge to staging or a perf branch:

1. Run `OccurrenceViewSet.list` regression check first (PR #1274 baseline must not break). NR query: `SELECT percentile(duration, 95) FROM Transaction WHERE name = 'WebTransaction/Function/ami.main.api.views:OccurrenceViewSet.list' SINCE 1 hour ago`.
2. Hit the target endpoint with the same query the failing trace used (project_id known from the slow trace).
3. Compare NR p95 + the per-span `Datastore/statement/...` durations against the values in this doc.
4. Re-run with `?with_counts=1` to verify the gated path still works.

Numbers in this doc are **post-PR-#1274** prod data, 2026-05-11 ~23:50 UTC, 30-min window. Sample sizes are small for the rarer endpoints (Charts: 2 hits; SourceImageCollection.list: 9 hits) — treat the p95s as directional, not stable.
