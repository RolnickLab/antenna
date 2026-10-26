# Per-taxon rollup counts on the taxa endpoint — query patterns and pitfalls

How to compute per-taxon counts on `GET /api/v2/taxa/` that roll up
descendant occurrences (a Family/Order row aggregating its species) without
timing out the list endpoint on large projects. Generalises to any "aggregate
over a taxon node and all its `parents_json` descendants" problem.

Canonical reference for PR #1317 (verification status on taxa views, issue
#1316) and follow-up #1319 (model-agreement stats — deferred).

Reference implementations in `ami/main/models.py`:

- `TaxonQuerySet.with_observation_counts_subqueries` (default path, correlated `Subquery`)
- `TaxonQuerySet.with_observation_counts_aggregated` (collection path, conditional aggregation)
- `TaxonQuerySet.observed_in_project_subqueries` (membership filter for default path)
- `TaxonQuerySet.with_verification_counts` (sparse `CASE`-from-map rollup)

Reference orchestrator in `ami/main/api/views.py`:

- `TaxonViewSet.get_taxa_observed` (dispatches between the two count shapes)

## TL;DR

- **Do not** roll up with a per-taxon correlated `parents_json @> [{"id": OuterRef}]`
  subquery. A containment whose RHS is an `OuterRef` can't use the GIN index, so it
  degrades to a per-row seq-scan that runs once per page row **and** once per taxon in
  the pagination `COUNT`.
- **Do** precompute when the driving data is *sparse*: one pass over the small set,
  build `{taxon_id: count}` dicts (incrementing the determination taxon + every
  ancestor in `parents_json`), then apply as constant-time `CASE` annotations. Resolve
  any membership filter from the same set via `id__in`.
- For *dense* per-taxon aggregates (one value per observed taxon: occurrences_count,
  best_determination_score, last_detected) the right shape depends on whether the
  occurrence filter joins detections: correlated `Subquery` per row when it does not,
  conditional aggregation over the reverse relation when it does.
- The GIN index (`main_taxon_parents_json_gin_idx`, migration `0087`) only helps the
  **literal**-RHS containment filters (occurrence-list `taxon=<id>`,
  `build_occurrence_default_filters_q`), not correlated ones.

## When to use which mechanism

| Driving set | Shape | Method | Why |
|---|---|---|---|
| Sparse (e.g. verified subset, bounded by review effort) | Python pass + `CASE`-from-map | `with_verification_counts` | Constant-time per row, DB-sortable, stripped from pagination `COUNT`. Sparse maps stay under sqlparse's 10000-token limit. |
| Dense, no detections join (default / event / deployment / verified / ordering paths) | Three correlated `Subquery` annotations | `with_observation_counts_subqueries` + `observed_in_project_subqueries` | Index-served by the composite `(determination_id, project_id, event_id, determination_score)` index on Occurrence. Membership materialised as `id__in`. |
| Dense, detections join in play (`?collection=<id>`) | Conditional aggregation over the Taxon→occurrences reverse relation | `with_observation_counts_aggregated` | One `GROUP BY`, constant-size SQL. The detections join turns each correlated `Subquery` into a per-row scan; the aggregate dedupes via `Count(distinct)` and replaces the membership query with a HAVING (`occurrences_count__gt=0`). |

The dispatch is in `TaxonViewSet.get_taxa_observed` and keys on whether
`"collection" in request.query_params` — that is the only filter on this viewset
that currently induces a detections join. Add new join-inducing filters to the
same branch.

The sparse verification rollup is the same on both paths — it queries Occurrence
directly with the same `occurrence_filters` Q, regardless of whether the
observation counts are subqueries or aggregates.

## The anti-pattern (does not scale)

```python
# Per-taxon correlated subquery — OuterRef RHS, can't use the GIN index.
descendant_match = JSONBContains(
    F("determination__parents_json"),
    jsonb_build_array(jsonb_build_object("id", OuterRef("id"))),
)
under_taxon = Occurrence.objects.filter(...).filter(
    Q(determination_id=OuterRef("id")) | Q(_under_taxon=True)
)
qs.annotate(verified_count=Coalesce(Subquery(under_taxon.values("project_id")
    .annotate(c=Count("id")).values("c")[:1]), 0))
```

Measured on a ~1k-taxa / ~17k-occurrence project (statement_timeout = 30s):
`limit=25` page **9s** for one such annotation; with two always-on annotations the
default list and `verified=false` hit the 30s timeout; `ordering=verified_count`
timed out (the subquery is computed for *every* taxon before the LIMIT).

Standalone, the same containment for **one** constant taxon id is ~70ms (it uses the
index). The cost is the correlation: per outer row the planner can't use the index for
a parameterised `@>` and re-evaluates the join. **Always benchmark the correlated form,
not the standalone query.**

## The sparse pattern (precompute over the small set + CASE)

Key observation: the verification counts only concern *verified* occurrences (those
with a non-withdrawn `Identification`), which are sparse — bounded by human review
effort, not total occurrences.

```python
verified_occ = (
    Occurrence.objects.filter(occ_filters)
    .filter(default_filters_q)
    .filter(Exists(Identification.objects.filter(occurrence=OuterRef("pk"), withdrawn=False)))
)

# ``pk`` in value_fields + ``.distinct()`` dedupes occurrences when occ_filters
# joins to detections (see "Detection fan-out" below).
counts: dict[int, int] = {}
for row in verified_occ.values("pk", "determination_id", "determination__parents_json").distinct():
    taxon_ids = {row["determination_id"], *(_id(p) for p in row["determination__parents_json"] or [])}
    for tid in taxon_ids:
        counts[tid] = counts.get(tid, 0) + 1

case = Case(*(When(id=tid, then=Value(c)) for tid, c in counts.items()),
            default=Value(0), output_field=IntegerField()) if counts else Value(0, ...)
qs = qs.annotate(verified_count=case)

# Membership filter from the same precomputed set:
qs.filter(id__in=list(counts)) / qs.exclude(id__in=list(counts))
```

Same project, after: every path (`default`, `verified=true/false`,
`ordering=verified_count`) ~1.1s cold. Cost is `O(verified occ × ancestor depth)`,
paid once per request. The `CASE` annotation is a constant per row → DB-sortable,
paginatable, and stripped from the pagination `COUNT`.

### Why this keeps `COUNT` cheap

Django's `QuerySet.count()` strips **select-only** annotations it doesn't need — so the
`CASE` annotations don't appear in the pagination `COUNT`. Two things defeat that strip
and were the original timeout:

- A filter that *references* the expensive expression — e.g. `verified=false` as
  `~Exists(correlated_subquery)` forces the subquery into the `COUNT` WHERE for every
  taxon. Resolving the filter via `id__in=<constant set>` avoids it.
- `.distinct()` combined with select annotations (wraps the whole annotated query in the
  `COUNT` subquery). Watch for it on list viewsets.

## The dense pattern (conditional aggregation over the reverse relation)

For dense per-taxon aggregates — one value per observed taxon, e.g. `occurrences_count`
/ `best_determination_score` / `last_detected` for a project's ~hundreds-to-thousands
of taxa — the sparse `CASE`-from-map fails: one `When` branch per taxon blows past
`sqlparse`'s parser limit and the query fails with
`SQLParseError: Maximum number of tokens exceeded (10000)`.

Use conditional aggregation over the Taxon→occurrences reverse relation:

```python
count_filter = (
    self.get_occurrence_filters(project, accessor="occurrences")
    & build_occurrence_default_filters_q(
        project, request, occurrence_accessor="occurrences",
        apply_default_score_filter=True,
        apply_default_taxa_filter=False,  # see "Two gotchas" below
    )
)
qs = qs.annotate(
    occurrences_count=Count("occurrences", filter=count_filter, distinct=True),
    best_determination_score=Max("occurrences__determination_score", filter=count_filter),
    last_detected=Max("occurrences__detections__timestamp", filter=count_filter),
).filter(occurrences_count__gt=0)  # HAVING — replaces the EXISTS membership query
```

One `GROUP BY`, constant-size SQL, scales in both taxa and occurrences. `Count(distinct)`
dedupes the detections fan-out under `?collection=`. The HAVING replaces a separate
membership query (the determination ids present in the filtered set are exactly the
observed taxa).

This is also the right shape for `with_charts=...` style endpoints or any other
aggregation over a join — it's the general pattern, not collection-specific.

### Two gotchas that turn fast conditional aggregation into a multi-minute scan

1. **Do not include the default *taxa* include/exclude filter in `count_filter` when
   the count groups by `determination = the taxon row`.** The filter is redundant
   (`filter_by_project_default_taxa` already keeps/drops the row at the queryset
   level), and including it adds a `parents_json` containment join inside the
   aggregate that the planner cannot reconcile with the detections join from
   `?collection=` — measured 0.3s → 182s on a ~1k-taxa project. Keep only the score
   threshold (per-occurrence, not redundant). The verification rollup *base* (which
   queries Occurrence directly and rolls up to ancestors) does still need the taxa
   filter, and pays no cost because its driving set is sparse.

2. **Audit `filter_backends` for redundant collection / event JOIN filters before
   adding conditional-aggregate annotations.** A backend like
   `queryset.filter(occurrences__detections__source_image__collections=<id>)` was
   harmless on top of correlated subqueries but, combined with the aggregate
   `GROUP BY`, induces an INNER JOIN that multiplies taxon rows and breaks the planner.
   Express the filter once — inside the aggregate (`accessor="occurrences"`) — and
   remove the backend, since the HAVING already enforces membership. (`TaxonCollectionFilter`
   was removed for this reason in PR #1317.)

## Detection fan-out under `?collection=<id>`

When `occurrence_filters` joins to detections (because `?collection=<id>` resolves to
`detections__source_image__collections=<id>`), a single Occurrence yields one row per
matching Detection in `.values(...)`. Without dedup the rollup counts every detection
as if it were a separate verified occurrence.

The fix in `with_verification_counts`:

```python
value_fields = ["pk", "determination_id", "determination__parents_json"]
# ...
verified_occ.values(*value_fields).distinct()
```

`pk` is selected only so that `.distinct()` can dedupe by Occurrence. Regression test:
`test_verified_count_not_inflated_by_collection_join` in
`ami/main/tests.py::TestTaxaVerification`.

The aggregate path uses `Count("occurrences", filter=count_filter, distinct=True)`
which serves the same dedup role for the dense per-taxon counts.

## Gotchas

- **`cachalot` caches query results**, including across repeated benchmark runs — a second
  identical timing is a cache hit, not a real measurement. Flush between paths with
  `docker compose exec -T redis redis-cli FLUSHALL`, or wrap timing in
  `from cachalot.api import cachalot_disabled` → `with cachalot_disabled(): ...`.
- **`django-pydantic-field` `.values()` returns deserialised pydantic objects**, not
  dicts. `parents_json` elements may be `TaxonParent` objects depending on the query
  path, so read the id defensively:

  ```python
  parent_id = parent.get("id") if isinstance(parent, dict) else getattr(parent, "id", None)
  ```

  This silently broke ancestor rollup in an earlier revision — direct/species counts
  worked, ancestors were 0.
- **GIN `jsonb_path_ops` only serves `@>` with a constant RHS.** Literal
  `parents_json__contains=[{"id": X}]` uses the index; an `OuterRef` RHS does not.
- **`Family/Order` rows can show `verified_count > occurrences_count`** because the
  former rolls up descendants while the latter is direct-match. Document this in API
  consumers if it might confuse readers.

## Why model-agreement stats were split out (#1319)

The verification surface (`verified_count`, `verified=true|false` filter) measures
human trust — "how much of this taxon is human-reviewed?" Model-agreement stats
(`agreed_with_prediction_count`, `agreed_exact_count`) measure ML evaluation — "how
often does the model match humans?" Different audiences (naturalists vs ML team) and
different consumers; bundling them into one PR without a FE consumer for the
agreement surface produced dead API columns, naming friction (`agreed_*` was ambiguous
between human and machine signals), and parser duplication (one in serializer, one in
view).

PR #1317 ships the verification surface only. Follow-up issue #1319 carries the
agreement stats with these implementation guardrails preserved:

- Reuse the sparse `CASE`-from-map pattern over the verified subset — both
  `agreed_with_prediction_count` and `agreed_exact_count` are bounded by the verified
  set, so they stay sparse.
- Extend `with_verification_counts` with an `include_agreement` flag and the
  `_best_machine_taxon_id` (`Classification` subquery ordered by
  `BEST_MACHINE_PREDICTION_ORDER`) + `_agreed_prediction_id` (`Identification`
  subquery ordered by `BEST_IDENTIFICATION_ORDER`) annotations from the original
  revision.
- Rename to `model_agreed_*` prefix to disambiguate from human verifications.
- Gate behind `?with_model_agreement=true` on the list endpoint to keep the default
  cheap; detail view always includes.
- Pass the gate flag through serializer context (single parser), not re-parsed in the
  serializer.
- Port the regression tests (rollup, chosen-identification-only, gated-on-list,
  detection-dedup) with the new names.

## Future direction — denormalised per-project observed taxa

The precompute approach scales with verified-data volume. If per-project taxa
aggregates (observed counts, verified counts, agreement) become a recurring perf
problem across endpoints, consider a dedicated **`TaxonObserved`** model holding
denormalised data per `(project, taxon)` — distinct from the generic project-agnostic
`Taxon` profile — refreshed via the cached-count pattern
(`update_cached_counts(run_async=True)`) on `Identification` / `Occurrence` writes.
That moves the rollup off the read path entirely and makes counts directly sortable /
filterable as real columns. Open idea, not yet scoped.
