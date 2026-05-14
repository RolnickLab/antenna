# API stats endpoints — `/<entity>/stats/<kind>/`

How to add an aggregate / leaderboard / chart endpoint that doesn't fit
the standard CRUD shape of an entity ViewSet.

## TL;DR

- URL: `/api/v2/<entity>/stats/<kind>/?project_id=X[&...]`
- Backed by `viewsets.GenericViewSet` (so paginator + filter backends
  are available per-action), namespaced under the entity the stats are
  computed *over* (not necessarily the entity returned).
- One `@action(detail=False, methods=["get"], url_path="<kind>")` per stats kind.
- Two response shapes coexist on the same viewset depending on the kind —
  see "Two patterns" below.
- Response always declared via `@extend_schema(responses=...)` on a DRF
  serializer so drf-spectacular autodocs it.
- Project gated via `ProjectMixin` (`require_project = True`) +
  `Project.objects.visible_for_user(request.user)` for draft visibility.
- Pure querysets live in `ami/main/models_future/<entity>.py`, view-free.

Reference implementation: `OccurrenceStatsViewSet` at
`ami/main/api/views.py` (after `OccurrenceViewSet`). The pure query for
the list kind lives in
`ami/main/models_future/occurrence.py::top_identifiers_for_project()`.

## Two patterns — pick by response shape

### Pattern 1 — list-shaped kinds (paginator)

Rows of entities with annotations. Build a queryset, ride the standard
list-endpoint rails — paginate + filter + order — return DRF's
`{count, next, previous, results: [...]}` envelope.

```python
@extend_schema(
    parameters=[project_id_doc_param],
    responses=UserIdentificationCountSerializer(many=True),
)
@action(detail=False, methods=["get"], url_path="top-identifiers")
def top_identifiers(self, request):
    project = self._gate_project(request)
    queryset = top_identifiers_for_project(project)
    queryset = self.filter_queryset(queryset)
    page = self.paginate_queryset(queryset)
    serializer = UserIdentificationCountSerializer(page, many=True, context={"request": request})
    return self.get_paginated_response(serializer.data)
```

Free with this pattern:

- `?limit=N&offset=M` (from `pagination_class`)
- `?ordering=-field` (from `NullsLastOrderingFilter` + `ordering_fields`)
- Any additional filter backends declared on the viewset
- Spectacular autodocs the paginated envelope + the row serializer

Examples: `top-identifiers`, future `most-observed`, `by-algorithm`.

### Pattern 2 — scalar / chart-shaped kinds

Single dict, scalar value, time series, Plotly-nested chart data — none
of which fit the row-list shape. Build the structure, serialize with a
kind-specific Serializer, return `Response(serializer.data)`.

```python
class IdentificationsSummarySerializer(serializers.Serializer):
    total_identifications = serializers.IntegerField()
    distinct_identifiers = serializers.IntegerField()
    distinct_identified_occurrences = serializers.IntegerField()


@extend_schema(
    parameters=[project_id_doc_param],
    responses=IdentificationsSummarySerializer,
)
@action(detail=False, methods=["get"], url_path="identifications-summary")
def identifications_summary(self, request):
    project = self._gate_project(request)
    ids = Identification.objects.filter(occurrence__project=project, withdrawn=False)
    data = {
        "total_identifications": ids.count(),
        "distinct_identifiers": ids.values("user_id").exclude(user__isnull=True).distinct().count(),
        "distinct_identified_occurrences": ids.values("occurrence_id").distinct().count(),
    }
    return Response(IdentificationsSummarySerializer(data).data)
```

No paginator — the response is one object. No `filter_queryset` —
scalars don't filter. Query params (if any) validated via
`SingleParamSerializer[T].clean(...)`.

Examples: `identifications-summary`, future `human-model-agreement`,
`identifications-by-species`, `timeline` (Plotly).

## Why both on one viewset

The two patterns share enough — URL namespace, project gating, draft
visibility, permission classes, OpenAPI registration — that splitting
them across separate viewsets adds boilerplate without adding clarity.
A `GenericViewSet` base lets each action opt into the paginator
machinery when it makes sense and ignore it when it doesn't.

## Registration order matters

In `config/api_router.py`:

```python
router.register(r"occurrences/stats", views.OccurrenceStatsViewSet, basename="occurrence-stats")
router.register(r"occurrences", views.OccurrenceViewSet)  # AFTER stats
```

DRF's `DefaultRouter` walks routes in registration order.
`OccurrenceViewSet`'s detail route is `^occurrences/(?P<pk>[^/.]+)/$` —
register it first and `/occurrences/stats/` matches with `pk="stats"`,
then 404s on `Occurrence.objects.get(pk="stats")`. The stats URL never
reaches its ViewSet.

Guard with a regression test that hits both `/occurrences/stats/<kind>/`
and `/occurrences/<real-pk>/` and asserts both return 200 — see
`TestOccurrenceStatsViewSet.test_registration_order_preserves_occurrence_retrieve`.

## Why `stats`, not `metrics`

"Metrics" carries observability connotations (Prometheus, StatsD,
infra). "Stats" reads as product-domain aggregates — what a user sees
on a dashboard. Reserve `metrics` for ops/infra; use `stats` for
user-facing aggregations.

## Don't leak entity lists from list-kinds

For list-shaped kinds that rank/filter entities by activity (top
identifiers, top species, top deployments), the underlying queryset
MUST exclude entities with zero activity — non-configurable, baked
into the `models_future` function.

Otherwise an anonymous client can call the stats endpoint without any
data in the project and get back the full project user list (or full
taxon list, etc). With `identification_count >= 1` baked in, the
endpoint returns `count: 0, results: []` instead.

```python
def top_identifiers_for_project(project: Project) -> QuerySet[User]:
    return (
        User.objects.filter(identifications__occurrence__project=project)
        .annotate(identification_count=Count(..., distinct=True))
        .filter(identification_count__gt=0)  # <-- non-configurable
        .order_by("-identification_count")
    )
```

The paginator / `?limit=N` still decides *how many* rows to return.
The query function decides *which rows are eligible* — and zero-count
rows never are.

## Query parameters beyond paginator / ordering

Use `SingleParamSerializer[T].clean(...)` from `ami/base/serializers.py`.
It runs a DRF `serializers.IntegerField`/etc. through the standard
validation pipeline and raises `ValidationError` → DRF returns 400
with the field-level error body the frontend expects.

```python
threshold = SingleParamSerializer[float].clean(
    param_name="score_threshold",
    field=serializers.FloatField(required=False, min_value=0, max_value=1, default=0.5),
    data=request.query_params,
)
```

Do **not** clamp silently — bad input should fail loud at the boundary.
Precedent: `ami/jobs/views.py:321` (cutoff_hours), `ami/jobs/views.py:250`
(logs_limit).

The paginator's `limit` / `offset` and the ordering filter's `ordering`
are special — DRF validates those itself (paginator clamps to
`max_limit`, ordering ignores unknown fields). Don't duplicate that
validation in the action.

## `get_active_project()` discipline

`ProjectMixin` with `require_project = True` enforces project presence
**only through `self.get_active_project()`**. The mixin does not
intercept the request automatically — if an action skips that call,
`require_project` does nothing.

Every action on a stats ViewSet MUST call `self.get_active_project()`
on its first line, before any other logic. The shared `_gate_project()`
helper on `OccurrenceStatsViewSet` bundles the call with the
visibility check — copy that pattern.

## Permissions

```python
permission_classes = [IsActiveStaffOrReadOnly]
```

`IsActiveStaffOrReadOnly` allows anon reads. The `_gate_project()`
helper then runs `Project.objects.visible_for_user()` to filter out
draft projects for non-members — anonymous users hitting a draft
project's stats get 404, not a leaked leaderboard.

## Backend layer split

- `ami/main/models_future/<entity>.py` — pure querysets and aggregation
  functions, no view layer dependencies. Reusable by anything else
  that needs the same data shape (jobs, exports, internal scripts).
  This is also where the "don't leak entity lists" filter lives.
- `ami/main/api/views.py` — viewset wires HTTP concerns (params,
  permissions, serialization, response shape) to the query function.

## Frontend hook location

Mirror the backend URL hierarchy:

```
ui/src/data-services/hooks/<entity>/stats/<kind>.ts
```

e.g. `ui/src/data-services/hooks/occurrences/stats/useTopIdentifiers.ts`.

For list-kinds the hook returns the DRF paginated envelope — interface
is `{count, next, previous, results: ...[]}`. The consumer reads
`data?.results`. For scalar-kinds the hook's `Response` interface
matches the kind-specific Serializer.

## Tests required (in the same commit)

For every new stats action:

- happy path — returns expected rows / scalar values
- query params (limit, ordering, anything kind-specific) — apply as expected
- missing `project_id` → 400 (via `require_project`)
- draft project, anonymous user → 404 (visibility gate)
- correctness invariant specific to the kind (e.g. distinct-vs-raw count,
  score-threshold respected, zero-count entities excluded)

For list-kinds, also:

- default pagination (no `?limit=`) returns `default_limit` rows
- `?ordering=-field` overrides the default order

For the viewset overall:

- registration order — both the stats URL and the entity retrieve URL
  resolve, in case someone reorders router registrations later

See `TestOccurrenceStatsViewSet` in `ami/main/tests.py` (12 tests
covering both patterns + shared regression).

## What this convention replaces

The earlier `/users/identifications/top/` pattern: an explicit
`path()` registration on a `GenericAPIView` sitting outside the DRF
router. It worked, but it bypassed router autodoc, polluted the
`/users/` namespace, used a hand-rolled envelope instead of the
standard paginator, and gave no place to put a sibling stats action.

The new pattern is a router-registered `GenericViewSet` with one
`@action` per kind, autodoc'd through drf-spectacular, namespaced
under the entity the stats are computed *over*.

## Future stats actions

Naming examples that fit the convention:

**List-shaped (pattern 1):**

- `GET /occurrences/stats/top-identifiers/` — done (this PR)
- `GET /occurrences/stats/by-algorithm/` — counts per detection algorithm
- `GET /occurrences/stats/identifications-by-species/` — per-taxon identification counts
- `GET /deployments/stats/processed-images/` — processed images per station, paginated
- `GET /taxa/stats/most-observed/` — top species by occurrence count
- `GET /jobs/stats/by-status/` — counts per JobState (if returned as rows)

**Scalar / chart-shaped (pattern 2):**

- `GET /occurrences/stats/identifications-summary/` — done (this PR, placeholder example)
- `GET /occurrences/stats/human-model-agreement/` — model agreement / verification rate
- `GET /occurrences/stats/timeline/` — Plotly-shaped time series for the occurrences page
- `GET /deployments/stats/by-status/` — capture counts per processing state (as a dict)

When adding a new entity's stats viewset, copy the docstring from
`OccurrenceStatsViewSet` verbatim — it's the contract.
