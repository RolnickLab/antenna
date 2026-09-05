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
  **Three required identity fields — `device_id`, `device_type`, `software_version` —
  and nothing else declared.** `Config.extra = "allow"` keeps whatever the device
  publishes beyond them.

  This is the shape because devices differ in what they can sense. A phone knows its
  battery percentage; a mains-powered box knows only that it is powered; a box with no
  fuel gauge knows nothing about power at all. Naming battery, storage and capture
  counts in the schema made the platform's guesses look like a contract and left every
  station with blank rows for readings its hardware cannot take.

  The docstring lists conventional key names (`status`, `battery_percent`,
  `storage_free_bytes`, `survey_config`, …) so devices that do report the same reading
  agree on spelling. None is required or validated. A reading that turns out to be
  common, and that the platform wants to filter or chart on, is the one to promote into
  a named field later — which is a migration, not a guess.

- `DeploymentStatus` — one row per report. `recorded_at` is the device's clock and
  orders the series; `created_at` is arrival. A device offline all night uploads a
  backlog, so the two differ by design, and the gap is how late it is running.
- `Deployment.last_status_at` / `Deployment.last_status` — the latest report copied onto
  the station, so a list can sort and filter on "last seen" without an aggregate query.
  Written by `Deployment.record_status()` with a queryset update, never `save()`:
  saving a Deployment recounts captures, occurrences and taxa and can queue a regrouping
  job, which is far too much work for a call that arrives every few minutes. A test pins
  this (`test_reporting_status_does_not_recount_the_station`).
- Permission: `Deployment.check_custom_permission` maps the `status` action to
  `SYNC_DEPLOYMENT`. Reporting is trusted at the same level as syncing a station's
  captures, so no new guardian permission and no permission migration.
- A late report does not overwrite a newer one: `record_status` refreshes the
  denormalized copy only when the report it just stored is the newest by `recorded_at`.

## UI

- **Station list: "Last seen" only** — a date, sortable on `last_status_at`. Nothing
  else, because nothing else is common to every device yet.
- **Station detail: two sections.** "Station status" carries last seen plus the three
  identity fields. "Reported by the device" lists everything else that arrived, label
  derived from the key and value rendered by type, so a phone shows its battery and a
  trail camera shows its lamp hours without either being given the other's empty rows.
  Both sections appear only once a station has reported.

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
