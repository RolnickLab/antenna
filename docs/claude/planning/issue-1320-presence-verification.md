# Issue #1320 — Presence verification workflow from the taxa view

Implementation plan. Branch: `worktree-taxa-verification-flow` (fresh off main, has migrations 0093/0094).
Scope decided with the user: **full BE + FE in one branch**, example thumbnail **opens the occurrence
identification modal over the taxa list**, bundle **link Last-seen & Best-score cells** + **gate the
`?collection=` example behind an opt-in param**. "Verify next" deferred to a follow-up.

## Goal

Add an **Example** column to the taxa list (`GET /api/v2/taxa/`, page `/projects/<id>/taxa`). Each row
shows one occurrence thumbnail; clicking it opens the existing occurrence identification modal (Agree /
Suggest ID) over the taxa list so a user can sweep unverified taxa and confirm presence one row at a time.

## Occurrence selection semantics (document on the field + column tooltip)

Hybrid, computed per taxon row:

- **Unverified row** (`verified_count == 0`) → **best-scoring unverified** occurrence (fastest clean ID).
- **Verified row** (`verified_count >= 1`) → **latest** occurrence (is it still showing up?).

Two extra ids for the optional cell links (exact-determination, mirroring the existing value columns):

- `best_scoring_occurrence_id` — highest `determination_score` occurrence (any status). Powers the
  Best-score cell link. Mirrors `best_determination_score`.
- `last_detected_occurrence_id` — most recent occurrence by detection timestamp (any status). Powers the
  Last-seen cell link. Mirrors `last_detected`.

All three are **exact-determination** (`determination_id = taxon`), matching how `occurrences_count` /
`best_determination_score` / `last_detected` are computed on the default path — NOT rolled up to
ancestors (that only applies to `verified_count`). Document this asymmetry.

## API contract (frozen — BE and FE build against this)

New query param on the taxa list: `with_example_occurrences=true|false` (default **false**), parsed with
`SingleParamSerializer` → 400 on bad input. Controls whether the three occurrence-id annotations run:

- **Default path** (no `?collection=`): cheap correlated subqueries, index-served. Computed when the flag
  is true.
- **`?collection=` path**: correlated subqueries degrade to per-row scans, so they run **only** when the
  flag is true (the gate). The FE sends the flag when the Example column is visible.

New list-row response fields (present only when `with_example_occurrences=true`, else omitted/null):

```jsonc
"example_occurrence": {          // null when the taxon has no qualifying occurrence
  "id": 123,
  "detection_id": 456,           // best detection of that occurrence, may be null
  "image_url": "https://…",      // best-detection crop, may be null
  "score": 0.97,                 // occurrence determination_score, may be null
  "verified": false              // is THIS occurrence verified (non-withdrawn Identification)
},
"best_scoring_occurrence_id": 123,   // int | null
"last_detected_occurrence_id": 789   // int | null
```

## Backend design

### 1. `TaxonQuerySet.with_example_occurrence_ids(...)` — new method (`ami/main/models.py`)

Dispatch-independent, mirrors `with_verification_counts`. Called after it in `get_taxa_observed`, reusing
the shared `direct_filters` and the verified-taxon-id set.

Signature:
```python
def with_example_occurrence_ids(self, project, request, *, occurrence_filters,
                                verified_taxon_ids: set[int],
                                apply_default_score_filter=True, apply_default_taxa_filter=True):
```
Builds `default_q = build_occurrence_default_filters_q(project, request, occurrence_accessor="", ...)` and
`base_filter = Q(occurrence_filters, determination_id=OuterRef("id")) & default_q` (same as
`with_observation_counts_subqueries`).

Three correlated subqueries (all `.values("id")[:1]`, deterministic `-id` tiebreak):
- `best_scoring = Occurrence.objects.filter(base_filter).order_by("-determination_score", "-id").values("id")[:1]`
- `last_detected = Occurrence.objects.filter(base_filter, detections__timestamp__isnull=False).order_by("-detections__timestamp", "-id").values("id")[:1]`
- `best_unverified = Occurrence.objects.filter(base_filter).filter(~Exists(Identification.objects.filter(occurrence=OuterRef("pk"), withdrawn=False))).order_by("-determination_score", "-id").values("id")[:1]`

Annotate:
```python
qs = self.annotate(
    best_scoring_occurrence_id=Subquery(best_scoring, output_field=IntegerField()),
    last_detected_occurrence_id=Subquery(last_detected, output_field=IntegerField()),
    example_occurrence_id=Case(
        When(id__in=list(verified_taxon_ids), then=Subquery(last_detected, output_field=IntegerField())),
        default=Subquery(best_unverified, output_field=IntegerField()),
        output_field=IntegerField(),
    ),
)
```
Note the two `OuterRef`s: `OuterRef("id")` = outer Taxon, `OuterRef("pk")` inside the `Exists` = inner
Occurrence. Django resolves them; spell them distinctly.

`verified_taxon_ids` is sparse (bounded by human review) so `id__in=list(...)` is a small IN — fine in the
`When`.

### 2. Refactor so the verified-taxon set is computed once (`with_verification_counts`)

`get_taxa_observed` needs `verified_taxon_ids` for the example Case, and `with_verification_counts`
already computes `verified_counts.keys()`. Avoid double-running the verified-occurrence query. Extract a
small `_verified_taxon_counts(project, request, occurrence_filters, ...) -> dict[int,int]` helper (the
current Python-pass body of `with_verification_counts`), and have both the count method and
`get_taxa_observed` use it. `get_taxa_observed` passes `set(counts)` into `with_example_occurrence_ids`.

### 3. `get_taxa_observed` wiring (`ami/main/api/views.py`)

- Parse `with_example_occurrences` (default false) via `SingleParamSerializer[bool]` (returns 400 on junk).
- Compute `verified_counts` once (helper), pass to `with_verification_counts` (so it doesn't recompute).
- On the **default** path: if the flag is true, call `with_example_occurrence_ids(...)`.
- On the **`?collection=`** path: if the flag is true, call the SAME `with_example_occurrence_ids(...)`
  (correlated subqueries; accepts the per-row scan cost — this is the gated tradeoff). Membership is
  already handled by HAVING, so the extra annotations just add subquery columns.
- When the flag is false: annotate the three ids as `Value(None)` so the serializer/`.values()` shape is
  stable, OR skip and let the serializer treat missing attrs as null. Prefer explicit `Value(None,
  IntegerField())` on both branches for a stable shape.

### 4. Hydrate `example_occurrence` in the viewset `list()` (batch, no N+1)

The SQL picks ids; hydrate them into the nested object in one extra query per page:
- Override `list()` (or use `get_serializer_context`): after the page queryset is realized, collect the
  page's `example_occurrence_id`s (~10), run one
  `Occurrence.objects.filter(id__in=ids).with_best_detection().annotate(is_verified=Exists(Identification…
  withdrawn=False), best_detection_id=Subquery(Detection…order_by("-classifications__score","id").values("id")[:1]))`
  build `{occ_id: {...}}`, pass via serializer context.
- `image_url` = `ami.utils.storages.get_media_url(best_detection_path)` (confirm helper name/location;
  `Detection.url` uses it). `score` = `determination_score`.

### 5. Serializer (`TaxonListSerializer`, `ami/main/api/serializers.py`)

Add to `Meta.fields`: `example_occurrence`, `best_scoring_occurrence_id`, `last_detected_occurrence_id`.
- `best_scoring_occurrence_id` / `last_detected_occurrence_id`: plain `IntegerField(read_only=True,
  allow_null=True)` bound to the annotations.
- `example_occurrence`: `SerializerMethodField` reading the hydration map from context by
  `obj.example_occurrence_id`; returns `None` if absent.

### 6. Perf / correctness gates before merge

- `python manage.py makemigrations --check --dry-run` — **no migration expected** (query-only change).
- `EXPLAIN ANALYZE` the `best_unverified` subquery (with `~Exists(Identification)`) — **measured** on a
  production-scale dev project (~180k occurrences), for the heaviest taxon (~8,800 occurrences):
  index-served via `Bitmap Index Scan on occur_det_proj_evt` (`determination_id, project_id, event_id`),
  then a top-N heapsort on `determination_score`; the `NOT EXISTS` is a hash anti-join over
  `main_identification`. **Execution ~27ms** for the worst-case single taxon. (The planner picked the
  3-col index + heapsort rather than `occur_det_proj_evt_score`; still index-served and fast.) Remaining
  gate: full end-to-end list cold-page bench with the flag on — rough estimate a few hundred ms for a
  25-taxon page on the default path, not yet measured.
- Bench the taxa list cold page under the same project as #1317: default `?with_example_occurrences=true`
  under ~2s; `?collection=…&with_example_occurrences=true` documented (gated, may be slower).
- FLUSHALL redis / `cachalot_disabled()` when timing (cachalot caches repeat runs).

## Backend tests (`ami/main/tests.py`, near `TestTaxaVerification`)

- `example_occurrence` populated on default / event / deployment / collection / verified paths (with flag).
- Flag **off** → fields null/absent (default budget protection).
- Unverified row returns a best-scoring **unverified** occurrence; verified row returns the latest.
- `?verified=false&deployment=X` → example satisfies both filters.
- No inflation under `?collection=` (detection fan-out) — the chosen id is a real single occurrence.
- `assertNumQueries` with a **multi-row** fixture — bounded query count (hydration is one extra query,
  not per-row).
- `?with_example_occurrences=abc` → 400.

## Frontend design (`ui/`)

Target page: the species/taxa list (`Species`, route `taxa/:id?`, `ui/src/pages/species/species.tsx`).

1. **Open the occurrence modal over the taxa list.** `taxa/:id` already means *taxon* detail, so key the
   occurrence modal off a separate search param, e.g. `?verifyOccurrence=<occId>`. Render the list, then
   `{verifyOccurrenceId ? <OccurrenceDetailsDialog id={verifyOccurrenceId} .../> : null}` (reuse the
   dialog from `ui/src/pages/occurrences/occurrences.tsx`; extract it if not exported). Close → drop the
   param. Always `keepSearchParams: true`.
2. **Example column** (`ui/src/pages/species/species-columns.tsx`): new `TableColumn<Species>` id
   `'example'`, **no `sortField`** (non-sortable), renders `ImageTableCell` from
   `item.exampleOccurrence?.imageUrl`, `to` = route adding `?verifyOccurrence=<id>`. Null-guard → empty
   images array. Tooltip "Verify one occurrence of this taxon." Add `'example'` to the column-visibility
   default map in `species.tsx`.
3. **Model** (`ui/src/data-services/models/species.ts`): add `exampleOccurrence` getter
   ({id, detectionId, imageUrl, score, verified}), `bestScoringOccurrenceId`, `lastDetectedOccurrenceId`.
   `ServerSpecies` is `any` — verify the live payload.
4. **Link Last-seen & Best-score cells** to `?verifyOccurrence=<id>` when the id is present.
5. **De-emphasis of verified rows**: dim rows where `numVerified > 0` + a "verified ✓" marker. Table has
   no row-className hook — add a small optional `rowClassName?: (item) => string` prop to the nova-ui-kit
   `Table` (backward-compatible) OR do it per-cell. Prefer the row hook if clean.
6. **Cache invalidation after verify**: the identification mutation invalidates `[IDENTIFICATIONS]` +
   `[OCCURRENCES]` but not the taxa list. Add `API_ROUTES.SPECIES` to the invalidation in
   `useCreateIdentification` / `useCreateIdentifications` so `verified_count` + the example thumbnail
   refresh.
7. **Empty state**: when `?verified=false` yields zero rows, "All taxa verified under this filter."
8. All copy via `translate(STRING.KEY)`; new `STRING.EXAMPLE`. Follow `ui/AGENTS.md`.

## FE checks

- `cd ui && yarn lint && yarn build` (or `tsc --noEmit`).
- Live browser check on a local project if the stack is up (Node 18 worktree recipe).

## Post-review fixes (adversarial review of the backend diff)

- **COUNT amplification (fixed).** `TagInverseFilter` always applies `.distinct()` (needed to dedupe the
  `occurrences__deployment/event/project` filterset joins), which pulls select-only annotations into the
  pagination COUNT subquery — so the example subqueries would run for every taxon in the project, not
  just the page. Fixed with `TaxonPagination.get_count`, mirroring `ProjectPagination`: count via
  `queryset.order_by().values("pk")` so annotations are stripped. Regression test
  `test_example_subqueries_stripped_from_pagination_count` asserts `main_identification` never appears in
  the COUNT SQL.
- **Test strengthening (fixed).** The dispatch tests now use a fixture that decouples score from recency
  (verifying an occurrence overrides its `determination_score`, so a verified taxon is marked via a
  separate occurrence); added the query-count differential (limit=5 vs 25), a real `?collection=`
  fan-out (second detection), the higher-rank NULL-example case, and a two-deployment scoping test.

## Out of scope (per issue): bulk verify, dedicated queue page, project-summary widget, per-user credit,
time-bucketed matrix, "Verify next" (deferred).
