# Captures list — "Processed / Not processed" filter

Date: 2026-05-28
Status: design approved, pending spec review
Scope: first of several planned captures-list filters; this PR ships the processed filter only.

## Goal

Add a "Processing status" filter to the Captures (SourceImage) list view, letting users
narrow to captures that have been processed, not processed, or all (no filter). Lay the
groundwork (a planned filter set) for additional filters in later PRs.

"Processed" = the image has been run through detection. Because PR #1093 writes a null
Detection marker for the "processed, found nothing" case, the presence of *any* Detection
row is an accurate signal of "was processed."

## Backend — no change required

The filter already exists and is exercised by the list endpoint:

- `ami/main/api/views.py:630-636` — `SourceImageViewSet.filter_by_has_detections`
  handles `?has_detections=true|false` by annotating
  `Exists(Detection.objects.filter(source_image=OuterRef("pk")))` and filtering on it.
  (`SourceImageViewSet` at `views.py:528`.)
- Called from `get_queryset` only for the `list` action (`views.py:600`), which is what
  the captures list uses.

Decision: reuse the existing `has_detections` query param. Zero backend change, already
tested behavior. The param name (`has_detections`) means "was processed" because of the
null-marker convention; we surface it to users with the label "Processing status" and keep
`has_detections` as the internal query key. This name/meaning gap is the one known wart and
is documented here rather than fixed (a `was_processed` alias was considered and rejected to
avoid extra surface area).

## Frontend — four wiring changes

1. **New component** `ui/src/components/filtering/filters/processing-status-filter.tsx`.
   Model on `verification-status-filter.tsx`. Two options: "Processed" (true) /
   "Not processed" (false). Wire `onValueChange={onAdd}` directly so both true and false
   are settable. (The generic `BooleanFilter` is unusable here: its "No" branch calls
   `onClear()` instead of filtering to false — see `boolean-filter.tsx:21-27`.)
   Use a translated label string for the two options (add to `utils/language` if needed).

2. **Register the component** in `ui/src/components/filtering/filter-control.tsx`
   `ComponentMap`: `has_detections: ProcessingStatusFilter`.

3. **Register the filter** in `ui/src/utils/useFilters.ts` `AVAILABLE_FILTERS`:
   `{ label: 'Processing status', field: 'has_detections', tooltip: { text: ... } }`.

4. **Render it** on the captures page `ui/src/pages/captures/captures.tsx` (inside the
   existing `FilterSection`, alongside `deployment` and `collections`):
   `<FilterControl field="has_detections" />`.

State, URL params, page reset, and the clear-X ("All") behavior all come from the existing
`useFilters` machinery — no changes there.

## Data flow

UI select -> `addFilter('has_detections', 'true'|'false')` -> URL search param ->
`useFilters` -> `useCaptures` builds `?has_detections=...` via `getFetchUrl`
(`ui/src/data-services/utils.ts`) -> DRF `filter_by_has_detections` -> filtered queryset.
Clear-X removes the param -> "All".

## Testing

- Backend: verify existing coverage for `?has_detections=true|false` on the captures list
  endpoint; add a test if missing (both branches + absent param).
- Frontend: manual verification against the running stack — select Processed, Not processed,
  and clear; confirm result counts change and the URL param round-trips.

## Out of scope (planned follow-up PRs)

To live in a collapsible "Advanced" `FilterSection` on the captures page later:

- **Date range** — `date_start`/`date_end` already in the FE registry with a `DateFilter`
  component, but the SourceImage viewset needs backend support mapping them to a `timestamp`
  range (new work).
- **Station** — already available via the existing `deployment` filter.
- **Site** — add `deployment__research_site` to `filterset_fields` + a Site filter component.
- **Device** — add `deployment__device` to `filterset_fields` + a Device filter component.
