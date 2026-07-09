# Station row "Sync" floating action button — design

**Date:** 2026-06-29
**Scope (initial phase):** Frontend only (`ui/`). No backend change, no
migration. This describes the first phase only; the PR later grew a backend
piece (list-serializer field, bulk `sync-all` endpoint, and an ML-data-manager
permission with a data migration) — see the Addendum at the end of this document.
**Branch/worktree:** `worktree-station-sync-action`

## Summary

Add a "Sync" floating action button to each row in the Stations (deployments)
list table, alongside the existing Delete button. Clicking it opens a small
confirmation dialog; confirming triggers an asynchronous data-storage sync job
that scans the deployment's connected S3 storage source and imports any new
captures. The button mirrors the existing per-row action pattern (the Delete
trash icon) and reuses the sync endpoint and React Query hook that already power
the "Sync now" button in the deployment detail view.

## What already exists (no work needed)

- **Backend endpoint:** `POST /api/v2/deployments/{pk}/sync/`
  (`DeploymentViewSet.sync`, `ami/main/api/views.py:339-361`). Creates a
  `DataStorageSyncJob` and enqueues it; returns `{ "job_id": <int>,
  "project_id": <int> }`. Raises `ValidationError` (HTTP 400) when the
  deployment has no `data_source`.
- **React Query hook:** `useSyncDeploymentSourceImages`
  (`ui/src/data-services/hooks/deployments/useSyncDeploymentSourceImages.ts`).
  `POST`s to the endpoint, on success invalidates the `[JOBS]` and `[CAPTURES]`
  query keys, and exposes `{ syncDeploymentSourceImages, isLoading, isSuccess,
  error, data }` where `data.data` is `{ job_id, project_id }`.
- **Row action toolbar:** `Toolbar` from `nova-ui-kit`
  (`ui/src/nova-ui-kit/components/toolbar.tsx`) — the circular pill that holds
  per-row icon buttons.
- **Reference for the confirmation-dialog action pattern:** `DeleteEntityDialog`
  (`ui/src/pages/project/entities/delete-entity-dialog.tsx`) + `DeleteForm`
  (`ui/src/components/form/delete-form/delete-form.tsx`).
- **Reference for the sync UX (button states + job link):**
  `SyncDeploymentSourceImages`
  (`ui/src/pages/deployment-details/deployment-details-form/section-source-images/actions/sync-source-images.tsx`).

## Decisions (from brainstorming)

1. **Interaction:** confirmation dialog (not one-click). Matches the Delete
   button neighbor and guards against accidental row-misclicks.
2. **Gating:** `item.canUpdate` only. The deployments **list** serializer
   (`DeploymentListSerializer`, `ami/main/api/serializers.py:180-211`) carries
   no data-source field, so a "show only when connected" gate is not possible
   without a backend change, which we are deliberately not doing here.
   Consequence: the button shows on every station the user can update; clicking
   it on a station with **no** data source returns HTTP 400, which the dialog
   surfaces via `FormError` (see error handling below).
3. **Feedback:** inline icon state (the app has no toast system). Sync button
   shows a spinner while loading and a check on success; on success the dialog
   also renders an eye-icon link to the created job, mirroring the detail-view
   sync component.

## Components

### New file: `ui/src/pages/deployments/sync-deployment-dialog.tsx`

`SyncDeploymentDialog`, modeled on `DeleteEntityDialog`.

Props:

```ts
{
  id: string         // deployment id
  projectId: string  // for the job-details link route
}
```

Structure:

- `Dialog.Root` with a local `useState` `isOpen` flag (`open` / `onOpenChange`),
  same as `DeleteEntityDialog`.
- `Dialog.Trigger asChild` wrapping a `nova-ui-kit` `Button`:
  - `size="icon"`, `variant="ghost"`, `className="shrink-0"`,
    `aria-label={translate(STRING.SYNC)}`.
  - Child: lucide `RefreshCwIcon` at `className="w-4 h-4"`.
- `Dialog.Content` (`ariaCloselabel={translate(STRING.CLOSE)}`, `isCompact`)
  containing the confirmation body (built inline with the shared
  `FormSection` / `FormError` layout from `components/form/layout/layout`, the
  same primitives `DeleteForm` uses):
  - If `error`: `<FormError message={parseServerError(error)?.message} />`
    (covers the no-data-source 400).
  - `FormSection` with `title` = "Sync captures from storage source?" and
    `description` = `translate(STRING.MESSAGE_SYNC_CONFIRM)`.
  - A right-aligned button row:
    - Cancel `Button` (`size="small"`, `variant="outline"`) →
      `setIsOpen(false)`.
    - Sync `Button` (`size="small"`, `variant="success"`,
      `disabled={isLoading || isSuccess}`) → `syncDeploymentSourceImages(id)`.
      Label `translate(STRING.SYNC)`; shows `Loader2Icon` (spin) while loading,
      `CheckIcon` on success.
  - On success (`isSuccess && data`): render an eye-icon `Link`
    (styled `buttonVariants({ size: 'icon', variant: 'ghost' })`) to
    `APP_ROUTES.JOB_DETAILS({ projectId, jobId: String(data.data.job_id) })`
    via `getAppRoute({ to, keepSearchParams: true })`, wrapped in a
    `BasicTooltip` (`content` = "View sync job"). Same shape as the existing
    detail-view sync component.

Hook usage: `const { syncDeploymentSourceImages, isLoading, isSuccess, error,
data } = useSyncDeploymentSourceImages()`.

### Edit: `ui/src/pages/deployments/deployment-columns.tsx`

In the `actions` column `renderCell` (currently lines ~232-242), add the sync
button inside the existing `Toolbar`, to the **left** of the Delete button:

```tsx
<Toolbar>
  {item.canUpdate && (
    <SyncDeploymentDialog id={item.id} projectId={projectId} />
  )}
  {item.canDelete && (
    <DeleteEntityDialog
      collection={API_ROUTES.DEPLOYMENTS}
      id={item.id}
      type={translate(STRING.ENTITY_TYPE_DEPLOYMENT)}
    />
  )}
</Toolbar>
```

Add the import for `SyncDeploymentDialog`. `projectId` is already in scope
(the `columns({ projectId })` factory argument).

### Edit: `ui/src/utils/language.ts`

Add two `STRING` enum members and their English values:

- `SYNC` → `"Sync"` (button label + aria-label).
- `MESSAGE_SYNC_CONFIRM` →
  `"This scans the connected storage source and imports any new captures as a background job."`

Place them near the existing sync-related strings
(`MESSAGE_CAPTURE_SYNC_HIDDEN`, `FIELD_LABEL_LAST_SYNCED`) following the file's
ordering convention.

## Data flow

1. User hovers a station row → `Toolbar` appears → clicks the `RefreshCwIcon`.
2. `SyncDeploymentDialog` opens; user clicks **Sync**.
3. `syncDeploymentSourceImages(id)` → `POST /api/v2/deployments/{id}/sync/`.
4. **Success:** hook invalidates `[JOBS]` + `[CAPTURES]`; dialog shows the check
   state and the eye-icon link to the new job. User can click through to the
   job detail page or close the dialog.
5. **Failure (e.g. no data source → 400):** `error` is set; `FormError` renders
   the parsed server message inside the dialog. User can cancel.

## Error handling

- No-data-source stations: backend returns 400 `ValidationError`; surfaced in
  the dialog via `FormError` + `parseServerError`. The confirmation step plus
  the in-dialog error message is the agreed mitigation for gating on
  `canUpdate` only.
- Generic request failures: same `FormError` path.

## Testing / verification

- `cd ui && yarn lint` and `yarn format` clean.
- TypeScript compiles (`tsc --noEmit` via the build).
- Manual (Chrome DevTools MCP against the local stack):
  - Sync button appears in station rows for an Update-permitted user, left of
    Delete; hidden for users without Update permission.
  - Click → dialog → confirm → spinner → check → job link navigates to the job
    detail page; a `DataStorageSyncJob` is created.
  - Confirm on a station with no configured data source → dialog shows the 400
    error message, no job created.

## Known limitations / follow-ups

- **`isSuccess` persistence (resolved in-scope):** the mutation state lives on
  the row-mounted hook instance, so without intervention reopening the dialog on
  the same row would show the prior success/error state and leave the Sync
  button disabled. The hook now exposes `reset`, and the dialog calls it on open
  so each open offers a fresh sync. (More important here than in the detail-view
  sync component, which unmounts on navigation; a list row stays mounted.)
- **Connected gate:** deferred. If we later want to hide the button on
  unconnected stations (or add a "Last synced" column), add `data_source_uri`
  (or a lightweight `data_source_connected` boolean) to
  `DeploymentListSerializer.fields` and gate on it.

## Addendum (2026-07-01): connected gate + "Sync all"

After the live test, three follow-ups were pulled into this PR (per the product
owner's call):

### 1. `data_source_connected` on the list serializer
`DeploymentListSerializer` gets a read-only `data_source_connected` boolean
(`obj.data_source_id is not None`). No query cost (the id is on the row), no
migration. The per-row Sync button now shows only when
`item.canSync && item.dataSourceConnected`, so it is hidden on stations with no
storage source. The endpoint's 400 stays as a safety net for races. The field
also feeds "Sync all" eligibility on the frontend.

### 2. "Sync all" bulk endpoint
`DeploymentViewSet.sync_all` (`detail=False`, POST, `project_id` via
`ProjectMixin.get_active_project`). It enqueues one `DataStorageSyncJob` per
connected deployment in the project — **separate jobs, not one consolidated
job** — matching the admin bulk action (`DeploymentAdmin.sync_captures`) and the
single-`deployment` FK on `DataStorageSyncJob`. Returns
`{ job_ids, queued, project_id }`.

### 3. Permissions (the parts that are invisible in the diff)
- `ObjectPermission.has_permission` returns `True` and `has_object_permission`
  only fires on detail actions (via `get_object`). A `detail=False` action is
  therefore unguarded unless it checks permissions itself. `sync_all` checks a
  transient probe: `Deployment(project=project).check_permission(user, "sync")`,
  which resolves to the `sync_deployment` guardian permission — exactly what the
  per-row `sync` action requires. Superusers pass via Django's bypass;
  `ProjectManager` and `MLDataManager` pass via guardian; `BasicMember`,
  `Researcher`, and `Identifier` are denied (403).
- The per-row button is gated on `canSync` — the `sync` entry in a deployment's
  `user_permissions`, backed by the `sync_deployment` guardian permission.
  Superusers receive `sync` there too: guardian's `get_perms` returns every
  permission defined on the project's content type for a superuser, and
  `sync_deployment` is one of them. `sync_deployment` is held by `MLDataManager`
  and `ProjectManager` (and superusers); `update_deployment` is held only by
  `ProjectManager`, so gating on `canUpdate` would wrongly hide the button from
  ML data managers who can sync. `canSync` is the exact set of users who may
  sync.
