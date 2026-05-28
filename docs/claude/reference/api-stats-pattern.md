# API stats endpoints — `/<entity>/stats/<kind>/`

How to add an aggregate / leaderboard / chart endpoint that doesn't fit
the standard CRUD shape of an entity ViewSet.

## TL;DR

- URL: `/api/v2/<entity>/stats/<kind>/?project_id=X[&...]`
- Backed by `viewsets.GenericViewSet` (action-based, no implicit CRUD),
  namespaced under the entity the stats are computed *over*.
- One `@action(detail=False, methods=["get"], url_path="<kind>")` per
  stats kind.
- Response declared via a kind-specific `Serializer` + `@extend_schema(responses=...)`
  so drf-spectacular autodocs the shape.
- Default response shape is a **scalar dict** owned by the kind. The
  generic DRF paginator envelope is a fallback we'll opt into per-action
  when a kind genuinely needs `?limit / ?offset / ?ordering` rails — see
  `docs/claude/planning/stats-list-pattern.md` for the deferred design.
- Project gated via `ProjectMixin` (`require_project = True`) +
  `Project.objects.visible_for_user(request.user)` for draft visibility.
- Pure querysets live in `ami/main/models_future/<entity>.py`, view-free.

Reference implementation: `OccurrenceStatsViewSet` at
`ami/main/api/views.py`. The pure query lives in
`ami/main/models_future/occurrence.py::top_identifiers_for_project()`.

## The scalar pattern

```python
class TopIdentifiersResponseSerializer(serializers.Serializer):
    project_id = serializers.IntegerField()
    top_identifiers = UserIdentificationCountSerializer(many=True)


class OccurrenceStatsViewSet(viewsets.GenericViewSet, ProjectMixin):
    permission_classes = [IsActiveStaffOrReadOnly]
    require_project = True

    @extend_schema(
        parameters=[project_id_doc_param, limit_doc_param],
        responses=TopIdentifiersResponseSerializer,
    )
    @action(detail=False, methods=["get"], url_path="top-identifiers")
    def top_identifiers(self, request):
        project = self.get_active_project()
        assert project is not None  # require_project=True guarantees this
        if not Project.objects.visible_for_user(request.user).filter(pk=project.pk).exists():
            raise NotFound("Project not found.")

        limit = SingleParamSerializer[int].clean(
            param_name="limit",
            field=serializers.IntegerField(required=False, min_value=1, max_value=50, default=5),
            data=request.query_params,
        )
        top_users = list(top_identifiers_for_project(project)[:limit])
        return Response(
            TopIdentifiersResponseSerializer(
                {"project_id": project.pk, "top_identifiers": top_users},
                context={"request": request},
            ).data
        )
```

The kind owns its envelope. A summary stat returns `{total: 42}`. A
leaderboard returns `{project_id, top_identifiers: [...]}`. A timeline
returns `{series: [{date, count}, ...]}`. There's no shared meta layer —
each kind's serializer is the contract.

## Why scalar by default

Most stats are small fixed-shape blobs the frontend renders into a
specific widget. Reaching for the paginator envelope before knowing the
consumer's needs gets you `count: 5, next: null, previous: null, results: [...]`
for a five-row leaderboard that the UI was always going to show in
full — three fields of noise to thread through every consumer.

When a kind genuinely needs paginated rails (e.g. a deployment
leaderboard with hundreds of entries that the UI wants to sort and
page through), see `docs/claude/planning/stats-list-pattern.md` for the
opt-in design.

## Don't leak entity lists

For kinds that rank entities by activity (top identifiers, top species,
top deployments), the underlying queryset MUST exclude entities with
zero activity — non-configurable, baked into the `models_future` function.

Otherwise an anonymous client can call the stats endpoint without any
data in the project and get back the full project user list (or full
taxon list, etc). With `identification_count >= 1` baked in, the
endpoint returns an empty list instead.

```python
def top_identifiers_for_project(project: Project) -> QuerySet[User]:
    return (
        User.objects.filter(identifications__occurrence__project=project)
        .annotate(identification_count=Count(..., distinct=True))
        .filter(identification_count__gt=0)  # <-- non-configurable
        .order_by("-identification_count")
    )
```

The `?limit=N` param decides *how many* rows to return. The query
function decides *which rows are eligible* — and zero-count rows
never are.

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

Guard with a regression test — see
`TestOccurrenceStatsViewSet.test_registration_order_preserves_occurrence_retrieve`.

## Why `stats`, not `metrics`

"Metrics" carries observability connotations (Prometheus, StatsD,
infra). "Stats" reads as product-domain aggregates — what a user sees
on a dashboard. Reserve `metrics` for ops/infra; use `stats` for
user-facing aggregations.

## Query parameters

Use `SingleParamSerializer[T].clean(...)` from `ami/base/serializers.py`.
It runs a DRF `serializers.IntegerField` / etc. through the standard
validation pipeline and raises `ValidationError` → DRF returns 400 with
the field-level error body the frontend expects.

```python
limit = SingleParamSerializer[int].clean(
    param_name="limit",
    field=serializers.IntegerField(required=False, min_value=1, max_value=50, default=5),
    data=request.query_params,
)
```

Do **not** clamp silently — bad input should fail loud at the boundary.
Precedent: `ami/jobs/views.py:321` (cutoff_hours), `ami/jobs/views.py:250`
(logs_limit).

## `get_active_project()` discipline

`ProjectMixin` with `require_project = True` enforces project
**presence** through `self.get_active_project()` — missing `project_id`
raises 400, an id pointing at a nonexistent project raises 404. It does
NOT gate **draft visibility** — drafts must be filtered explicitly:

```python
project = self.get_active_project()
assert project is not None
if not Project.objects.visible_for_user(request.user).filter(pk=project.pk).exists():
    raise NotFound("Project not found.")
```

Two lines, inline at the top of each action. Don't extract a helper
until a viewset has 3+ actions sharing the gate — at that point a
private method is justified, but with one or two actions it's just
indirection.

## Permissions

```python
permission_classes = [IsActiveStaffOrReadOnly]
```

`IsActiveStaffOrReadOnly` allows anon reads. The inline `visible_for_user`
check above is what filters draft projects for non-members.

## Backend layer split

- `ami/main/models_future/<entity>.py` — pure querysets / aggregation
  functions, no view dependencies. Reusable from jobs, exports, scripts.
  Security-baked filters (e.g. `identification_count >= 1`) live here.
- `ami/main/api/views.py` — viewset wires HTTP concerns (params,
  permissions, serialization, visibility gate) to the query function.

## Frontend hook location

Mirror the backend URL hierarchy:

```
ui/src/data-services/hooks/<entity>/stats/<kind>.ts
```

e.g. `ui/src/data-services/hooks/occurrences/stats/useTopIdentifiers.ts`.

The hook's `Response` interface matches the kind-specific serializer.

## Response field schema via OPTIONS

Stats endpoints set `metadata_class = ResponseSchemaMetadata` (from
`ami/base/metadata.py`) on the viewset and pass `serializer_class=` to
each `@action(...)` decorator. The default DRF `SimpleMetadata` only
emits serializer fields for write methods (POST / PUT) — without this
override the response shape and its `help_text=` annotations are
invisible to clients on read-only endpoints.

With it wired, `OPTIONS /<entity>/stats/<kind>/` returns the response
serializer's field schema under `actions.GET`:

```json
{
  "name": "Model agreement",
  "description": "Verified / human↔model agreement rates...",
  "actions": {
    "GET": {
      "verified_pct": {
        "type": "float",
        "label": "Verified pct",
        "help_text": "verified_count / total_occurrences",
        "min_value": 0.0,
        "max_value": 1.0
      },
      ...
    }
  }
}
```

Frontends fetch OPTIONS once at component mount and key tooltips /
labels by field name, so stat copy lives next to the serializer
definition rather than being hardcoded in the UI. Interpretation copy
("wide CI means shaky number") stays in the FE bundle next to the
visualization — `help_text` describes *what the number is*, not *how
to read it as a human*.

Each `@action` must pass `serializer_class=` so `view.get_serializer()`
returns the right response shape during OPTIONS resolution. Multiple
actions on one viewset can carry different serializers this way.

## Tests required (in the same commit)

For every new stats action:

- happy path — returns the expected shape with correct values
- missing `project_id` → 400 (via `require_project`)
- invalid query param (e.g. out-of-range `limit`) → 400
- draft project, anonymous user → 404 (visibility gate)
- correctness invariant specific to the kind (e.g. distinct-vs-raw
  count, zero-count entities excluded)

Plus, for the viewset overall (once):

- registration order — both the stats URL and the entity retrieve URL
  resolve, in case someone reorders router registrations later

See `TestOccurrenceStatsViewSet` in `ami/main/tests.py` (6 tests).

## What this convention replaces

The earlier `/users/identifications/top/` pattern: an explicit `path()`
registration on a `GenericAPIView` sitting outside the DRF router. It
worked, but it bypassed router autodoc, polluted the `/users/` namespace,
and gave no place to put a sibling stats action.

The new pattern is a router-registered `GenericViewSet` with one
`@action` per kind, autodoc'd through drf-spectacular, namespaced under
the entity the stats are computed *over*.

## Future stats actions

Naming examples that fit the convention (all scalar by default — opt
into pagination only if the kind genuinely needs it):

- `GET /occurrences/stats/top-identifiers/` — done (this PR)
- `GET /occurrences/stats/identifications-summary/` — total / distinct / verified counts
- `GET /occurrences/stats/model-agreement/` — model agreement rate
- `GET /occurrences/stats/identifications-by-species/` — per-taxon ID counts
- `GET /occurrences/stats/timeline/` — Plotly-shaped time series
- `GET /deployments/stats/processed-images/` — processed images per station
- `GET /deployments/stats/by-status/` — capture counts per processing state
- `GET /taxa/stats/most-observed/` — top species by occurrence count
- `GET /jobs/stats/by-status/` — counts per JobState

When adding a new entity's stats viewset, copy the docstring from
`OccurrenceStatsViewSet` verbatim — it's the contract.
