# Station status and heartbeat — `POST /api/v2/deployments/{id}/status/`

Branch: `feat/deployment-status-heartbeat`, off `main`. One migration (a new model and
two fields on `Deployment`). The capture app is the first client.

## Why

Most stations never report anything. They are configured in Antenna and synced on
demand from an SD card or object storage, and that stays the normal case. This is for
the minority that have a device on the network: when one of those goes quiet, the
platform previously saw only an absence of captures, which looks exactly like a quiet
night. `Deployment` carried no telemetry of any kind, so a device's own account of
itself had nowhere to land.

Because a connected device is the exception rather than a property of every station,
none of this is presented as something a station has. A station that never reports shows
nothing, and loses nothing.

## Shape

- `StationStatusPayload` (`ami/main/models.py`) — a pydantic schema stored through
  `django_pydantic_field.SchemaField`, the same pattern as `Project.feature_flags`.
  **Two required fields — `device_id` and `software_version` — and nothing else
  declared.** `Config.extra = "allow"` keeps whatever the device publishes beyond them.

  Those two are required because nothing else records them: a station's `device` says
  what *kind* of hardware was configured, not which physical box is on site or what it
  is running. A device does not report its own type — that would duplicate the `Device`
  the station already carries, and the two could then disagree.

  Everything else is capability, and devices differ. A phone knows its battery
  percentage; a mains-powered box knows only that it is powered; a box with no fuel
  gauge knows nothing about power at all. Naming battery, storage and capture counts in
  the schema made the platform's guesses look like a contract and left every station
  with blank rows for readings its hardware cannot take.

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
- Permission, in two layers. **Sending** a report maps the `status` action to
  `SYNC_DEPLOYMENT` through `Deployment.check_custom_permission`, so it is trusted at the
  same level as syncing a station's captures — no new guardian permission and no
  permission migration. **Reading** what a device reported requires membership of the
  station's project and nothing more, so a basic member can see that a station needs
  attention without being able to speak for it.
- Membership is the line for reading because the report is operational detail — which
  unit is on site, what it runs, how much battery it has left — and a project that is
  not a draft is otherwise readable by anyone, including an anonymous visitor. The
  `last_status` and `last_status_at` fields are answered as null for a non-member rather
  than omitted, so the shape of the response does not change with the reader.
  `Project.is_member()` is the single test, asked once per project per response so a
  list of stations costs one extra query however many stations it holds.
- A late report does not overwrite a newer one: `record_status` refreshes the
  denormalized copy only when the report it just stored is the newest by `recorded_at`.

## UI

- **Station list: "Last seen" only** — a date, sortable on `last_status_at`, blank for
  every station that syncs offline. That blank is the honest answer, not a gap.
- **Station detail: one section, "Reported by the device"** — last seen, the device's
  id and software version, then everything else that arrived, label derived from the key
  and value rendered by type. It appears only when a device has reported, so a station
  configured for offline sync looks exactly as it did before.

## The client example

`ami/tests/test_station_status_client.py` is both the integration test for the endpoint
and the documentation a device author copies. It runs against a live server over real
HTTP, so the requests in it are exactly what a device sends; the client itself is the
two functions at the top of the file. Four situations are covered as tests: readings
through a night arriving in order, a device reporting only what it can measure, a report
refused for not naming the unit that sent it, and a backlog uploaded late without
overwriting what is current.

## Related, and deliberately not here

Device types and deployments both want configurable metadata of their own — a JSON field
per record, edited in the UI, queryable and publishable (#507, and #307 for the
deployment half). That is a different shape from this one: it is metadata a person
configures about a station, where this is a reading a device publishes about itself. The
two will sit beside each other on the same record, and this pull request stays on the
heartbeat.

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
