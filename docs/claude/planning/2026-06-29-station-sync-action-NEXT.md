# Station Sync action — session handoff / next steps

**Last updated:** 2026-07-01
**Worktree:** `/home/michael/Projects/AMI/antenna/.claude/worktrees/station-sync-action`
**Local branch:** `worktree-station-sync-action` → tracks `origin/feat/station-sync-action`
**PR:** #1357 (draft) — https://github.com/RolnickLab/antenna/pull/1357
**Head commit:** `89c25743`

## What is done (shipped in PR #1357, draft)

A per-row "Sync" floating action button on the Stations (deployments) list,
beside Delete. Confirmation dialog → fires the existing async
`DataStorageSyncJob` via `POST /api/v2/deployments/{id}/sync/`; shows spinner →
check + a link to the created job; no-data-source 400 surfaced via `FormError`.

**Note (historical):** this section describes the first phase. The shipped PR
also includes backend work — a `data_source_connected` list-serializer field, a
bulk `sync-all` endpoint, and granting the sync permission to ML data managers
(with a data migration). The "Frontend-only, no migration" framing applies to
the initial phase only.

Commits on the branch:
1. `e6a4303c` docs: design doc
2. `26439c41` implementation
3. `89c25743` self-review fixes (mutation `reset()` on dialog open; swallow the
   intended-400 rejection; clearer "Sync captures" dialog title)

Design doc: `docs/claude/planning/2026-06-29-station-sync-action-design.md`.

### Verification status
- lint / prettier / tsc clean for the changed files (only the pre-existing,
  unrelated `react-zoom-pan-pinch` missing-dep tsc errors remain in the tree).
- **NOT yet run against a live stack.** Local docker-compose browser test is the
  first next-session task.

### Repair note (context)
Early in the session the edits accidentally landed in the **main checkout**
(`/home/michael/Projects/AMI/antenna`, then on branch
`fix/disable-prod-admin-email-handler`). All work was moved to this worktree and
the main repo was reset back to `585b1b07` (clean, untouched). When operating in
a worktree: run git with `-C <worktree>` and edit files under the worktree path,
not the main checkout.

## Key files (current feature)
- `ui/src/pages/deployments/sync-deployment-dialog.tsx` — the dialog component.
- `ui/src/pages/deployments/deployment-columns.tsx` — actions column `Toolbar`
  (Sync gated on `item.canUpdate`, left of Delete).
- `ui/src/pages/deployments/deployments.tsx` — list page; header has
  `SortControl` (line ~49) and the "Create new station" control — where a
  "Sync all" button would go.
- `ui/src/data-services/hooks/deployments/useSyncDeploymentSourceImages.ts` —
  the mutation hook (now exposes `reset`).
- `ui/src/utils/language.ts` — strings `SYNC`, `SYNC_CAPTURES`,
  `MESSAGE_SYNC_CONFIRM`, `VIEW_JOB`.

## Next-session task list

### 1. Local docker-compose test (do first)
- `docker compose up -d` (from main repo, or bind-mount worktree `ui/`).
  Local UI: http://localhost:4000, API: http://localhost:8000, creds
  antenna@insectai.org / localadmin.
- To test worktree FE against the main stack, see
  `docs/claude/reference/worktree-testing.md` (bind-mount worktree subdirs) —
  note the compose file mounts `.:/app:z`, so mount subdirectories, not `/app`.
- Verify: button visibility by permission (`canUpdate`); confirm → job link
  navigates; no-data-source station → 400 shown in dialog; reopen after success
  offers a fresh sync (reset works).
- Use Chrome DevTools MCP for the browser checks + a PR screenshot.

### 2. Plan a "Sync all" button
- Location: Stations list header near "Create new station" / `SortControl`
  (`deployments.tsx`).
- Scope: sync every station in the project that has a data source and that the
  user can update. Confirmation dialog should state how many will be synced and
  that each starts its own job.
- Backend: there is **no bulk sync endpoint** today. Options:
  - (a) FE fires N `POST /deployments/{id}/sync/` calls (one per eligible
    station). Simple, reuses the object-permission-checked endpoint; but N
    requests + the FE must know which stations are eligible (the list serializer
    has no data-source field — see the connected-gate note below).
  - (b) New bulk endpoint, e.g. `POST /deployments/sync_all/?project_id=` (or a
    project-scoped action) that enqueues one job per deployment server-side and
    returns the job ids. Mirrors the admin bulk action (below). Fewer round
    trips, server decides eligibility.
  - Recommendation to discuss: (b) — it matches the admin precedent and keeps
    eligibility logic server-side.

### 3. Permissions review
- Per-row sync endpoint already enforces object perms:
  `DeploymentViewSet` has `permission_classes = [ObjectPermission]` and `sync`
  uses `self.get_object()` (`ami/main/api/views.py:284,303,339-361`). Good.
- FE gates the per-row button on `item.canUpdate`.
- For "Sync all": decide the required permission (project-level update? per-
  deployment update filtered server-side?) and make the bulk endpoint filter the
  queryset to deployments the user may update, skipping the rest (like the admin
  action skips no-project / no-data-source).

### 4. One consolidated job vs separate jobs (Sync all + Admin bulk)
**Precedent already in the codebase — separate jobs:**
- Admin bulk action `DeploymentAdmin.sync_captures` (`ami/main/admin.py:208-232`)
  loops the selected queryset and creates **one `DataStorageSyncJob` per
  deployment** (`job.enqueue()` each), skipping deployments with no project / no
  data source, then reports the queued job ids.
- Same one-task-per-item shape as `calculate_size_async` (admin.py:791) and
  `populate_collection_async` (admin.py:834).
- `DataStorageSyncJob` has a **single** `job.deployment` FK
  (`ami/jobs/models.py:700+`, `run()` calls `job.deployment.sync_captures(...)`),
  so a job models exactly one deployment today.

**Decision to make:**
- Keep **separate** (one job per station): zero backend model change, per-station
  progress / retry / visibility, consistent with admin + other bulk actions.
  Cost: floods the jobs list when syncing many stations at once.
- **Consolidate** (one job for a Sync-all run): single jobs-list entry and one
  progress bar, but requires either a new job type that iterates multiple
  deployments (M2M or project-scoped) or a parent/child job structure — real
  model + progress work.
- Leaning: keep separate for now (matches precedent, cheapest, most granular);
  revisit consolidation only if the jobs-list flooding becomes a real complaint.
  If consolidating, a "parent Sync-all job with child per-deployment jobs" is the
  cleaner shape than an M2M on `DataStorageSyncJob`.

## Open decision already flagged in PR #1357
- Visibility gate is `canUpdate` only because `DeploymentListSerializer`
  (`ami/main/api/serializers.py:180-211`) exposes no data-source field. To hide
  the button on unconnected stations (and to let a FE "Sync all" know
  eligibility), add `data_source_uri` (or a `data_source_connected` boolean) to
  the list serializer. This ties into task #2 option (a).
