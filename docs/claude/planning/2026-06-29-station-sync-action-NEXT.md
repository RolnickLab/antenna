# Station Sync action — status

**Status:** shipped in PR #1357 — https://github.com/RolnickLab/antenna/pull/1357
**Branch:** `feat/station-sync-action`
**Design doc:** `docs/claude/planning/2026-06-29-station-sync-action-design.md`

## What shipped

- **Per-row "Sync"** floating action button on the Stations (deployments) list.
  Confirmation dialog → `POST /api/v2/deployments/{id}/sync/` → creates and
  enqueues a `DataStorageSyncJob`; success shows a link to the job.
- **Header "Sync all"** button → `POST /api/v2/deployments/sync-all/?project_id=`
  → one `DataStorageSyncJob` per connected station (separate jobs, matching the
  admin bulk action). Shown only when at least one station is syncable.
- **`data_source_connected`** boolean on `DeploymentListSerializer` so the
  frontend can hide the button on stations with no storage source.
- **Sync permission** (`sync_deployment`) granted to the ML data manager role
  (in addition to project manager), with data migration
  `0095_grant_sync_deployment_to_mldatamanager` backfilling existing projects.

## Permission model

- The sync action requires the `sync_deployment` guardian permission, held by
  ML data managers, project managers, and superusers. The frontend gates the
  button on `canSync` (the `sync` entry in a deployment's `user_permissions`);
  superusers receive it because guardian returns every project permission for
  them.
- `sync_all` is a `detail=False` action, which DRF does not route through
  `has_object_permission`, so it checks the permission itself with a transient
  probe: `Deployment(project=project).check_permission(user, "sync")`.

## Concurrency

Two syncs on the same station cannot corrupt data: event regrouping is
serialized by the per-deployment cache lock in `group_images_into_events`
(the "sync-time regroup" caller named in its docstring), and source-image
insertion upserts on `(deployment, path)`. Duplicate "Sync all" runs therefore
only cost redundant work and extra job rows, not incorrect state.
