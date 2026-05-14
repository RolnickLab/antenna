# Next session — PR #1307 rework

**Branch:** `feat/human-model-agreement-endpoint` (worktree `occurrence-stats`)
**PR:** https://github.com/RolnickLab/antenna/pull/1307
**Main stack override:** `/home/michael/Projects/AMI/antenna/docker-compose.override.yml` mounts this worktree's `ami/` + `config/` over the main `antenna` stack — `docker compose ps` already shows django/celeryworker recreated. Stack live; smoke against `http://localhost:8000/api/v2/occurrences/stats/human-model-agreement/?project_id=18` returns 200.

## Tasks for this session

### 1. Rename: drop "human"

User wants `human-model-agreement` → `model-agreement`, `HumanModelAgreement*` → `ModelAgreement*`, `human_model_agreement_for_project` → `model_agreement_for_project`. Files to touch:

- `ami/main/models_future/occurrence.py:160` — fn name + docstring
- `ami/main/api/serializers.py` — `HumanModelAgreementSerializer` class
- `ami/main/api/views.py:35-38` — import; line 94 import; viewset action name + url_path; serializer references at the action site
- `ami/main/tests.py` — `TestHumanModelAgreementForProject` class; `agreement_url`; all imports
- `ui/src/data-services/hooks/occurrences/stats/useHumanModelAgreement.ts` — rename file to `useModelAgreement.ts`; rename hook + `Response` interface to `ModelAgreementResponse` (Copilot review caught the DOM `Response` shadow)
- `docs/claude/planning/2026-05-14-human-model-agreement-endpoint.md` — leave the old plan doc as historical record; cite the new endpoint name where relevant
- PR title + body

### 2. Push aggregation into SQL (Copilot + CodeRabbit both flagged)

**Evidence:** Vermont (project 18) has 43,149 occurrences; `?apply_defaults=false` curl hit 159s and timed out at the curl layer. Current Python iteration over the full filtered queryset doesn't scale.

**Proposed approach** (validate before coding):

1. Annotate the queryset with subqueries to expose `best_machine_taxon_id` (already there via `with_best_machine_prediction()`) and `best_user_taxon_id` (new — subquery over `Identification` ordered by `BEST_IDENTIFICATION_ORDER`).
2. Compute totals with `aggregate()` using `Count('pk', filter=Q(...), distinct=True)`:
   - `total_occurrences = Count('pk')`
   - `verified_count = Count('pk', filter=Q(best_user_taxon_id__isnull=False))` (drop the verified-without-prediction trap from Copilot finding #3 — see fix below)
   - `agreed_exact_count = Count('pk', filter=Q(best_user_taxon_id=F('best_machine_taxon_id')))`
3. For `agreed_under_order_count` — the hard part — try one of:
   - **(a)** Annotate `best_user_taxon_order_id` and `best_machine_taxon_order_id` via Postgres `jsonb_path_query_first(parents_json, '$[*] ? (@.rank == "ORDER").id')` raw expressions. Two taxa agree under-order iff their order ids match AND neither is null. Add a row-level Python check only if the user's own rank is at-or-below ORDER (since user might ID at FAMILY directly with no ORDER ancestor in parents_json — but the taxon's own rank should be checked too).
   - **(b)** Denormalize: add `order_taxon_id` column on Taxon, populate in `update_parents()`. Cleaner queries, needs migration + backfill.
   - **(c)** Hybrid: keep Python LCA but batch via single annotated `values_list('pk', 'best_user_taxon_id', 'best_machine_taxon_id')` query plus one batched `Taxon` lookup. Avoids the `list(qs)` materialization but still does Python LCA. Faster than current; not as clean as (a) or (b).
4. Bench against project 18 unfiltered AND with `apply_defaults=false` before merging. Target: subsecond.

Read Copilot's comment at `ami/main/models_future/occurrence.py:227` and CodeRabbit's at `:187` for their exact wording.

### 3. Fix correctness bugs flagged in review

**3a. `TaxonRank.UNKNOWN` bug** (Copilot, `:227`)
`UNKNOWN` is defined AFTER `SPECIES` in `ami/utils/schemas.py`, so `TaxonRank.UNKNOWN >= TaxonRank.ORDER` is `True` by definition order. If either chain contains an `UNKNOWN` ancestor that happens to be the deepest shared one, LCA wrongly counts as under-order. Filter `UNKNOWN` out of `lca_rank_between`'s candidate ranks. Add a unit test.

**3b. Denominator bug** (Copilot, `:240`)
`agreed_exact_pct` / `agreed_under_order_pct` divide by `verified` but `verified` includes occurrences with **no** machine prediction — those can never agree, so they drag the pct down. Two options:
- Change the denominator to `verified AND has_machine_prediction` and call the field `verified_with_prediction_count` (clearer semantics).
- Keep `verified` as the denominator but add a separate `no_prediction_count` so the consumer can adjust.

User probably prefers option 1 + surface the `no_prediction_count` as a sibling field. Check with them before coding.

**3c. Drop wasted `select_related("taxon")` on idents prefetch** (Copilot, `:182`) — only `taxon_id` is read; the related Taxon row is re-fetched in the batch.

**3d. `verified_by_me` anon access** (Copilot, `ami/main/api/views.py:1303`)
`OccurrenceVerifiedByMeFilter` is now wired into `OccurrenceStatsViewSet` via the shared `OCCURRENCE_FILTER_BACKENDS` tuple. With `IsActiveStaffOrReadOnly` allowing anon reads, an anon `?verified_by_me=true` reads `request.user` (AnonymousUser) — the filter currently guards on `is_authenticated` so it short-circuits, but consider gating the action explicitly or filtering the backend list for anon. Decide before merging.

### 4. Test gaps to fill

**4a. Under-order-but-not-exact HTTP coverage** (Copilot, `tests.py:4969`)
`test_agreement_happy_path` only hits the exact-match shortcut. Add a test that wires a sister-species identification (matches the T2 aggregation test's "bucket 1") and asserts `agreed_exact_count=0, agreed_under_order_count=1`.

**4b. `UNKNOWN` rank regression test** — covered above in 3a.

**4c. `no_prediction_count` test** — if you add that field per 3b, test it.

### 5. Markdown lint nit (CodeRabbit, plan doc:43)

Add `text` lang specifier to the fenced "File Structure" block.

## After the rework

1. Run full sweep: `docker compose -f docker-compose.ci.yml run --rm django python manage.py test ami.main.tests.TestOccurrenceStatsViewSet ami.main.tests.TestModelAgreementForProject ami.main.tests.TestLcaRankBetween ami.main.tests.TestOccurrenceListQueryCount -v 1 --keepdb`
2. Bench against project 18 — log curl `time_total` for the unfiltered + `apply_defaults=false` cases. Memory budget: should not materialize 43k rows.
3. Reply to each Copilot/CodeRabbit thread with `**Claude says:** Fixed in <sha>...` per CLAUDE.md PR comment workflow.
4. Resolve threads via GraphQL once replied.
5. Push, let CI run, then ping user.

## Files to grep first

- Existing SQL-side patterns: `OccurrenceQuerySet.with_best_machine_prediction()` at `ami/main/models.py:2998`, `with_verification_info()` at `:3022`, `unique_taxa()` at `:3051`. These all use `Subquery(...)` annotations — same pattern to follow.
- `parents_json` jsonb queries: `Taxon.objects.filter(parents_json__contains=[{"id": ...}])` at `ami/main/models.py:3661, 3776, 3787` — that's the standard ORM idiom. For `jsonb_path_query_first` you'll need `RawSQL` or a custom `Func` subclass.
- Override file (already mounted): `/home/michael/Projects/AMI/antenna/docker-compose.override.yml` — leave as-is.

## Compaction note

Current session committed 5 PR commits + the plan doc + side-research export stub at `docs/claude/planning/occurrence-filter-driven-exports.md`. PR #1307 open with CodeRabbit + Copilot reviews already on it. Memory file `MEMORY.md` should be updated to add a `project_pr_1307_human_model_agreement.md` entry summarizing state (TODO this session start).
