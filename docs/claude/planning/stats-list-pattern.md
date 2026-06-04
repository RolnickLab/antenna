# Stats endpoints — list / paginator pattern (deferred)

Companion to `docs/claude/reference/api-stats-pattern.md`.

The reference doc establishes the scalar pattern as the default for
`/<entity>/stats/<kind>/` endpoints. This doc captures the
list-paginator pattern that was prototyped and removed before PR #1296
merged, ready to revive when a stats kind genuinely needs it.

## When to opt in

Use the scalar pattern unless the kind has both:

1. **Many rows** the UI wants to page through (hundreds-to-thousands —
   not a five-row leaderboard), AND
2. **`?ordering=` flexibility the UI actually exercises** (sort by
   different annotated fields, ascending vs descending).

If neither holds, the scalar `{project_id, top_identifiers: [...]}`
envelope with a single `?limit=N` slice is enough. Don't pay for the
paginator's `{count, next, previous, results}` overhead just because
the response happens to be a list.

Indicators you've crossed the line:

- A `?limit=N` query param with `N` in the hundreds.
- The UI's "view all" page wants `?offset=` paging.
- The UI lets the user re-sort the column (counts, names, dates).

## What the opt-in looks like

Add `StatsPagination` + filter backends + `ordering_fields` at the
viewset level, then the action returns the paginator envelope:

```python
class StatsPagination(LimitOffsetPagination):
    default_limit = 5
    max_limit = 50


class OccurrenceStatsViewSet(viewsets.GenericViewSet, ProjectMixin):
    queryset = User.objects.none()  # hint for LimitOffsetPaginationWithPermissions._get_current_model
    permission_classes = [IsActiveStaffOrReadOnly]
    pagination_class = StatsPagination
    filter_backends = [NullsLastOrderingFilter]
    ordering_fields = ["identification_count"]
    require_project = True

    @extend_schema(
        parameters=[project_id_doc_param],
        responses=UserIdentificationCountSerializer(many=True),
    )
    @action(detail=False, methods=["get"], url_path="top-identifiers")
    def top_identifiers(self, request):
        project = self.get_active_project()
        assert project is not None
        if not Project.objects.visible_for_user(request.user).filter(pk=project.pk).exists():
            raise NotFound("Project not found.")

        queryset = top_identifiers_for_project(project)
        queryset = self.filter_queryset(queryset)
        page = self.paginate_queryset(queryset)
        serializer = UserIdentificationCountSerializer(page, many=True, context={"request": request})
        return self.get_paginated_response(serializer.data)
```

Response envelope: `{count, next, previous, results: [...]}` instead
of the scalar `{project_id, top_identifiers: [...]}`. The frontend
hook switches to reading `data?.results`.

## Coexistence with scalar kinds

The viewset can host both. A single action picks its shape: paginate +
`get_paginated_response` for list-kinds, or build a dict + serialize +
`Response(serializer.data)` for scalar-kinds. The viewset's
`pagination_class` and `filter_backends` are shared infrastructure, not
applied automatically — they only kick in for actions that call
`self.paginate_queryset()` / `self.filter_queryset()`.

If a stats viewset ends up with both shapes, docstring should call out
which actions opt into the paginator and why.

## Why this was deferred from PR #1296

The PR established the URL convention with one concrete action
(`top_identifiers`). Initial implementation used the paginator envelope
to demonstrate the "list" pattern. Review feedback:

- The leaderboard is intentionally short (default 5, never more than 50)
  — three extra `{count, next, previous}` fields per response add no value.
- Showing both patterns up front lent weight to a list-default
  assumption that doesn't reflect how stats kinds actually shake out
  (most are small fixed-shape blobs).
- A speculative second action (`identifications_summary`) was added
  just to demonstrate the scalar shape — but the leaderboard itself
  already wanted scalar, so the placeholder was scaffolding for a
  pattern we hadn't validated.

Reverting to scalar-only for the merged PR removed the placeholder
action and dropped the paginator/filter machinery, then captured the
opt-in design here so the next stats endpoint can adopt it without
re-deriving anything.

## Tests to add when adopting

On top of the standard stats-endpoint test set (happy path, missing
project_id, invalid params, draft 404, registration order):

- default pagination (no `?limit=`) returns `default_limit` rows
- `?limit=N` caps `results` length, `count` still reflects the total
- `?offset=N` skips into the queryset
- `?ordering=-field` flips the sort
- `?ordering=field` (ascending) matches default-but-reversed
- unknown ordering fields silently ignored (DRF default; we're not
  custom-validating)

## Open questions for when this gets picked up

- Does the `LimitOffsetPaginationWithPermissions` machinery want a
  `_get_current_model` hint via `queryset = X.objects.none()` here?
  PR #1296's prototype set `queryset = User.objects.none()` because
  the rows were Users; verify the pagination permissions layer
  actually reads this.
- Should `max_limit` differ between leaderboard-style kinds (capped
  at ~50) and timeline-style kinds (more flexible)? Probably define
  per-action `pagination_class` rather than per-viewset if so.
- `NullsLastOrderingFilter` only — do we want the full
  `DefaultViewSetMixin.filter_backends` (`DjangoFilterBackend` +
  `SearchFilter`)? Stats kinds probably don't want free-text search;
  keep it narrow.
