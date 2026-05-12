# New Relic post-upgrade findings — 2026-05-11

**Status:** observations after PR #1299 (NR agent 9.6.0 → 12.1.0 + tuned config) shipped. Hypothesis-framed; no fixes proposed below the connection-pool incident.
**Companion doc:** [`2026-05-11-list-endpoint-perf-analysis.md`](2026-05-11-list-endpoint-perf-analysis.md) — covers the SourceImageCollection/SourceImage/Project.charts list-side detail this doc only summarizes.
**Data window:** ~1h after deploy; throughput 181 rpm, errorRate 0%, avg resp 65ms, 16 hosts reporting.

## tl;dr

1. **DB visibility restored.** `databaseCallCount` populated on 57% of transactions vs 2.8% one day earlier. ~20× lift, no other agent variables changed. Confirms the psycopg3 instrumentation gap was the cause, not ASGI context.
2. **Surfaced N+1 on `SourceImageViewSet.retrieve`** — 571 DB calls per single-image fetch, 1.5s p99. Hidden pre-upgrade; not on PR #1274's radar.
3. **Surfaced PG connection-slot exhaustion burst** around the deploy window (22:22–22:32 UTC). 440 `OperationalError` events, ~99% at `CsrfViewMiddleware.process_view` (request entry, before any view). Pattern suggests a pool-sizing or `CONN_MAX_AGE` issue rather than a slow-endpoint cause.
4. **`function_trace` config is mostly redundant** — DRF auto-instrumentation already captures every `*ViewSet.list/.retrieve`. Only the Pydantic-heavy serializer method and the two Celery task entries are still earning their slot.

## 1. DB visibility — before/after

NRQL:
```
SELECT filter(count(*), WHERE databaseCallCount IS NOT NULL) as with_db,
       count(*) as txns
FROM Transaction
WHERE appName = '<APP>'
SINCE 1 hour ago COMPARE WITH 1 day ago
```

| Window | Txns | With DB call count |
|---|---|---|
| Current (agent 12.1.0) | 9863 | **5669 (57.4%)** |
| 1 day ago (agent 9.6.0) | 8815 | 245 (2.8%) |

Postgres span breakdown is now usable: `main_occurrence/select` 191ms avg with a 568ms tail; `main_taxon/select` 21ms avg but a 704ms outlier; `ml_processingservice/update` 125 spans (periodic health check chatter, max 115ms); Redis `mget` 17780 calls @ 0.7ms avg (cachalot working as expected). None of this was queryable before the upgrade.

## 2. Top N+1 / slow-tail endpoints

Transactions filtered to `duration > 0.5s`, faceted by name, 1h window:

| Endpoint | n | avg | p99 | DB calls/req | DB ms |
|---|---|---|---|---|---|
| **`SourceImageViewSet.retrieve`** | 1 | 1469ms | 1469ms | **571** | 866ms |
| `OccurrenceViewSet.list` | 80 | 624ms | 1310ms | 194 | 177ms |
| `ProjectViewSet.list` | 9 | 578ms | 644ms | 242 | 305ms |
| `SourceImageViewSet.list` | 4 | 3489ms | 4974ms | 167 | 3335ms |
| `EventViewSet.list` | 1 | 4142ms | 4142ms | 118 | 3986ms |
| `SourceImageCollectionViewSet.list` | 4 | 3693ms | 10583ms | 117 | 3484ms |
| `SummaryView.get` | 4 | 965ms | 1542ms | 26 | 892ms |
| `TaxonViewSet.list` | 2 | 1441ms | 1505ms | 20 | 1363ms |
| `ProjectViewSet.charts` | 1 | 7585ms | 7585ms | 36 | 7457ms |

### Worth calling out

- **`SourceImageViewSet.retrieve` @ 571 DB calls** — only one sample in this window, but the call count is so far above the rest that it's almost certainly an N+1 (and not just slow individual queries). Companion doc covers the list endpoint; the **detail endpoint hasn't been audited**. Likely candidates: `detections` prefetch missing on the detail serializer, or `Occurrence.detection_images / .best_prediction / .best_identification` firing per detection inside the response.
- **`SourceImageCollectionViewSet.list` and `SourceImageViewSet.list`** are dominated by **DB time** (>95% of total). High DB-call counts but bigger fix is the SQL itself, not the count — see companion doc for the `COUNT(DISTINCT) FILTER (...)` annotation-explosion analysis.
- **`ProjectViewSet.charts` @ 7.6s with only 36 queries** — not an N+1. Aggregate-heavy SQL. Different fix shape (materialized view, or limit time range default).
- **PR #1274 target is real but not the worst offender.** OccurrenceViewSet.list at 194 calls / 1.3s p99 is in the upper tier, but Detail+Collection list outrank it on both call-count and tail.

## 3. PG connection-pool incident — 22:22–22:32 UTC

### Observation

`TransactionError` table, `error.class = django.db.utils:OperationalError`, last 24h:

```
22:22 UTC — 4 errors
22:27 UTC — 152 errors
22:32 UTC — 284 errors
all other hours — 0
```

Error messages:
- 402× `connection failed: FATAL: remaining connection slots are reserved for non-replication superuser connections`
- 22× `connection failed: FATAL: sorry, too many clients already`
- 15× combination of both

Faceted by `transactionName`:
- **435/440 at `WebTransaction/Function/django.middleware.csrf:CsrfViewMiddleware.process_view`**
- 4 at `OtherTransaction/Celery/ami.jobs.tasks.update_async_services_seen_for_pipelines`
- 1 at `WebTransaction/Function/ami.main.api.views:SourceImageViewSet.list`

### Interpretation (hedged)

The CSRF middleware runs early in the Django request lifecycle, and one of its first steps is resolving `request.user` — which opens a DB connection. Errors landing on CSRF rather than a downstream view means **most of these requests never reached a queryset** — they couldn't open a connection to start with. That's a pool-sizing/connection-lifecycle problem, not a slow-endpoint problem.

Possible contributors (none verified):
- `hostCount = 16` × `WEB_CONCURRENCY=4` (per `.envs/.production/.django-example` line 130) = **64 web workers minimum**, plus Celery (`CELERY_WORKER_CONCURRENCY=16`, line 28) on whichever host runs the worker = ~80 processes against PG.
- `psycopg[binary]==3.1.9` + Django default `CONN_MAX_AGE=0` (settings not searched for an override) = every request opens and closes a connection. Under uvicorn ASGI (async workers can handle many concurrent requests), the simultaneous-connection ceiling is much higher than `WEB_CONCURRENCY` alone suggests.
- PG default `max_connections=100` with `superuser_reserved_connections=3` = ~97 usable. Easily exhausted by the above.

The curve shape (4 → 152 → 284 over 15 minutes, growing) is **not** a single restart blip. Restarts produce a spike-and-drop. Sustained growth implies real load contention.

### What we still need to verify

- Confirm `CONN_MAX_AGE` setting in `config/settings/production.py`. If 0 (default), the suspicion is correct.
- Confirm whether pgbouncer fronts Postgres in production (no entry in `docker-compose.yml` here, but production may differ).
- Get PG `max_connections` from the live server (`SHOW max_connections;`).
- Correlate the 22:22 burst with deploy logs — did the NR upgrade restart cause a brief spike in concurrent connections during worker rollout? Or was it coincident with user-triggered load (e.g. a large job submission)?
- Check whether 22:22 was UTC or local — confirm against deploy timestamp.

### Directions to discuss

In order of effort/risk:

1. **`CONN_MAX_AGE=60`** in production settings — Django persistent connections. Single-line change, large effect on per-request connection churn. Risk: if a worker holds a stale connection across a PG restart, the request errors once. Acceptable trade-off.
2. **pgbouncer in transaction-pooling mode** in front of PG — caps the connection ceiling regardless of worker count. Bigger infra change but standard for Django/Celery setups.
3. **Lower `WEB_CONCURRENCY`** until pool is sized — quick bandage if neither above is fast to ship.

## 4. function_trace coverage — operational note

Verified that DRF auto-instrumentation in agent 12.1.0 already captures every `*ViewSet.list/.retrieve` we explicitly listed in `config/newrelic.ini` lines 194–202. The explicit entries that **are still pulling their weight**:

- `ami.main.api.serializers:OccurrenceListSerializer.get_determination_details` (842 calls/hr, captures per-row serializer cost)
- `ami.jobs.tasks:run_job` and `ami.jobs.tasks:process_nats_pipeline_result` (Celery tasks, no auto-instrumentation for these by name)
- `ami.main.models:Occurrence.detection_images / .best_prediction / .best_identification` (model methods called inside serializers; auto-instr doesn't see these)

The four `*ViewSet.list` / `JobViewSet.result` entries can be removed at the next config audit — they're duplicated by auto-instrumentation. Low priority (no cost penalty for keeping them, just config bloat).

## 5. Open follow-ups

- [ ] Audit `SourceImageViewSet.retrieve` for N+1 (571 DB calls in one sample is a clear smell).
- [ ] File / link a ticket on the 22:22 connection-pool incident with the `CONN_MAX_AGE` and pgbouncer questions answered.
- [ ] Re-check the same NRQL queries 24h after deploy to confirm steady-state DB visibility (this writeup is from the first hour after rollout).
- [ ] Trim redundant `function_trace` entries at next config audit.

## Method (for reproduction)

All queries run via the `newrelic` skill against `Antenna Backend (live)`. Pattern:
```
cd ~/Projects/AMI/ami-devops && set -a && . ./.env && set +a && cat > /tmp/q.json << EOF
{"query": "{ actor { account(id: $NEW_RELIC_ACCOUNT_ID) { nrql(query: \"<NRQL>\") { results } } } }"}
EOF
curl -s https://api.newrelic.com/graphql \
  -H "API-Key: $NEW_RELIC_API_KEY" \
  -H "Content-Type: application/json" \
  -d @/tmp/q.json | jq '.data.actor.account.nrql.results'
```
