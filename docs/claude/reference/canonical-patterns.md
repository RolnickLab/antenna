# Canonical Patterns — Reuse Before Reinventing

"Use our existing pattern" is the most repeated review comment in this repository's history.
Check this list before writing a new helper, view method, or response format. Add to it
whenever a reviewer points at an existing pattern — that's the signal the pattern is
canonical but was undocumented.

## Backend (Django/DRF)

| Pattern | Where | Use for |
|---|---|---|
| `SingleParamSerializer` | `ami/base/serializers.py:108` (usage: `ami/base/views.py:47`) | Validating individual GET params — returns 400 on bad input instead of a 500 |
| `url_boolean_param()` | `ami/utils/fields.py:5` (usage: `ami/jobs/views.py:165`) | Boolean query params, e.g. `?incomplete_only=true` |
| `ProjectMixin` / `require_project` | `ami/base/views.py:67-96` | Project scoping on viewsets. Set `require_project` explicitly on every new viewset; `get_active_project()` raises 400/404 for you |
| Permission base classes | `ami/base/permissions.py:20` (`IsActiveStaffOrReadOnly`), `:118` (`IsProjectMemberOrReadOnly`), `:147` (`ObjectPermission`) | Object-level enforcement. `ObjectPermission` delegates to the model's `check_permission()`. DRF calls `check_object_permissions()` via `get_object()` — never look up objects by raw pk |
| `apply_default_filters()` | `ami/main/models.py:3118` (OccurrenceQuerySet) | All occurrence-related querysets — combines score thresholds + hierarchical taxa lists. Respects `apply_defaults=false` |
| Stats endpoints | `docs/claude/reference/api-stats-pattern.md` | Aggregate/leaderboard/chart endpoints: `GenericViewSet` + `@action` per stat kind, pure querysets in `ami/main/models_future/<entity>.py`, scalar dicts (not paginated lists) |
| Pydantic schemas | `ami/<app>/schemas.py` (exists in `base`, `utils`, `jobs`, `ml`, `main/api`, `main/checks`) | All structured payloads. Don't pass raw dicts where a schema exists |
| Queryset construction | Override `get_queryset()` | That's the method overridden everywhere else — don't build querysets inside individual actions |
| API responses | DRF serializers | Not hand-built dict responses |
| Test data | `ami/tests/fixtures/` (main.py, images.py, ml.py), `ami/users/tests/factories.py` | Use fixtures/factories, not manual model instantiation |
| Query-count assertion | `ami/ml/tests.py:1006` | `assertNumQueries` example — pair with a multi-row fixture |
| Permission matrix test | `ami/main/tests.py:1532-1590` | Template: owner / member / other-user tests asserting 200/403 per endpoint action |
| `update_calculated_fields()` | `ami/base/models.py:165` (usage: `ami/tests/fixtures/main.py:166`) | Refresh cached aggregates after related-data changes / bulk operations |

## Conventions

- **Raise, don't return sentinels** — error paths raise; DRF serializer validation produces the 4xx.
- **Schemas live in `ami/<app>/schemas.py`** — new Pydantic models go there, not inline in views/tasks.
- **Naming**: API filter keys for IDs use the `_id` suffix (`project_id`, not `project`). Renaming a public API param is a breaking change — keep the old name working or coordinate the frontend change in the same PR.

## Frontend

See `ui/CLAUDE.md` for frontend conventions, and
`docs/claude/reference/react-form-to-drf-values.md` for the form-value → DRF serializer
behavior reference.
