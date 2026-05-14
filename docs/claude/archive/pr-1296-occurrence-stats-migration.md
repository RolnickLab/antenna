# PR #1296 — Migrate top-identifiers to /occurrences/stats/ + Stats API Convention

**Status**: Plan written 2026-05-13. Implementation pending.
**Branch**: `feat/project-overview` (`worktree-project-overview` worktree)
**PR**: https://github.com/RolnickLab/antenna/pull/1296

## Where we are

4 commits already pushed to `origin/feat/project-overview`:

1. `8494ad34` — `fix(project-overview): address PR review feedback` (drop email field, refactor view to use serializer, set `require_project=True`, `Count(filter=Q)`, list-item img cropping fix)
2. `7758499c` — `fix(api): gate top-identifiers endpoint on project visibility` (Project.visible_for_user 404 gate)
3. `b671d699` — `fix(api): count distinct occurrences in top-identifiers leaderboard` (`Count("identifications__occurrence", distinct=True)`)
4. `253d5dcf` — `refactor(summary): extract SummaryColumn to dedupe overview columns` (#7 from takeaway review, also drops dead `?ordering=` on per-row detail-page links)

Stack still running with worktree code bind-mounted into main project compose. UI dev server on port 4000. Backend on 8000.

## Decision: stats endpoint convention

After comparing iNat / GitHub / GitLab / Stripe / eBird / GBIF conventions, and probing the current route table:

```
/users/...                     handled by djoser router (registered as r"users")
/users/identifications/top/    handled by explicit path() listed BEFORE router.urls →
                               works today because Django URL resolver matches in order;
                               not actually claimed by djoser, but bypasses the router
                               → pollutes /users/ hierarchy + no autodoc grouping
/identifications/              our IdentificationViewSet
/occurrences/                  our OccurrenceViewSet
/occurrences/stats/            currently dispatches to OccurrenceViewSet.retrieve(pk="stats")
                               → 404 via Occurrence.objects.get(pk="stats") ValueError.
                               NOT clean greenfield — slot must be claimed by registering
                               r"occurrences/stats" BEFORE r"occurrences"
```

Migration motivation: `/users/identifications/top/` lives outside the router → no autodoc, no
consistency with `/projects/<id>/...` and `/captures/...`. Also: this PR ships the first
aggregate-stats endpoint, so the route shape sets precedent for many future ones.

**Chosen pattern**: `/<entity>/stats/<kind>/?project_id=X`

- **Entity-rooted** (iNat domain precedent): path tells caller what universe is being aggregated
- **Explicit `stats/` 2nd segment** (GitHub-flavored): discoverable, distinct from raw list endpoints
- **Nested under entity prefix** (not sibling `r"occurrence-stats"`): reads hierarchically. Cost:
  must register `r"occurrences/stats"` BEFORE `r"occurrences"` else DRF's retrieve route eats it.
  Annotate the registration in `config/api_router.py` with a `# NB:` comment for future readers
- **Noun = `stats`** (not `metrics`): "metrics" carries observability/Prometheus connotation
  (request rates, latency, ops dashboards). "Stats" reads as product-domain aggregates (counts,
  rankings, distributions). Pairs cleanly with existing `/status/summary/` global-scalar endpoint
- **`?project_id=X` scope param**: consistent with existing `ProjectMixin` query-param scoping
  across deployments/events/captures/taxa. `require_project=True` enforces at framework level
  via `self.get_active_project()` — but only fires when the action calls it. Every `@action`
  on a stats viewset MUST call `self.get_active_project()`; docstring reminds
- **Kebab-kind URL slugs**: matches existing router convention (`source-images`, `data-exports`)
- **Org-future**: `?organization_id=Y` query param. Same URL shape. Stats functions take `scope`
  and dispatch
- **Module layout** (M2 colocated): stats query functions live near the entity
  (`ami/main/models_future/occurrence.py`), viewsets thin compose
- **Response shape is per-kind, always declared via DRF serializer**: ranked top-N returns
  envelope `{project_id, <kind>: [...]}` matching the existing top-identifiers shape; scalar
  aggregates return `{...}`; charts return Plotly-shaped objects modelled with nested
  serializers. NEVER `Response({"some": "dict"})` with no declared schema. Use
  `@extend_schema(responses=...)` so OpenAPI captures shape. Pydantic NOT used — DRF
  serializers integrate with drf-spectacular natively; Pydantic would introduce a parallel
  type system for no benefit
- **Query-param validation via `SingleParamSerializer`** (existing convention,
  `ami/base/serializers.py:108`): every query param gets a typed field. Bad values 400, not 500.
  See `ami/jobs/views.py:321` for the rationale comment

**Specifically for this PR**: `/occurrences/stats/top-identifiers/?project_id=X&limit=5`

## Future sibling endpoints under this pattern

- `/occurrences/stats/species-counts/?project_id=X` — top species (alternative to current Taxon viewset ordering)
- `/occurrences/stats/by-algorithm/?project_id=X` — occurrence distribution by ML pipeline
- `/captures/stats/processing-progress/?project_id=X` or `?deployment_id=Y` — % images processed
- `/classifications/stats/accuracy/?project_id=X` — species-wise accuracy from predictions+verifications
- Org-level same paths, swap `?organization_id=Y`

## Implementation plan (3 commits, on top of `253d5dcf`)

### Commit 1: extract query into models_future, no behavior change

**File**: `ami/main/models_future/occurrence.py` (new)

```python
from django.db.models import Count, Q
from ami.main.models import User, Project


def top_identifiers_for_project(project: Project, limit: int = 5):
    """Return a queryset of Users annotated with their identification_count
    (distinct occurrences identified) for the given project, ordered desc.
    """
    return (
        User.objects.filter(identifications__occurrence__project=project)
        .annotate(
            identification_count=Count(
                "identifications__occurrence",
                filter=Q(identifications__occurrence__project=project),
                distinct=True,
            )
        )
        .filter(identification_count__gt=0)
        .order_by("-identification_count")[:limit]
    )
```

**File**: `ami/main/api/views.py::UserIdentificationCountsView.get` — call the new function instead of inlining. Keeps existing route working.

### Commit 2: add /occurrences/stats/ viewset with top-identifiers action + tests

**File**: `ami/main/api/views.py`

```python
class TopIdentifiersResponseSerializer(serializers.Serializer):
    """Declared response shape for /occurrences/stats/top-identifiers/.

    Envelope keeps the existing FE contract Anna built (project_id + named list).
    Future stats actions either keep an envelope keyed by their kind name, OR
    return a scalar dict / nested Plotly-shaped object — but ALWAYS via a
    declared serializer so OpenAPI captures the shape. No raw Response({...}).
    """
    project_id = serializers.IntegerField()
    top_identifiers = UserIdentificationCountSerializer(many=True)


class OccurrenceStatsViewSet(viewsets.ViewSet, ProjectMixin):
    """Aggregate stats over Occurrences. Each @action = one stats kind.

    Convention (see docs/claude/planning/pr-1296-occurrence-stats-migration.md):
    - URL: /<entity>/stats/<kind>/?project_id=X[&limit=N&...]
    - Every action MUST call `self.get_active_project()` — `require_project=True`
      only enforces through that call path, NOT automatically per request.
    - Every action MUST declare its response via @extend_schema(responses=...)
      with a serializer. No raw Response({...}) shapes.
    - Query params validated via SingleParamSerializer (ami/base/serializers.py).
    """
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

        queryset = top_identifiers_for_project(project, limit=limit)
        user_serializer = UserIdentificationCountSerializer(queryset, many=True, context={"request": request})
        return Response({"project_id": project.id, "top_identifiers": user_serializer.data})
```

**Note**: `limit_doc_param` = new `OpenApiParameter("limit", int, required=False, default=5,
description="1-50; 400 if out of range")`. Add alongside `project_id_doc_param`.

**File**: `config/api_router.py`

```python
# NB: r"occurrences/stats" MUST register BEFORE r"occurrences" — DRF's DefaultRouter
# preserves registration order and the OccurrenceViewSet's retrieve route
# `^occurrences/(?P<pk>[^/.]+)/$` would otherwise capture `/occurrences/stats/`.
router.register(r"occurrences/stats", views.OccurrenceStatsViewSet, basename="occurrence-stats")
router.register(r"occurrences", views.OccurrenceViewSet)  # existing line, just moved below
```

**File**: `ami/main/tests/test_api.py` (or wherever the existing UserIdentificationCounts tests live)

Tests required in this commit (NOT a follow-up):
- `test_top_identifiers_happy_path` — `?project_id=18` returns 200 + envelope shape +
  ordered desc by `identification_count`
- `test_top_identifiers_with_limit` — `?project_id=18&limit=2` returns 200 + 2 entries
- `test_top_identifiers_limit_out_of_range` — `?project_id=18&limit=0` → 400;
  `?project_id=18&limit=99` → 400
- `test_top_identifiers_no_project_id` — no `project_id` → 400 (require_project)
- `test_top_identifiers_invisible_project_anon` — draft project as anonymous → 404
- `test_top_identifiers_distinct_count` — user with 2 identifications on same occurrence
  counts as 1 (the b671d699 fix)
- `test_registration_order` — assert `/occurrences/stats/` resolves to
  `OccurrenceStatsViewSet` not `OccurrenceViewSet.retrieve` (catches accidental
  re-registration order changes)

### Commit 3: flip UI hook + drop old route/view

**File**: move `ui/src/data-services/hooks/identifications/useTopIdentifiers.ts` →
`ui/src/data-services/hooks/occurrences/stats/useTopIdentifiers.ts`

- Change URL to `${API_URL}/occurrences/stats/top-identifiers/?project_id=...`
- Optionally add `&limit=5` (default matches backend)
- **Response interface UNCHANGED**: `{project_id?, top_identifiers: [...]}` envelope kept
  (Anna's existing shape). Only the URL flips
- Update import sites in `ui/src/pages/project/summary/summary.tsx` to new path

**File**: `ui/src/pages/project/summary/summary.tsx::MostIdentifications`

- No data-shape changes (envelope unchanged), just the import path update from
  `data-services/hooks/identifications/useTopIdentifiers` →
  `data-services/hooks/occurrences/stats/useTopIdentifiers`

**File**: `ami/main/api/views.py`

- Delete `UserIdentificationCountsView` class
- Serializer `UserIdentificationCountSerializer` stays (used by new viewset)

**File**: `config/api_router.py`

- Remove `path("users/identifications/top/", ...)` registration

**Verification**:
- `curl /api/v2/occurrences/stats/top-identifiers/?project_id=18` → 200 envelope
- `curl /api/v2/occurrences/stats/top-identifiers/?project_id=18&limit=2` → 200, 2 entries
- `curl /api/v2/occurrences/stats/top-identifiers/` → 400 (project_id required)
- `curl /api/v2/occurrences/stats/top-identifiers/?project_id=18&limit=99` → 400
- `curl /api/v2/occurrences/stats/top-identifiers/?project_id=99999` → 404
- `curl /api/v2/users/identifications/top/?project_id=18` → 404 (old route gone)
- Browser: project 18 summary → "Most identifications" panel renders top 5 with same
  numbers as before (Kent 31, Mohamed 5, etc)

### Commit 4: convention reference doc

**File**: `docs/claude/reference/api-stats-pattern.md` (new)

One page. Sections:
1. **Pattern**: `/<entity>/stats/<kind>/?project_id=X[&...]` with kebab-kind, scope as query
2. **Why nested + the registration-order trap** (link back to this planning doc)
3. **Why `stats` not `metrics`** (metrics = observability connotation; stats = product aggregates)
4. **Response shapes per kind** (envelope vs scalar vs Plotly-nested), all serializer-declared
5. **Query param validation** via `SingleParamSerializer`
6. **`get_active_project()` discipline** (require_project=True only fires when called)
7. **Org-future**: same URL, `?organization_id=Y` swaps in

PR description links to this ref doc. Future stats endpoints follow it.

## After this PR — convention propagation tasks

1. Open follow-up issue: "Migrate /status/summary/ to /projects/<id>/stats/ or /summary/ pattern
   (decide later)" — note current `SummaryView` is the scalar-counts special case, doesn't need
   urgent migration
2. Next stats endpoint that lands (species-accuracy, processing-progress, etc) confirms the
   convention. If the 2nd endpoint resists the entity-rooted shape, revisit
3. Add convention pointer to `docs/claude/INDEX.md` after Commit 4

## Closed concerns (from second review pass 2026-05-13)

- ~~Sibling vs nested route shape~~ — nested won (hierarchy reads better, ordering trap accepted)
- ~~`stats` vs `metrics` noun~~ — `stats` won (no observability/Prometheus connotation)
- ~~Pydantic vs DRF serializer for response shape~~ — DRF (drf-spectacular integration native)
- ~~Drop envelope vs keep Anna's envelope~~ — keep (FE doesn't change, future stats endpoints
  follow per-kind shape rules)
- ~~`limit` clamp vs strict validation~~ — strict via `SingleParamSerializer` (400 on out-of-range,
  matches `ami/jobs/views.py:321` precedent)
- ~~Tests as open question~~ — required in Commit 2
- ~~djoser-squat claim~~ — wrong; the path() works fine, real issue is router bypass + namespace
  pollution
- ~~`/occurrences/stats/` clean greenfield claim~~ — wrong; falls into retrieve(pk="stats"),
  registration order is mandatory

## Resume instructions for next session

1. Pull latest on `feat/project-overview` (HEAD after this plan-update commit)
2. Stack still bind-mounted into main compose (`/home/michael/Projects/AMI/antenna/docker-compose.override.yml` overrides django+celeryworker+ui-dev to point at worktree)
3. Apply Commit 1 (extract query into `ami/main/models_future/occurrence.py`). `docker compose restart django`. Verify old `/users/identifications/top/?project_id=18` still returns same envelope
4. Apply Commit 2 (new viewset + route + tests). Probe new URL via curl, confirm registration order won (registration-order test catches regressions)
5. Apply Commit 3 (UI hook move + path flip + old route/view delete). Verify in browser
6. Commit 4 (convention reference doc)
7. Push all four. Reply on PR thread `3232119836` (mihow's "Do you think we will have other identifications stats to expose?") citing the ref doc + the new URL
