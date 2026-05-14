# Filter-driven occurrence exports — scoping stub

**Status:** scoping only. No API design, no task breakdown, no migrations.
**Goal:** let a user on `/occurrences/` apply filters in the UI, click "Export",
and get a job whose output matches exactly that filtered set — without first
having to materialize a `SourceImageCollection`.

## 1. Current export architecture

- Entry point: `ami/exports/views.py:30-87` `ExportViewSet.create()` — validates
  format + filters, optionally looks up a `SourceImageCollection` from
  `filters["collection_id"]`, creates `DataExport`, wires it to a `Job`, calls
  `job.enqueue()`.
- Persistence: `ami/exports/models.py:23-35` — `DataExport` stores
  `format`, `filters` (JSONB), `project`, `user`, `file_url`.
- Worker side: `ami/exports/base.py:17-28` — `BaseExporter.__init__` calls
  `apply_filters(queryset, filters, filter_backends)` using
  `get_filter_backends()` which today returns just
  `[OccurrenceCollectionFilter]` (`base.py:42-45`).
- Filter replay: `ami/exports/utils.py:13-72` — `generate_fake_request()`
  builds a DRF `Request` from a path + query-param dict, then
  `apply_filters()` runs the backends against the synthetic request.
- Format-specific querysets: `ami/exports/format_types.py:46-63` (JSON) and
  `212-234` (CSV) — both call `Occurrence.objects.valid().filter(project=...)`
  and layer custom queryset annotations on top.

So the export infra **already** has a "filters JSON → re-run backends in
worker" pattern. The catch: it's hard-wired to `OccurrenceCollectionFilter`
and never sees the rest of the `/occurrences/` filter stack.

## 2. `/occurrences/` list filter stack

`ami/main/api/views.py:1171-1209` registers:

- `DefaultViewSetMixin.filter_backends` (DjangoFilter, ordering, search)
- `CustomOccurrenceDeterminationFilter` (`views.py:968-987`) — taxon + descendants
- `OccurrenceCollectionFilter` (`views.py:988-1006`)
- `OccurrenceAlgorithmFilter` (`views.py:1008-1030`)
- `OccurrenceDateFilter` (`views.py:1084-1102`)
- `OccurrenceVerified` (`views.py:1032-1049`)
- `OccurrenceVerifiedByMeFilter` (`views.py:1051-1066`) — **reads `request.user`**
- `OccurrenceTaxaListFilter` (`views.py:1105-1152`)

Plus `filterset_fields = ["event", "deployment", "determination__rank",
"detections__source_image"]` (DjangoFilter), and the project-level default
filter chain via `qs.apply_default_filters(project, self.request)`
(`views.py:1232`) which layers score thresholds + include/exclude taxa
from `ami/main/models_future/filters.py`.

## 3. The gap

What an async export needs that a raw filter dict doesn't supply on its own:

- **Pickleability.** Celery serializes args; the snapshot must be plain JSON
  (already true for `DataExport.filters`).
- **User identity for user-scoped filters.** `verified_by_me` and
  `apply_default_filters` both read `request.user` — `generate_fake_request`
  currently builds an anonymous request, so these silently no-op or behave
  differently than the user expected.
- **Drift between submit and run.** If a project's default-filter config,
  taxa lists, or score thresholds change between job enqueue and worker
  execution, the export may not match what the user previewed.
- **Pagination semantics don't transfer.** The user filtered to 12k rows; we
  need to export all 12k, not a single page. Trivial today (no `limit`/
  `offset` in the JSON) but worth stating.
- **Ordering preservation.** `ordering=` may or may not matter for an export
  consumer; needs a call.
- **Large result streaming.** Already partially handled by
  `get_data_in_batches` (`utils.py:75-105`), but only after the filtered
  queryset materializes — needs verification at the scale users will hit.

## 4. Proposed approaches

**A. Persist filter params as JSON, re-run pipeline in the worker.** Extend
`BaseExporter.get_filter_backends()` to return the full `/occurrences/` stack
and feed the JSON through `apply_filters()` as today. Also stash `user_id`
on `DataExport` (already present) and stitch it into the synthetic request
so user-scoped filters work. Lowest infra change; highest drift risk
(re-resolves against live project config at run time).

**B. Materialize a transient `SourceImageCollection` from the filtered set.**
At submit time, resolve the filter to a list of `SourceImage` ids, create a
hidden collection, point the existing export job at it. Reuses every
existing code path. Heaviest write at submit (could be slow for 100k+ rows);
collection-as-snapshot semantics are misleading because collections are
SourceImage-rooted, not Occurrence-rooted.

**C. New `ExportFilter` model snapshotting params + resolved querystring +
user + project-default-filter version.** Adds explicit provenance ("this
export reflects filters X under project config version Y"). Most fidelity,
most surface area; only worth it if (A) drift bites in practice.

Rough ordering by effort: **A < B < C**. Rough ordering by drift safety:
**C > B > A**.

## 5. Open questions

- How should `apply_default_filters` be re-evaluated at worker time vs.
  frozen at submit? (Today's behaviour is implicitly "re-evaluate.")
- For `verified_by_me`, do we trust `DataExport.user` as the identity, or
  require the submit-time `request.user` to match?
- Should `ordering` be preserved, or is unordered export acceptable?
- What's the realistic upper bound on exported occurrences, and does
  `get_data_in_batches` hold up there?
- Does the UI need a preview count before the job is enqueued? (Today
  `update_record_count()` runs synchronously in the view — fine for small
  filtered sets, awkward for huge ones.)
- Should the export job snapshot the project's default-filter config so
  re-runs are reproducible?

## 6. Out of scope for this doc

- Concrete API design (request/response shapes, field names).
- Task breakdown / sequencing.
- Schema migrations.
- UI changes on `/occurrences/`.
