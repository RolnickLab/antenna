# API stats endpoints — `/<entity>/stats/<kind>/`

How to add an aggregate / leaderboard / chart endpoint that doesn't fit
the standard CRUD shape of an entity ViewSet.

## TL;DR

- URL: `/api/v2/<entity>/stats/<kind>/?project_id=X[&limit=N&...]`
- Backed by a `viewsets.ViewSet` (not `GenericViewSet` — actions are
  independent aggregations, no shared queryset)
- One `@action(detail=False, methods=["get"], url_path="<kind>")` per stats kind
- Response shape declared via a DRF serializer + `@extend_schema(responses=...)` —
  never raw `Response({...})`
- Query params validated with `SingleParamSerializer[T].clean(...)` — strict
  400 on invalid, no silent clamping
- Project gated via `ProjectMixin` with `require_project = True`, then
  `Project.objects.visible_for_user(request.user)` for draft visibility

Reference implementation: `OccurrenceStatsViewSet.top_identifiers` at
`ami/main/api/views.py` (after `OccurrenceViewSet`). The pure query lives
in `ami/main/models_future/occurrence.py::top_identifiers_for_project()`.

## Why a separate ViewSet, not actions on the entity ViewSet

`OccurrenceViewSet` is a `ModelViewSet` — list, retrieve, create, etc.
share a single queryset, filters, pagination, serializer. Stats actions
don't fit:

- Each stats action queries a different *model* (`User` for
  top-identifiers, `Taxon` for top-species, an aggregation row for
  detection-counts). They share no queryset.
- The response shape varies per kind (envelope, scalar dict, Plotly
  nested) so the single `serializer_class` slot is wrong.
- Pagination and filter backends from the entity ViewSet don't apply.

A bare `viewsets.ViewSet` (no model, no queryset, no serializer_class)
gets routed by DRF the same way and stays out of the entity ViewSet's
plumbing.

## Registration order matters

In `config/api_router.py`:

```python
router.register(r"occurrences/stats", views.OccurrenceStatsViewSet, basename="occurrence-stats")
router.register(r"occurrences", views.OccurrenceViewSet)  # AFTER stats
```

DRF's `DefaultRouter` walks routes in registration order. `OccurrenceViewSet`'s
detail route is `^occurrences/(?P<pk>[^/.]+)/$` — register it first and
`/occurrences/stats/` matches with `pk="stats"`, then 404s on
`Occurrence.objects.get(pk="stats")`. The stats URL never reaches its
ViewSet.

Guard with a regression test that hits both `/occurrences/stats/<kind>/`
and `/occurrences/<real-pk>/` and asserts both return 200 — see
`TestOccurrenceStatsTopIdentifiers.test_registration_order_preserves_occurrence_retrieve`.

## Why `stats`, not `metrics`

"Metrics" carries observability connotations (Prometheus, StatsD,
infra). "Stats" reads as product-domain aggregates — what a user sees
on a dashboard. Reserve `metrics` for ops/infra; use `stats` for
user-facing aggregations.

## Response shapes are per-kind, declared on a serializer

There is no universal envelope. Pick the shape that fits the kind and
declare it on a serializer so drf-spectacular autodocs it.

```python
class TopIdentifiersResponseSerializer(serializers.Serializer):
    project_id = serializers.IntegerField()
    top_identifiers = UserIdentificationCountSerializer(many=True)
```

Then on the action:

```python
@extend_schema(
    parameters=[project_id_doc_param, limit_doc_param],
    responses=TopIdentifiersResponseSerializer,
)
@action(detail=False, methods=["get"], url_path="top-identifiers")
def top_identifiers(self, request):
    ...
    return Response({"project_id": project.id, "top_identifiers": user_serializer.data})
```

A scalar stats kind would declare its own shape:

```python
class DetectionCountsResponseSerializer(serializers.Serializer):
    by_algorithm = serializers.DictField(child=serializers.IntegerField())
```

A Plotly chart kind would declare nested `data: [...]` matching the
Plotly JSON contract.

**Pydantic is not used here.** DRF serializers integrate with
drf-spectacular natively; adding Pydantic for response shapes would
introduce a parallel type system for no benefit. Pydantic stays for
data that's actually stored as JSONB on a model field (e.g.
`JobProgress` on `Job`).

## Query parameters

Use `SingleParamSerializer[T].clean(...)` from `ami/base/serializers.py`.
It runs a DRF `serializers.IntegerField`/etc. through the standard
validation pipeline and raises a `ValidationError` → DRF returns 400
with the field-level error body the frontend expects.

```python
limit = SingleParamSerializer[int].clean(
    param_name="limit",
    field=serializers.IntegerField(required=False, min_value=1, max_value=50, default=5),
    data=request.query_params,
)
```

Do **not** clamp silently (`max(1, min(limit, 50))`) — that hides
caller bugs. A bad limit should fail loud at the boundary, like every
other param-validation error in the codebase. Precedent:
`ami/jobs/views.py:321` (cutoff_hours), `ami/jobs/views.py:250`
(logs_limit).

## `get_active_project()` discipline

`ProjectMixin` with `require_project = True` enforces project presence
**only through `self.get_active_project()`**. The mixin does not
intercept the request automatically — if an action skips that call,
`require_project` does nothing.

Every action on a stats ViewSet MUST call `self.get_active_project()`
on its first line, before any other logic. The reminder lives in the
viewset docstring so future actions inherit it.

## Permissions

```python
permission_classes = [IsActiveStaffOrReadOnly]
```

Then in the action body:

```python
project = self.get_active_project()
assert project is not None  # require_project=True guarantees this
if not Project.objects.visible_for_user(request.user).filter(pk=project.pk).exists():
    raise NotFound("Project not found.")
```

`IsActiveStaffOrReadOnly` allows anon reads. `visible_for_user` then
filters out draft projects for non-members — anonymous users hitting a
draft project's stats get 404, not a leaked leaderboard.

## Backend layer split

- `ami/main/models_future/<entity>.py` — pure querysets and aggregation
  functions, no view layer dependencies. Reusable by anything else
  that needs the same data shape (jobs, exports, internal scripts).
- `ami/main/api/views.py` — viewset wires HTTP concerns (params,
  permissions, serialization, response shape) to the query function.

```python
# models_future/occurrence.py
def top_identifiers_for_project(project: Project, limit: int = 5) -> QuerySet[User]:
    return User.objects.filter(...).annotate(...).order_by(...)[:limit]
```

## Frontend hook location

Mirror the backend URL hierarchy:

```
ui/src/data-services/hooks/<entity>/stats/<kind>.ts
```

e.g. `ui/src/data-services/hooks/occurrences/stats/useTopIdentifiers.ts`.

The hook is a thin `useAuthorizedQuery` wrapper — no shape mapping
unless the backend envelope changes. Use the response envelope
declared in the backend serializer directly as the TypeScript
`Response` interface.

## Tests required (in the same commit)

Every new stats action gets at minimum:

1. happy path — returns ranked / aggregated data correctly
2. limit / similar query param — applies as expected
3. limit below min → 400
4. limit above max → 400
5. missing project_id → 400 (via `require_project`)
6. draft project, anon user → 404 (visibility gate)
7. correctness invariant specific to the kind (e.g. distinct-vs-raw
   count, score-threshold respected)
8. registration order — both the stats URL and the entity retrieve
   URL resolve, in case someone reorders router registrations later

See `TestOccurrenceStatsTopIdentifiers` in `ami/main/tests.py`.

## What this convention replaces

The earlier `/users/identifications/top/` pattern: an explicit
`path()` registration on a `GenericAPIView` sitting outside the
DRF router. It worked, but it bypassed router autodoc, polluted the
`/users/` namespace, and gave no place to put a sibling stats action.

The new pattern is a router-registered ViewSet with one action per
kind, autodoc'd through drf-spectacular, namespaced under the entity
the stats are computed *over* (not the entity returned in the response).

## Future stats actions

Naming examples that fit the convention:

- `GET /occurrences/stats/top-identifiers/` — done (this PR)
- `GET /occurrences/stats/by-algorithm/` — counts per detection algorithm
- `GET /occurrences/stats/identifications-by-species/` — per-taxon identification counts
- `GET /occurrences/stats/human-model-agreement/` — model agreement / verification rate
- `GET /occurrences/stats/timeline/` — Plotly-shaped time series for the occurrences page
- `GET /deployments/stats/processed-images/` — processed images per station
- `GET /deployments/stats/by-status/` — capture counts per processing state
- `GET /taxa/stats/most-observed/` — top species by occurrence count
- `GET /jobs/stats/by-status/` — counts per JobState

When adding a new entity's stats viewset, copy the docstring from
`OccurrenceStatsViewSet` verbatim — it's the contract.
