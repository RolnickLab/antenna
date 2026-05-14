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
/users/                       HTTP 401   djoser owns this
/users/identifications/       HTTP 401   djoser interpreting as user PK/action
/users/identifications/top/   HTTP 401   squatting on djoser namespace
/identifications/             HTTP 200   our IdentificationViewSet
/occurrences/                 HTTP 400   our OccurrenceViewSet
/occurrences/stats/           HTTP 404   clean greenfield
```

`/users/identifications/top/` invented 3 levels in djoser-managed territory. Migrate.

**Chosen pattern**: `/<entity>/stats/<kind>/?project_id=X`

- **Entity-rooted** (iNat domain precedent): path tells caller what universe is being aggregated
- **Explicit `stats/` 2nd segment** (GitHub-flavored): discoverable, distinct from raw list endpoints
- **`?project_id=X` scope param**: consistent with existing `ProjectMixin` query-param scoping across deployments/events/captures/taxa. `require_project=True` on the view enforces it at framework level
- **Kebab-kind URL slugs**: matches existing router convention (`source-images`, `data-exports`)
- **Org-future**: `?organization_id=Y` query param. Same URL shape. Stats functions take `scope` and dispatch
- **Module layout** (M2 colocated): stats query functions live near the entity (`ami/main/models_future/occurrence.py`), viewsets thin compose

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

### Commit 2: add /occurrences/stats/ viewset with top-identifiers action

**File**: `ami/main/api/views.py`

```python
class OccurrenceStatsViewSet(viewsets.ViewSet, ProjectMixin):
    """Aggregate stats over Occurrences. Each @action = one stats kind.

    Convention: /<entity>/stats/<kind>/?project_id=X (see docs/claude/planning/
    pr-1296-occurrence-stats-migration.md for the rationale).
    """
    permission_classes = [IsActiveStaffOrReadOnly]
    require_project = True

    @extend_schema(parameters=[project_id_doc_param, ...])
    @action(detail=False, methods=["get"], url_path="top-identifiers")
    def top_identifiers(self, request):
        project = self.get_active_project()
        assert project is not None
        if not Project.objects.visible_for_user(request.user).filter(pk=project.pk).exists():
            raise NotFound("Project not found.")

        limit = int(request.query_params.get("limit", 5))
        limit = max(1, min(limit, 50))  # clamp

        queryset = top_identifiers_for_project(project, limit=limit)
        serializer = UserIdentificationCountSerializer(queryset, many=True, context={"request": request})
        return Response(serializer.data)
```

**File**: `config/api_router.py`

```python
router.register(r"occurrences/stats", views.OccurrenceStatsViewSet, basename="occurrence-stats")
# NB: must register BEFORE `router.register(r"occurrences", ...)` because DRF
# matches paths in registration order and `/occurrences/stats/` would otherwise
# be eaten by the OccurrenceViewSet's `<pk>` route.
```

(Verify registration-order constraint at apply time — DRF's `DefaultRouter` does typically match in order.)

**Response shape**: serializer `many=True` → returns plain list, no envelope:

```json
[
  {"id": 32, "name": "Kent McFarland", "image": "...", "identification_count": 31},
  ...
]
```

### Commit 3: flip UI hook + drop old route/view

**File**: `ui/src/data-services/hooks/identifications/useTopIdentifiers.ts`

- Change URL to `${API_URL}/occurrences/stats/top-identifiers/?project_id=...`
- Optionally add `&limit=5` (default matches backend)
- Change `Response` interface: was `{project_id?, top_identifiers: [...]}` → now `Array<{...}>`
- Return `{data, ...}` where `data` is the array

**File**: `ui/src/pages/project/summary/summary.tsx::MostIdentifications`

- `isEmpty={!data?.top_identifiers.length}` → `isEmpty={!data?.length}`
- `data?.top_identifiers.map(...)` → `data?.map(...)`

**File**: `ami/main/api/views.py`

- Delete `UserIdentificationCountsView` class
- Serializer `UserIdentificationCountSerializer` stays (still used by new viewset)

**File**: `config/api_router.py`

- Remove `path("users/identifications/top/", ...)` registration

**Verification**:
- `curl /api/v2/occurrences/stats/top-identifiers/?project_id=18` → 200 list
- `curl /api/v2/occurrences/stats/top-identifiers/?project_id=18&limit=2` → 200 list of 2
- `curl /api/v2/occurrences/stats/top-identifiers/` → 400 (project_id required)
- `curl /api/v2/occurrences/stats/top-identifiers/?project_id=99999` → 404
- `curl /api/v2/users/identifications/top/?project_id=18` → 404 (old route gone)
- Browser: project 18 summary → "Most identifications" panel renders top 5 with same numbers as before (Kent 31, Mohamed 5, etc)

### Optional Commit 4: convention note

Short addition to either:
- `ami/main/api/views.py::OccurrenceStatsViewSet` docstring (terse — links to planning doc)
- Or `docs/claude/reference/api-stats-pattern.md` (new) with the 5-bullet convention

Two-paragraph max. Anchors the pattern so the next stats endpoint follows it.

## Open questions left for implementation

- **Registration order** in `api_router.py`: need to verify whether registering `r"occurrences/stats"` before `r"occurrences"` actually wins, or whether DRF's `DefaultRouter` uses longest-prefix-match. Apply, test, adjust if needed (`path()` wrapper as fallback).
- **Permission**: keep `IsActiveStaffOrReadOnly` (anonymous read OK because visible_for_user gate covers draft-project case) or upgrade to `IsAuthenticated`? Current stance: keep, since the user-facing Summary page renders for unauth viewers of public projects.
- **`limit` validation**: simple int parse + clamp at the view, or a `FilterParamsSerializer`-style validator? View-level clamp is fine for v1.
- **Tests**: still missing (CodeRabbit flagged earlier). Add at least 3 cases — happy path with project, 400 without project_id, 404 for draft project as anonymous. Best to do alongside Commit 2.

## After this PR — convention propagation tasks

1. Open follow-up issue: "Migrate /status/summary/ to /projects/<id>/stats/ or /summary/ pattern (decide later)" — note current `SummaryView` is the scalar-counts special case, doesn't need urgent migration
2. Next stats endpoint that lands (species-accuracy, processing-progress, etc) confirms the convention. If the 2nd endpoint resists the entity-rooted shape, revisit.
3. Add convention to CLAUDE.md or `docs/claude/reference/` after 2nd endpoint lands

## Resume instructions for next session

1. Pull latest on `feat/project-overview` (4 commits at HEAD `253d5dcf`)
2. Stack still bind-mounted into main compose (`/home/michael/Projects/AMI/antenna/docker-compose.override.yml` overrides django+celeryworker+ui-dev to point at worktree)
3. Apply Commit 1 (extract query). `docker compose restart django`. Verify old `/users/identifications/top/?project_id=18` still returns same data
4. Apply Commit 2 (new viewset + route). Probe new URL via curl, confirm registration order
5. Apply Commit 3 (UI flip + old route delete). Verify in browser
6. Optionally Commit 4 (convention note)
7. Push all three. Reply on PR thread `3232119836` (mihow's "Do you think we will have other identifications stats to expose?" question) citing the convention doc + the new URL
