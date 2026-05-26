# Next session — PR #1317 follow-ups

## Branch / deploy state (2026-05-26)

- Branch `worktree-taxa-verification-counts`, HEAD `4f456819` (docs-only on top of `cf86550d`).
- serbia (`antenna-dev-serbia`, `~/antenna`) deployed at `cf86550d`.
- Migrations applied through `0087_taxon_parents_json_gin_index` (renumbered from `0085` after merging main).
- 43 taxa tests pass (`TestTaxaVerification`, `TestTaxonomyViews`, `TestTaxonListQueryCount`, `TestProjectDefaultTaxaFilter`, `TestCachedCountsDefaultFilters`).

## Final live timings on project 5 (~1k taxa / 17k occ)

| path | ms |
|---|---|
| default `limit=25` | 2140 (was 820 pre-refactor — **regression**) |
| `verified=true` | 810 |
| `verified=false` | 1190 |
| `ordering=verified_count` | 1450 |
| `collection=5` | 1830 (was 30s+ timeout) |
| `collection=5&with_agreement=true` | 1920 |

## Why default regressed

Conditional aggregation does **one big GROUP BY** over all project occurrences (16861 rows) every request. The previous correlated `Subquery` form was **index-served per row** by the composite `(determination_id, project_id, event_id, determination_score)` index — perfect for the default path. Conditional aggregation is universally correct + scales to the collection path; correlated subqueries are faster *when no detections join is in play*.

## Tasks for next session

### 1. Hybrid: keep conditional aggregation for `?collection=`, restore correlated subqueries for everything else

In `TaxonViewSet.annotate_taxon_counts` (`ami/main/api/views.py:1683`), dispatch on whether the occurrence filter joins detections (i.e. `?collection=` is in the request — the only filter that currently induces that join):

- **No detections join** (default / event / deployment / verified / ordering): use the ORIGINAL three correlated `Subquery` annotations (occurrences_count / best_score / last_detected) — restore the block that was deleted in `838f9d75`. Membership = the materialised `id__in` from `29bec78c` (or the original EXISTS; both worked fine without the detections join).
- **Detections join in play** (`?collection=<id>`): use the conditional aggregation block that exists now (`Count("occurrences", filter=count_filter, distinct=True)` + `Max(...)` + HAVING). Already validated at 1.83s on project 5.

Pick the branch from `request.query_params` (`"collection" in self.request.query_params`) rather than introspecting the Q object — simpler and reflects the actual decision.

Targets after hybrid: default ≤ 0.9s, collection ≤ 2s. Verify both on serbia.

### 2. Move counting into `TaxonQuerySet` methods (lighten view, make reusable)

Existing custom queryset: `TaxonQuerySet` at `ami/main/models.py:3422` (already has `with_occurrence_counts(project)`, `filter_by_project_default_taxa`, `visible_for_user`). Manager at `models.py:3488`. The CLAUDE.md "Custom QuerySet Methods (Always Use These)" section already lists this as the canonical pattern.

Methods to add:

- `with_observation_counts(project, request, *, apply_default_score_filter=True, apply_default_taxa_filter=True, occurrence_filters=None)` — applies the dense aggregates (after hybrid: correlated subqueries OR conditional aggregation). Replaces the existing `with_occurrence_counts` (or replaces its body — the existing one is just `Count("occurrences", distinct=True)`, narrower scope).
- `observed_in_project(project, request, *, occurrence_filters=None)` — membership filter, returns the qs filtered to observed taxa. Mirrors the existing pattern.
- `with_verification_counts(project, request)` — the sparse CASE-from-map rollup (currently `TaxonViewSet._annotate_verification_counts`). Note this method materialises an Occurrence query and builds Python maps before annotating, but that's still appropriate to live on the queryset (it's a method, not a pure annotation).

What stays in the view:
- `get_occurrence_filters(project, accessor="")` — parses request query params for `occurrence_id` / `deployment` / `event` / `collection`, plus the per-id existence checks that raise 404. View-specific (request introspection). Pass the resulting `Q` into the queryset methods.
- `_include_agreement` (request param parsing).
- `_case_from_map` could move to the queryset module as a module-level helper since it's generic; or stay on the view. Tradeoff: queryset module if anything else might use it.

After refactor, `get_taxa_observed` shrinks to chaining queryset methods:

```python
def get_taxa_observed(self, qs, project, include_unobserved=False, apply_default_score_filter=True, apply_default_taxa_filter=True):
    occ_filters = self.get_occurrence_filters(project)
    qs = qs.with_observation_counts(project, self.request, occurrence_filters=occ_filters,
                                    apply_default_score_filter=apply_default_score_filter,
                                    apply_default_taxa_filter=apply_default_taxa_filter)
    if not include_unobserved:
        qs = qs.observed_in_project(project, self.request, occurrence_filters=occ_filters)
    return qs.with_verification_counts(project, self.request, occurrence_filters=occ_filters,
                                       include_agreement=self._include_agreement(),
                                       verified_param=self.request.query_params.get("verified"))
```

(Verified filter application — currently inside `_annotate_verification_counts` — can stay there or move to a small `.filter_verified(...)` queryset method. Either way the view loses the filter wiring.)

### 3. Gotchas to preserve (cited in `docs/claude/reference/hierarchical-rollup-query-performance.md`)

- **Dense CASE-from-map fails on large projects** — `SQLParseError: tokens exceeded 10000`. Only use the CASE-from-map pattern for *sparse* maps (verified subset). Dense aggregates need conditional aggregation OR correlated subqueries.
- **Don't include the default taxa filter in the conditional-aggregate `count_filter`** — it adds a `parents_json` containment join inside the aggregate that the planner cannot reconcile with the detections join under `?collection=`. Redundant anyway because `filter_by_project_default_taxa` keeps/drops the row at the qs level. Keep only score threshold in `count_filter`.
- **`TaxonCollectionFilter` removed** (`cf86550d`) — the backend's `queryset.filter(occurrences__detections__source_image__collections=<id>)` was redundant on top of the aggregate's collection filter and broke the planner. If reintroducing for any reason, gate it on the absence of conditional aggregation.

### 4. Other still-open items (already tracked, lower priority)

- Browser check of the FE Verified column / verified filter pill / detail panel — not done.
- The `TaxonCollectionFilter` class itself is still defined at `views.py:1207` but unused — delete or keep as cruft? Either way.
- Future scaling: dedicated `TaxonObserved` denorm model (`[[project-taxon-observed-denorm]]`) — only if the conditional-aggregation default-regression or future read-path counts keep biting.

## Key files / commits

- `ami/main/api/views.py:1540` `get_occurrence_filters(project, accessor="")`
- `ami/main/api/views.py:1683` `annotate_taxon_counts(qs, project, ...)`
- `ami/main/api/views.py:1740` `_annotate_verification_counts(qs, base)`
- `ami/main/api/views.py:1675` `_case_from_map(mapping, default, output_field)`
- `ami/main/api/views.py:1462` filter_backends (TaxonCollectionFilter removed)
- `ami/main/models.py:3422` `TaxonQuerySet` (target home for new methods)
- `docs/claude/reference/hierarchical-rollup-query-performance.md` — pattern + gotchas reference
- `ami/main/tests.py:4766` `TestTaxaVerification` — gate the hybrid against these

## Commits this session (most recent first)

- `4f456819` docs: sparse vs dense, gotchas
- `cf86550d` fix: remove redundant TaxonCollectionFilter backend (collection 182s → 1.83s)
- `f20a05d0` fix: drop redundant taxa filter from occurrences_count aggregate (broken→working but slow path still)
- `7f571be7` fix: conditional aggregation for dense per-taxon counts
- `838f9d75` refactor: centralize per-taxon counts (introduced; dense CASE form broke SQL token limit)
- `29bec78c` fix: materialize observed-taxon id set
- `b92b2b0e` fix: collection-COUNT scale (membership id__in subquery — regressed, superseded)
- `30955e33` chore: migration renumber 0085 → 0087 after main merge
- `10c72cbd` fix: dedupe occurrences in verification rollup under collection filter
