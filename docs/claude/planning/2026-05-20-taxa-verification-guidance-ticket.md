# Add guidance and stats about which taxa need verification

## Motivation

To get a meaningful project-wide picture of model accuracy and data quality, users should verify at least one occurrence of every unique taxon their pipelines have apparently observed. Today there is no surface that tells them *which* taxa still need attention or how many they have already verified — they have to drill into the occurrence list per taxon and check by hand.

This ticket adds per-taxon verification and agreement data to the existing taxa list endpoint, plus the matching UI controls, so users can sort and filter to find the taxa that most need their attention. It is part of this year's proactive-surfacing goal and is the natural next step after [#1296](https://github.com/RolnickLab/antenna/pull/1296) (project summary) and [#1307](https://github.com/RolnickLab/antenna/pull/1307) (dataset-wide model agreement endpoint).

## Scope

Backend annotations on `GET /api/v2/taxa/` plus a new filter, and a new column + filter in the taxa list table. The dataset-wide `/occurrences/stats/model-agreement/` endpoint from #1307 is unchanged — it stays as the aggregate view; this ticket adds the per-taxon breakdown.

### Out of scope (queued separately)

- "Needs verification" badge / status pill on rows.
- Project-summary widget with `X of Y unique taxa verified`.
- Dedicated unverified-taxa queue page.
- Backfilling counts onto a denormalized `Taxon` field.
- Macro-average rollup (occurrence-weighted descendant sum is the only rollup in this ticket).

## Backend

### Filter

- `verified=true|false` on `TaxonViewSet` — matches taxa with at least one non-withdrawn `Identification` on an occurrence whose `determination` is the taxon itself **or any descendant** (via `parents_json__contains`). Implemented as an `EXISTS` subquery, project-scoped, respects `apply_default_filters`.

### Always-on annotations (cheap)

Both reuse the existing hierarchical-match pattern (`parents_json__contains [{id: OuterRef("id")}] OR determination_id = OuterRef("id")`) used by the `taxon=<id>` filter in the occurrence list, so a Family row aggregates all its descendant species' occurrences — occurrence-weighted by construction.

- `verified_count` — count of occurrences under the taxon (incl. descendants) with at least one non-withdrawn `Identification`. Sortable. Single correlated subquery per row.
- `agreed_with_prediction_count` — count of verified occurrences whose chosen `Identification.agreed_with_prediction` is non-null. No join through `Classification` needed — just a non-null FK check. Different signal from `agreed_exact_count` below: this measures the *agree-with-model workflow* (user clicked the "agree" button on a prediction), not independent-match accuracy.

### Gated annotation (heavier)

- `agreed_exact_count` — count of verified occurrences where `occurrence.determination_id` equals the top machine `Classification.taxon_id` for the same occurrence. Surfaced only when `with_agreement=true` is on the request. Cost: two correlated subqueries per row (verified set + best classification per occurrence). Needs benchmarking on P#85 (13k verified) before this can default on. **NOT** included in the default list response.

`occurrence.determination` is already maintained as the top non-withdrawn user identification's taxon (`update_occurrence_determination` runs on every `Identification.save`, see `ami/main/models.py:2528, 3383-3393`), so we do not need a correlated subquery over `Identification` to find the best human identification — just read `determination_id` directly. This is what makes `agreed_exact_count` only two subqueries instead of three.

### Dropped vs PR #1307

- `agreed_under_order_count` is not added per-taxon. The under-order LCA bucket from `/occurrences/stats/model-agreement/` stays available at the dataset level; per-taxon it's redundant since each row already represents a single taxon.

### Detail view

`GET /api/v2/taxa/<id>/` should include all four fields above unconditionally — single-row cost is negligible.

### Performance prerequisites

- The hierarchical match uses `Taxon.parents_json` containment. Without a GIN index on that column, Family- and Order-rank rows on large projects (P#85 has 13k verified, P#20 has 41k occurrences) will fall back to seq-scan and dominate query time. **This index is already flagged as a follow-up to #1307**:

  ```sql
  CREATE INDEX CONCURRENTLY main_taxon_parents_json_gin_idx
    ON main_taxon USING gin (parents_json jsonb_path_ops);
  ```

  Treat shipping the GIN index as a hard blocker for enabling recursive rollup correctness at higher ranks. Without it, this ticket is safe to ship for projects with shallow taxa lists (species-only) but will be slow elsewhere.

- The composite-index follow-up from #1307 (`main_occurrence (project_id, determination_score)`) is also relevant — `verified_count` filters by project + verified flag and benefits from the same indexed path.

### Cost benchmarks to run before merge

| Query | Project | Expected | Acceptance |
|---|---|---|---|
| `/taxa/?project_id=18&verified=true` | P#18 (45 verified) | < 200ms warm | ≤ 1.5× current `/taxa/` p99 |
| `/taxa/?project_id=85&verified=false` | P#85 (13k verified) | < 500ms warm | ≤ 2× current p99 |
| `/taxa/?project_id=85&with_agreement=true` | P#85 | < 1.5s warm | < 5s cold |
| `/taxa/?project_id=85&ordering=verified_count` | P#85 | < 1s warm | doesn't fall off cliff |

If `with_agreement=true` exceeds the cold budget on P#85, fall back to keeping `agreed_exact_count` on the detail view only and add a `/taxa/stats/verification/` aggregate endpoint mirroring the #1307 pattern instead.

## Frontend

### Taxa list page (`/projects/<id>/taxa`)

- New sortable column **Verified** showing `verified_count` per row. Default ordering unchanged; user can click the column to sort asc (least-verified first → matches the proactive-surfacing intent).
- New filter pill **Verification status**: `All` (default) / `Verified` / `Unverified`. Wires to the `verified=` query param.
- Existing `Occurrences` column stays as the primary count signal; `Verified` sits next to it so the ratio is visually obvious.

### Not in this ticket

- No new column for `agreed_with_prediction_count` or `agreed_exact_count` in the table by default. These are surfaced on the **taxon detail page** only (existing detail page; add a small "Verification" panel showing the four numbers). If the table eventually grows a "Model accuracy" toggle, it would flip `with_agreement=true` on — design that in a follow-up.

## API contract examples

```bash
# Verified taxa only, project default filters applied
curl '.../api/v2/taxa/?project_id=18&verified=true'

# Unverified taxa, sorted by occurrence count desc — the "biggest gaps" view
curl '.../api/v2/taxa/?project_id=18&verified=false&ordering=-occurrences_count'

# Sort by which taxa have the most human verification
curl '.../api/v2/taxa/?project_id=18&ordering=-verified_count'

# Enable the heavier agreed_exact_count on a list response
curl '.../api/v2/taxa/?project_id=18&with_agreement=true'

# Detail view always includes all four
curl '.../api/v2/taxa/567/?project_id=18'
```

### Response shape (list)

```json
{
  "id": 567,
  "name": "Hyalophora cecropia",
  "rank": "SPECIES",
  "occurrences_count": 124,
  "verified_count": 3,
  "agreed_with_prediction_count": 2,
  "best_determination_score": 0.94,
  "last_detected": "2025-08-12T03:14:22"
}
```

With `with_agreement=true`:

```json
{
  "...": "...",
  "verified_count": 3,
  "agreed_with_prediction_count": 2,
  "agreed_exact_count": 2
}
```

## Test plan

Backend:

- [ ] Unit test on `Taxon` queryset: `verified=true` returns only taxa with non-withdrawn identifications, respecting hierarchical match (verifying a species also marks its genus/family as verified at higher-rank rows).
- [ ] Unit test on `Taxon` queryset: `verified=false` is the strict complement on the project's filtered taxa set.
- [ ] Unit test: `verified_count` equals number of verified occurrences under the taxon (descendants included).
- [ ] Unit test: `agreed_with_prediction_count` only counts the chosen identification's `agreed_with_prediction`, not all identifications on the occurrence.
- [ ] Unit test: `agreed_exact_count` reads `occurrence.determination_id` for the user side and top-score `Classification.taxon_id` for the model side, and is only populated when `with_agreement=true`.
- [ ] HTTP test: list endpoint shape includes new fields; gated field absent unless flag is set.
- [ ] HTTP test: `verified=` filter behaves correctly under `apply_defaults=true|false`.
- [ ] Bench: queries above hit acceptance thresholds.

Frontend:

- [ ] Verified column renders, sorts asc and desc.
- [ ] Filter pill updates URL, persists across reload, clears with the rest of the project filter state.
- [ ] Detail page Verification panel renders all four fields.

## Follow-ups (not in this ticket)

- `Taxon.parents_json` GIN index (carries over from #1307 — gating dependency for rollup correctness at higher ranks).
- `main_occurrence (project_id, determination_score)` composite index (also from #1307).
- Project-summary "X of Y unique taxa verified" widget on the overview page.
- "Needs verification" status pill on taxa rows once we know what the threshold should be (`verified_count == 0` is the obvious v1).
- Dedicated unverified-taxa queue view (pre-filtered, ranked by occurrence count desc).
- Macro-averaged agreement rollup at higher ranks (alternative to the occurrence-weighted sum this ticket ships).
- A `with_counts` / `with_agreement` query-param convention audit across the API — we already have similar gated-annotation patterns elsewhere; document a single convention.

## References

- PR #1307 — dataset-wide `/occurrences/stats/model-agreement/` endpoint, established the LCA + agreement-bucket compute that this ticket reuses per-taxon. Includes the GIN-index and composite-index follow-ups this ticket inherits.
- PR #1296 — project summary view, the surfacing target this work feeds into.
- `ami/main/api/views.py:1403` — `TaxonViewSet`, where the new annotations and filter land.
- `ami/main/api/views.py:1576` — `get_taxa_observed`, the existing helper that already wires `parents_json`-aware subqueries; pattern for adding the new ones.
- `ami/main/models.py:2440` — `Identification` model (`agreed_with_prediction` FK).
- `ami/main/models.py:3383` — `update_occurrence_determination`, which keeps `Occurrence.determination` aligned with the top non-withdrawn user identification.
