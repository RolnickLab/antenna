# Hierarchical (descendant) rollup counts — performant query patterns

How to compute a per-taxon count that rolls up descendant occurrences
(a Family/Order row aggregating its species) without timing out the list
endpoint on large projects. Generalises to any "aggregate over a node and
all its `parents_json` descendants" problem.

Reference implementation: `TaxonQuerySet.with_verification_counts` in
`ami/main/models.py` (verified_count / agreed_with_prediction_count /
agreed_exact_count for #1316). History: the first revision used the
anti-pattern below and timed out; commit `16b14686` switched to the pattern.
The logic moved from `TaxonViewSet.add_verification_data` → the queryset
method as part of the view→queryset refactor for #1317.

## TL;DR

- **Do not** roll up with a per-taxon correlated `parents_json @> [{"id": OuterRef}]`
  subquery. A containment whose RHS is an `OuterRef` can't use the GIN index, so it
  degrades to a per-row seq-scan that runs once per page row **and** once per taxon in
  the pagination `COUNT`.
- **Do** precompute when the driving data is *sparse*: one pass over the small set,
  build `{taxon_id: count}` dicts (incrementing the determination taxon + every
  ancestor in `parents_json`), then apply as constant-time `CASE` annotations. Resolve
  any membership filter from the same set via `id__in`.
- The GIN index (`main_taxon_parents_json_gin_idx`, migration `0087`) only helps the
  **literal**-RHS containment filters (occurrence-list `taxon=<id>`,
  `build_occurrence_default_filters_q`), not correlated ones.

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

## The pattern (precompute over the sparse set + CASE)

Key observation: the three counts only concern *verified* occurrences (those with a
non-withdrawn `Identification`), which are sparse — bounded by human review effort, not
total occurrences.

```python
verified_occ = Occurrence.objects.filter(occ_filters).filter(default_filters_q).filter(
    Exists(Identification.objects.filter(occurrence=OuterRef("pk"), withdrawn=False))
).annotate(_agreed_prediction_id=...)  # + _best_machine_taxon_id when gated

counts: dict[int, int] = {}
for row in verified_occ.values("determination_id", "determination__parents_json", ...):
    taxon_ids = {row["determination_id"], *(_id(p) for p in row["determination__parents_json"] or [])}
    for tid in taxon_ids:
        counts[tid] = counts.get(tid, 0) + 1

case = Case(*(When(id=tid, then=Value(c)) for tid, c in counts.items()),
            default=Value(0), output_field=IntegerField()) if counts else Value(0, ...)
qs = qs.annotate(verified_count=case)

# membership filter from the same precomputed set:
qs.filter(id__in=list(counts)) / qs.exclude(id__in=list(counts))
```

Same project, after: every path (`default`, `verified=true/false`,
`ordering=verified_count`) ~0.3s. Cost is `O(verified occ × ancestor depth)`, paid once
per request. The `CASE` annotation is a constant per row → DB-sortable, paginatable,
and stripped from the pagination `COUNT`.

### Why this keeps COUNT cheap

Django's `QuerySet.count()` strips **select-only** annotations it doesn't need — so the
`CASE` annotations don't appear in the pagination `COUNT`. Two things defeat that strip
and were the original timeout:
- a filter that *references* the expensive expression — e.g. `verified=false` as
  `~Exists(correlated_subquery)` forces the subquery into the `COUNT` WHERE for every
  taxon. Resolving the filter via `id__in=<constant set>` avoids it.
- `.distinct()` combined with select annotations (wraps the whole annotated query in the
  `COUNT` subquery). Watch for it on list viewsets.

## Gotchas

- **cachalot caches query results**, including across repeated benchmark runs — a second
  identical timing is a cache hit, not a real measurement. Wrap timing in
  `from cachalot.api import cachalot_disabled` → `with cachalot_disabled(): ...`.
- **`django-pydantic-field` `.values()` returns deserialised pydantic objects**, not
  dicts. `parents_json` elements may be `TaxonParent` objects depending on the query
  path, so read the id defensively: `p.get("id") if isinstance(p, dict) else getattr(p, "id", None)`.
  (This silently broke ancestor rollup — direct/species counts worked, ancestors were 0.)
- **GIN `jsonb_path_ops` only serves `@>` with a constant RHS.** Literal
  `parents_json__contains=[{"id": X}]` uses it; an `OuterRef` RHS does not.

## When to use which mechanism (sparse vs dense)

The CASE-from-map pattern above is the right tool **only when the map is sparse**.
For *dense* per-taxon aggregates — one value per observed taxon, e.g. the existing
`occurrences_count` / `best_determination_score` / `last_detected` for a project's
~hundreds-to-thousands of taxa — it does **not** work: one `When` branch per taxon
blows past `sqlparse`'s parser limit and the query fails with
`SQLParseError: Maximum number of tokens exceeded (10000)`.

The scalable alternative for dense aggregates is **conditional aggregation over the
reverse relation** (already documented for Event counts in `build_occurrence_default_filters_q`):

```python
count_filter = (
    self.get_occurrence_filters(project, accessor="occurrences")
    & build_occurrence_default_filters_q(project, request, occurrence_accessor="occurrences", ...)
)
qs = qs.annotate(
    occurrences_count=Count("occurrences", filter=count_filter, distinct=True),
    best_determination_score=Max("occurrences__determination_score", filter=count_filter),
    last_detected=Max("occurrences__detections__timestamp", filter=count_filter),
).filter(occurrences_count__gt=0)  # HAVING — replaces the EXISTS membership query
```

One GROUP BY, constant-size SQL, scales in both taxa and occurrences. `Count(distinct)`
dedupes the detections fan-out under `?collection=`. The HAVING replaces a separate
membership query (the determination ids present in the filtered set are exactly the
observed taxa).

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
   GROUP BY, induces an INNER JOIN that multiplies taxon rows and breaks the planner.
   Express the filter once — inside the aggregate (`accessor="occurrences"`) — and
   remove the backend, since the HAVING already enforces membership.

## Future direction — denormalised per-project observed taxa

The precompute approach scales with verified-data volume. If per-project taxa
aggregates (observed counts, verified counts, agreement) become a recurring perf
problem across endpoints, consider a dedicated **`TaxonObserved`** model holding
denormalised data per `(project, taxon)` — distinct from the generic project-agnostic
`Taxon` profile — refreshed via the cached-count pattern
(`update_cached_counts(run_async=True)`) on `Identification` / `Occurrence` writes.
That moves the rollup off the read path entirely and makes counts directly sortable /
filterable as real columns. Open idea, not yet scoped.
