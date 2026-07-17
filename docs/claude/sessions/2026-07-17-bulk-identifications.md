# Bulk identifications endpoint (PR #1371) — session notes

**Date**: 2026-07-17
**Branch**: `feat/bulk-identifications` (worktree off `origin/main`)
**PR**: #1371 (draft) — *Let identifiers apply identifications to many occurrences in one request*
**Author**: AI agent session

Notes for whoever picks this up. Written for context recovery, not as a tutorial.

## What shipped

`POST /api/v2/identifications/bulk/` — a `detail=False` action on `IdentificationViewSet`
(`ami/main/api/views.py`, search `def bulk`). Serializers are `Bulk*` in
`ami/main/api/serializers.py`. Tests in `ami/main/test_bulk_identifications.py` (34).

Contract: `{"identifications": [{occurrence_id, taxon_id, comment?, agreed_with_identification_id?,
agreed_with_prediction_id?}]}` → `200 {created_count, error_count, results: [{index, occurrence_id,
status, id?, errors?}]}`.

## Findings that shaped the design (do not re-derive these)

### The request shape was decided by the frontend, not by preference

The mass-ID UI **already exists** and already fans out N POSTs
(`ui/src/data-services/hooks/identifications/useCreateIdentifications.ts` — `Promise.allSettled`
plus retry-only-the-rejected). Three call sites, all already building
`IdentificationFieldValues[]`:

- `ui/src/pages/occurrences/occurrences-actions.tsx` — "Agree/Confirm". **Heterogeneous**: each
  item's taxon is *that occurrence's own* determination, and each item's agree target is its own
  identification or prediction.
- `ui/src/pages/occurrence-details/suggest-id/suggest-id.tsx` — one taxon, many occurrences.
- `ui/src/pages/occurrence-details/id-quick-actions/id-button.tsx` — one taxon, many occurrences.

The Agree flow makes `{taxon_id, occurrence_ids: []}` impossible. Hence a list of per-item objects.

### Batch size is bounded by the page, not by the project

`ui/src/pages/occurrences/occurrences.tsx` filters `selectedItems` to occurrences on the currently
displayed page. So real batches are ~25–100. The ">100k occurrences" scaling worry does not reach
this endpoint today. It would if a "select all matching this filter" action ever ships.

### The task brief was wrong on two points

- **PR #1281 "Update agree logic for human identifications" is a one-line frontend fix**
  (`human-identification.tsx`, +1/−1). It is not backend agree logic.
- **`user_agrees_with_identification` (`ami/main/models.py`) has zero call sites** — dead code. It
  also carries an unbounded module-level `@functools.cache` keyed on model instances (stale results
  + per-worker growth) if anyone ever wires it up.

There is **no special backend agree handling**. `agreed_with_identification` / `agreed_with_prediction`
are plain nullable FKs stored as provenance; `save()` never branches on them.

### `update_occurrence_determination` compares an int to a Taxon (pre-existing)

`current_determination` is read via `.values("determination")`, which yields the **raw FK id**, then
compared against `top_identification.taxon`, a **model instance**. `Taxon != int` is always true, so
the guard never short-circuits, the "no update needed" branch is effectively unreachable, and every
identification rewrites `determination` and `determination_score`.

**Verified empirically**, not inferred: a single POST agreeing with an existing determination moves
`determination_score` from 0.9 to 1.0.

Consequence: agreeing *does* set the score to 1.0. That may be desirable, but it is reached by
accident. `determination_score` feeds project score-threshold filters
(`ami/main/models_future/filters.py`), so changing it changes which occurrences appear in filtered
lists. **Do not "fix" it as a drive-by.** The bulk endpoint deliberately reproduces today's behaviour.

## Two bugs caught in review that are invisible in a diff

### `ATOMIC_REQUESTS` defeats naive per-item transactions

`config/settings/base.py:59` sets `ATOMIC_REQUESTS = True`. The whole request is therefore already
one transaction, and a per-item `transaction.atomic()` is a **savepoint**, not an independent commit.
Wrapping each item is not enough to get partial success: an exception escaping `save()` aborts the
request transaction and discards every item already written, returning a 500.

The fix is to **catch** the failure so the savepoint rolls back that item alone and the loop
continues. Pinned by `test_a_database_failure_on_one_item_is_reported_without_losing_the_others`,
which was confirmed to fail without the fix.

### The action name silently becomes a permission nobody has

A `detail=False` action is never routed through `has_object_permission`, and
`ObjectPermission.has_permission` returns `True` unconditionally (`ami/base/permissions.py`), so the
action must check permission itself. If it passes `view.action` (`"bulk"`) to `check_permission`, that
misses the CRUD map in `BaseModel.check_permission` (`ami/base/models.py`) and falls through to
`check_custom_permission` → `has_perm("bulk_identification", project)` — a permission no role grants.
Superusers still pass via guardian's shortcut, so **a happy-path test written as a superuser would
never catch it**. The action maps explicitly to `"create"`.

Related: `Identification.check_permission`'s `"create"` branch depends only on the occurrence's
project, which is why the batch is authorized once per project. A note now lives at
`Identification.check_permission` (the line a future editor touches), not only at the endpoint.

## Verification

- 34 tests green (`ami.main.test_bulk_identifications`), full `ami.main` suite green.
- **Live HTTP check against a real runserver** — the suite runs under `APITestCase`, which wraps each
  test in a transaction, so `ATOMIC_REQUESTS` degrades to a savepoint there and real commit behaviour
  is never exercised. The live check confirmed a mixed batch returns 200 with 2 created + 1 error, the
  survivors **commit** (re-read from a separate process), the prior identification is withdrawn, and
  403/400 paths behave. Scripts were kept out of the repo (throwaway).

### Gotcha: the CI stack's *dev* database is polluted

`docker compose -f docker-compose.ci.yml` → the `ami` database has a `main_project.license` NOT NULL
column that **exists in no migration on `main`**, left behind by another branch. `migrate` reports
"no migrations to apply" because the other branch's migration row is recorded. Seeding real data there
fails with `null value in column "license"`.

Workaround used: create a throwaway database, migrate it, run, drop it. Build the URL from
`POSTGRES_*` env vars **inside** the container so no credential ever appears in a command.

### Gotcha: two concurrent `--keepdb` runs corrupt each other

Running two test commands against the CI stack at once produces spurious failures — they share the
`test_ami` database. Also hit the known cachalot issue: `--keepdb` plus permission migrations →
`IntegrityError on auth_group_permissions`. Fix is to drop the test DB **and** `redis-cli FLUSHALL`
together (see `reference_ci_compose_cachalot_flush`).

## Frontend switch (in this PR)

The pressure relief only lands when the FE stops fanning out N POSTs. `useCreateIdentifications.ts` now
makes one POST to `/bulk/`; the singular `useCreateIdentification.ts` (still used by the per-occurrence
Agree card in `agree.tsx`) is untouched. The plural hook keeps its return shape
(`isLoading`/`isSuccess`/`error`/`createIdentifications`), so the three callers (`occurrences-actions.tsx`,
`suggest-id.tsx`, `id-button.tsx`) are unchanged. Two behaviours preserved on purpose: retry resends
only the rejected items, and a partial failure is not reported as success (drives the Agree
"Confirmed" state). "Select all" is page-bounded (`occurrence-gallery.tsx:173` maps the current page's
`items`; default page size 20), so batches stay well under `MAX_BULK_IDENTIFICATIONS = 200`.

FE verified: `tsc --noEmit`, eslint, prettier, and `yarn build` all clean. BE string-ID contract
(`"123"` coerced by DRF IntegerField) pinned by `test_accepts_ids_sent_as_strings`.

## Follow-ups

- **Batched write path** — planned; the request contract does not change. See the planning doc.
- **`update_occurrence_determination` int-vs-Taxon comparison** — needs a decision, then tests, before
  anyone touches determination logic.
- **`user_agrees_with_identification`** — delete or fix the `functools.cache`.
- **Single-item endpoint asymmetries** — it accepts a writable `withdrawn` and unvalidated
  `agreed_with_*` targets. The bulk endpoint rejects both.
