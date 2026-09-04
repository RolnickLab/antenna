# Station status and heartbeat — `POST /api/v2/deployments/{id}/status/`

Branch: `feat/deployment-status-heartbeat`, off `main`. One migration (a new model and
two fields on `Deployment`). The capture app is the first client.

## Why

A station in the field runs unattended for weeks. When it stops working — a flat
battery, a full disk, a survey that never started — the platform sees only an absence
of captures, which looks the same as a quiet night. `Deployment` carried no telemetry
of any kind, so a station's own account of itself had nowhere to land.

## Shape

- `StationStatusPayload` (`ami/main/models.py`) — a pydantic schema stored through
  `django_pydantic_field.SchemaField`, the same pattern as `Project.feature_flags`.
  Named fields for the readings an operator acts on: battery, storage, whether the
  station is capturing, what software it is running.
  - `Config.extra = "allow"`, so a station running newer software can report a reading
    the platform has no field for and the reading is stored rather than dropped. A
    reading reported often enough to filter or chart on should graduate into a named
    field.
  - `survey_config` holds the capture configuration verbatim, untyped. The capture
    app's own configuration is still changing shape, and storing it unparsed is better
    than losing it. It also means a capture's settings are recorded from the first
    heartbeat, rather than waiting for every field to be modelled here.
- `DeploymentStatus` — one row per report. `recorded_at` is the station's clock and
  orders the series; `created_at` is arrival. A station that was offline all night
  uploads a backlog, so the two differ by design, and the gap is how late it is running.
- `Deployment.last_status_at` / `Deployment.last_status` — the latest report copied onto
  the station, so a list can sort and filter on "last seen" without an aggregate query.
  Written by `Deployment.record_status()` with a queryset update, never `save()`:
  saving a Deployment recounts captures, occurrences and taxa and can queue a regrouping
  job, which is far too much work for a call that arrives every few minutes. A test pins
  this (`test_reporting_status_does_not_recount_the_station`).
- Permission: `Deployment.check_custom_permission` maps the `status` action to
  `SYNC_DEPLOYMENT`. Reporting a station's status is trusted at the same level as
  syncing its captures, and reusing that permission means no new guardian permission and
  no permission migration. Project managers and ML data managers hold it.
- A late report does not overwrite a newer one: `record_status` only refreshes the
  denormalized copy when the report it just stored is the newest by `recorded_at`.

## UI

- Station list: a "Last seen" column, sortable on `last_status_at`, with the reported
  status and battery underneath.
- Station detail: a "Station status" section, shown only once a station has ever
  reported — last seen, reported status, battery and state, storage free, software
  version, captures.

## Where the rest of a capture's provenance lives

This endpoint records what a station is doing *now*, including the configuration it is
running under. It is not the record of what any individual capture was taken with. That
belongs on the upload path, alongside the captures themselves — see
`2026-07-23-mobile-upload-api.md` — and is still open: a synced capture carries its
file and timestamp, not the settings that produced it. Until that lands, the heartbeat's
`survey_config` is the only place a station's capture settings are recorded, which is
why it is stored verbatim rather than dropped for being unmodelled.

## Not built here

- No notification or alert fires on a stale or unhealthy station. The denormalized
  fields exist so a trigger has something cheap to watch.
- No retention policy on `DeploymentStatus`. At one report a minute a station produces
  about half a million rows a year, so a prune or rollup will be needed before this runs
  at scale.
- No aggregate "station health" verdict. What counts as stale depends on the station's
  own reporting cadence, which it does not yet declare.
