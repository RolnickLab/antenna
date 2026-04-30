# Job state triangulation: DB + Redis + NATS

**Status:** captured for future work — low priority. Tracked in
[#1285](https://github.com/RolnickLab/antenna/issues/1285). Discussion
artifact from session 2026-04-30 following PR #1276.

## Problem

The platform has three distinct sources of truth for the lifecycle of an
async_api job:

1. **DB (`ami.jobs.models.Job`)** — `Job.status` (lifecycle enum) and
   `Job.progress` (Pydantic `JobProgress` JSONB). External-facing; what UI
   reads. Clobber-prone since #1261 dropped `select_for_update` from
   `_update_job_progress` (`ami/jobs/tasks.py`).
2. **Redis (`AsyncJobStateManager`)** — atomic per-image lifecycle: pending
   set per stage, failed set, total. Ephemeral (7-day TTL). Single source of
   truth used by reaper guard after PR #1276.
3. **NATS JetStream consumer state** — message lifecycle: `delivered`,
   `ack_floor`, `num_pending`, `num_ack_pending`, `num_redelivered`,
   `num_waiting`. Authoritative for what was dispatched and acked.

Each lies differently. None alone catches every bug class observed in
production.

## What each source knows that others don't

| Bug class | DB | Redis | NATS | Diagnosis signal |
|---|---|---|---|---|
| 2521 clobber (#1276 root cause) | progress incomplete | empty | `ack_floor == delivered` | last-writer race in `_update_job_progress` |
| Lost images (#1247) | stuck STARTED | non-empty | `num_pending > 0`, redelivery exhausted | NATS gave up, Redis still tracks |
| Worker crash loop | stuck STARTED | non-empty | `num_redelivered` climbing | infrastructure issue |
| Result-handler swallow | SUCCESS | failed set non-empty | drained | error path bug |
| Hung in-flight worker | progress 95% | non-empty | `ack_pending > 0` for minutes | worker stalled mid-batch |

DB alone catches none of these reliably. Redis catches most. Redis+NATS
catches all.

## Proposed: diagnostics endpoint

`GET /api/v2/jobs/<id>/diagnostics` returning structured triangulation:

```json
{
  "db": {
    "status": "STARTED",
    "celery_state": "SUCCESS",
    "progress_complete": false,
    "stages": {"process": 1.0, "results": 1.0, "collect": 0.0}
  },
  "redis": {
    "process": {"pending": 0, "total": 450},
    "results": {"pending": 0, "total": 450},
    "failed": [],
    "all_tasks_processed": true,
    "ttl_seconds": 580000
  },
  "nats": {
    "stream": "...",
    "consumer": "...",
    "delivered": 450,
    "ack_floor": 450,
    "num_pending": 0,
    "num_ack_pending": 0,
    "num_redelivered": 12,
    "num_waiting": 4
  },
  "divergence": [
    {
      "severity": "warn",
      "msg": "DB progress incomplete but Redis drained and NATS fully acked — likely _update_job_progress clobber"
    }
  ]
}
```

Cache 5–10s server-side (NATS info is async socket round-trip).

## Proposed: UI diagnostic panel

Default jobs detail view: keep existing progress bars (simple).

Add expandable **Diagnostics** panel (admin/power-user). Per stage row:

```
process     dispatched  acked   pending  failed  redelivered
            450/450     445     5        0       12
            ── NATS ──  ─NATS─  ─Redis─  Redis   NATS
```

Header strip: NATS consumer name, Redis TTL, DB vs Celery vs Redis truth
mismatch flags.

"Force reconcile" admin button = re-run reaper guard logic on demand.

## Proposed: snapshot on terminal transition

On terminal state change (SUCCESS / FAILURE / REVOKED), persist NATS
snapshot into `Job.progress.diagnostics` (or a new `Job.diagnostics` JSONB
field). Forensic record for post-mortems — NATS consumer state is
short-lived after job completion.

## Reuse for reaper

`AsyncJobStateManager.all_tasks_processed()` (added in #1276) is half of
this. Promote to `JobReconciler.diagnose()` returning the full structured
triangulation. Reaper consumes `diagnose().is_terminal_safe`. Diagnostics
endpoint consumes the same call. Single source of triangulation logic.

## Tradeoffs

- NATS info call needs JetStream credentials in Django (already have via
  natsconn work).
- More numbers = more confusion for non-admins → gate diag panel by
  permission.
- NATS consumer state goes stale fast post-completion (consumers are
  deleted). Snapshot-on-terminal mitigates.
- Adds a per-job NATS round-trip on diag endpoint hit. Cache + admin-only
  surface keeps cost bounded.

## Recommended implementation order

1. **Snapshot-on-terminal** first — cheap, no UI work, big forensic value.
2. **Diagnostics endpoint** + JSON shape. Lets reaper + admin tooling
   consume it; no UI needed yet.
3. **Promote reaper to consume `JobReconciler.diagnose()`** — replaces
   inline tri-state branch.
4. **UI diagnostic panel** last, once endpoint shape is stable.

## Related tickets

- #1232 — Redis-only follow-ups from PR #1231 retry-conflation work
- #721 — Backend bug: status stuck STARTED (user-facing symptom)
- #1085 — PSv2: integrate incomplete job monitoring
- #1134 — COMPLETED job state for partial-error jobs
- #1112 — Worker visibility per job
- #1166 — Processing service status indicator (UI side)
- #1168 — Async jobs hang when NATS exhausts max_deliver

## Why this is low priority

PR #1276 closes the immediate clobber-revoke loop with Redis-direct check.
Triangulation is the next step up: forensic visibility + catching adjacent
bug classes (#1247-style, result-handler swallow). Not blocking; pull when
the next stuck-job report lands and Redis-only signal is insufficient.
