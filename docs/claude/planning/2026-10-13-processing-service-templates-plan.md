# Processing-service templates: plan from main (2026-10-13, reworked)

Supersedes the vectors-first plan (`2026-10-13-processing-service-parity.md` on the parity branch). That work
(#1511, #1512) is parked as a later layer; see §6.

Goal: the template processing services in `processing_services/` work against the contract that is on
`main` today, in push (sync) and pull (async) mode, proven in CI on GitHub. Start from the open template PRs
#1252 (minimal v2 worker), #992 (global moths in `example`) and #952 (real classifiers in local dev). Feature
vectors come later, as a separate layer.

## 1. What main expects (origin/main e02b6772)

- **Schema** (`ami/ml/schemas.py`): no change from #1461; it adds `AlgorithmResult` storage but states that
  processing services cannot send results yet. No new task types to emit.
- **Push**: Antenna calls `/readyz` (status list = pipelines online) and `/info` (pipelines only); never `/livez`.
  `/process` gets `config` = pipeline default config merged with the project's config, and `detections` only when
  reprocessing is on. A non-2xx response is logged as an error result.
- **Pull**: `Authorization: Token` only (no Api-Key on main). Job listing
  `GET /jobs/?pipeline__slug__in=a,b&ids_only=1&incomplete_only=1&dispatch_mode=async_api` returns
  `{results:[{id, pipeline_slug}]}`, one job per call (random order). That call is also the idle heartbeat;
  liveness expires after 60 s. `POST /jobs/{id}/tasks/` `{batch_size, client_info?}`; `POST /jobs/{id}/result/`
  `{results:[PipelineTaskResult], client_info?}`; 503 when NATS or the broker is down; no 413 handling.
  Every task's image must appear in `source_images` of its result (that is how Antenna counts it processed).
  Registration `POST /projects/{id}/pipelines/` `{processing_service_name, pipelines}` → 201.
- **save_results**: exactly one detection-type algorithm per pipeline; every returned algorithm key registered;
  classifiers need a category map; `bbox: null` allowed; `terminal=false` for intermediate classifiers;
  score stored as `max(scores)`, taxon from the label string.
- **ADC main** (the real service the templates stand in for) uses the same job-listing query, Token auth, no
  `client_info`, manual registration, one result item per image posted per batch, `AMI_PIPELINES`.

## 2. Gaps

| Where | Gap | Severity |
|---|---|---|
| #1252 worker | Lists jobs one slug at a time with `pipeline__slug=…&status=STARTED`: no idle heartbeat (service shows offline after 60 s), misses RETRY jobs, lists sync jobs and then gets 400 from `/tasks/`, which aborts the poll pass | **High** |
| #1252 worker | 503 on `/result/` drops the batch until NATS redelivers; `reply_subject` None becomes `""` | Medium |
| #1252 worker | `ANTENNA_API_KEY` sends `Api-Key`, which main ignores (anonymous) — forward-compat for #1194 only | Low, document |
| #1252 | Lint check failing; conflicts with main (`.envs/.ci/.django`, `ami/main/tests.py`, append-only); no schema-drift guard; no CI test of pull mode; design doc drift | Medium |
| minimal (main) | `PipelineResultsResponse.errors` missing; `DetectionResponse.bbox` required (main: optional); `logits` default `[]` (main: None); dead `api/test.py` (imports a removed class), not run by CI | Low |
| #992 | **Weights URL is dead** (old host alias returns 403); the current host used by ADC main serves the weights (333 MB) and labels (0.9 MB) | **High** |
| #992 | `run()` zips predictions with the unfiltered detection list, so labels attach to the wrong detections when an image fails to load (CodeRabbit) | **High** |
| #992 | Returns only the top-1 score: the determination is right, but the stored `scores` array no longer lines up with the category map, so "top predictions" views mislabel it | Medium, decision D2 |
| #992 | `get_or_download_file` always uses `requests.get` (breaks local paths), no timeout, logs per 8 KB chunk; duplicate `get_best_device`; hard-coded class count; no tests; no human PR description; 254 commits behind main (merges cleanly) | Medium |
| #952 | Switches the dev `ml_backend` to `example` with no model caches (first `up` downloads HF models every recreate); removes the minimal worker from the default dev stack, which #1252 wants there | Medium |
| example | No pull mode | Later, decision D4 |
| Overlaps | #1194 (Api-Key auth) adds the same `register.py`/`start.sh`; #1089 (flat-bug) conflicts with #992 in `example/api/{pipelines,schemas}.py`; #1011 (Celery-direct templates) is opposed to #1252's design | Decision D5 |

## 3. Plan: PRs on main, in parallel where possible

### PR 0 (new, Antenna, in progress by an agent: branch `feat/classification-scores-from-logits`) — derive probabilities from logits
Owner decision D2: services send logits only; `scores` will be deprecated. Main reads `scores` in three places
(`ami/ml/models/pipeline.py:739` category-map lookup by argmax, `:810` and `:845` stored score), so a logits-only
classification fails today (`max([])`).
1. Extract the numerically stable softmax that class masking already uses (`ami/ml/post_processing/class_masking.py`)
   into a shared helper.
2. In `create_classification` and the category-map lookup: when `scores` is empty and `logits` is present, use
   softmax(logits) for the argmax and the stored score. Keep storing `scores` as derived values for now, because the
   predictions views read them (the deprecation of the column itself is a later step).
3. Schema docstrings: `logits` is the preferred field; `scores` optional and deprecated.
4. Tests: logits-only, scores-only (unchanged), both present (scores win, unchanged); a logits-only classification
   gets the same taxon, score and top-N as the equivalent scores-only one.
5. Reading: one `Classification` method prefers softmax(logits), falls back to `scores` for legacy rows, returns
   nothing for rows with neither (old data is expected to be reprocessed; no backfill).
6. Deprecation: one warning per algorithm per save batch when a service sends scores without logits; `scores`
   marked deprecated in the schema.
7. Later (PR 1 or after): minimal's classifiers send logits only, once PR 0 is merged.
PR 2 (#992) returns logits only and depends on PR 0.


All three are based on `main`, so GitHub CI runs on them (unlike the stacked vector PRs). Branches are updated by
merging `main` in, never rebased.

### PR 1 — #1252: the async template, working and tested in CI
Base main. Push to the existing branch.
1. Merge main; resolve the two append-only conflicts; fix the lint failure.
2. Worker listing: one call with `pipeline__slug__in`, `ids_only`, `incomplete_only`, `dispatch_mode=async_api`;
   use each job's `pipeline_slug` (ported from 89eb4136 on the parked branch).
3. Startup checks: no pipelines to poll → stop; keep errors per task out of the poll loop.
4. `/result/` 503: retry the POST with backoff before giving up; skip tasks with no `reply_subject` with a warning.
5. minimal schema parity with main: `errors`, optional `bbox`, `logits: None`; replace the dead `api/test.py`
   with real tests; add a drift guard: a test in Antenna's suite that imports nothing from the service but compares
   the field names of `worker/schemas.py` and `api/schemas.py` models to `ami/ml/schemas.py` (reads the files).
6. CI: `ml_backend_worker` service behind an `async` compose profile; `scripts/ci/async_processing_service_e2e.sh`;
   `test_ml_job_e2e --timeout` and non-zero exit on failure; workflow job `test-async-processing-service`;
   service unit tests step (ported from 10a3424e / 059e50b4, minus vectors).
7. Docs: README pull-mode section; design doc drift fixed; PR body refreshed.
Verify: service + worker unit tests; async e2e script on a fresh local stack; full backend suite;
`makemigrations --check`; pre-commit; then GitHub CI including the new job.

### PR 2 — #992: global moths classifier in `example`, correct and reproducible
Base main. Push to the existing branch. Independent of PR 1 (only `example/`).
1. Merge main.
2. Weights and labels from the current host, behind a `MODEL_BASE_URL` setting (as ADC's `AMI_MODEL_BASE_URL`).
3. Fix the prediction/detection misalignment (track the detections actually batched; `zip(strict=True)`).
4. `get_or_download_file`: local paths, timeout, progress logging every N MB; one `get_best_device`; class count
   from the labels file.
5. Return logits only (D2), the full 29,176-value vector per detection; no top-1 `scores`. Depends on PR 0.
6. Tests with a tiny fake model and labels file (no download): alignment when one crop fails, category map built
   from labels, `scores` length = number of classes (or per D2).
7. One real local run: download the weights, run the pipeline on the sample images on CPU, record time per image
   and response size per detection in the PR body.
8. Human PR description.

### PR 3 — #952: real models in local dev, async still available
Base main (or PR 2's branch until it merges). Push to the existing branch.
1. Dev `ml_backend` builds `example`, with HF, torch and weights caches as named volumes.
2. Keep the minimal service in the dev stack as the async worker (`api+worker`, per PR 1), so local dev has real
   models in push mode and a working pull-mode worker.
3. README: first-run download size and time; how to register pipelines.
Verify: dev stack up from clean; register; run one sync job on the global moths pipeline and one async job on
the minimal worker.

### Later
- PR 4: `example` in pull mode (D4).
- Vectors layer (§6).

## 4. Execution

PR 1 and PR 2 are independent and run in parallel in separate worktrees (one agent each, Sonnet for
implementation, reviewed here). PR 3 follows PR 2's fixes. Each PR gets a code review agent and a structural
review before it is marked ready. Stacks use their own compose project names and the overrides noted in §7.

## 5. Decisions needed before code

- **D1 — decided:** push to the existing branches of #1252/#992/#952, merging main in.
- **D2 — decided:** logits only; `scores` will be deprecated (PR 0 makes Antenna accept it).
- **D3 — decided:** keep the zero-shot "insect" detector in #992; ADC's FasterRCNN 2023 + moth/non-moth filter
  in a follow-up PR.
- **D4** `example` pull mode: share the worker package (build context moves to `processing_services/`) or copy it.
  Deferred to PR 4.
- **D5 — exploring:** auth, registration and identity must stay simple for local dev and work for real deployments.
  Options in §8 (from #1194, #1011, ADC and related issues).
- **D6** #1252's `ensure_default_project` runs in CI and local dev at Django startup — confirm that is wanted in
  `.envs/.ci` (the async e2e relies on it).

## 6. Parked: vectors layer (#1511, #1512)

Kept as drafts. After #1462 and #1479 merge and PRs 1–3 land, #1511's vector work is rebuilt on main and #1512 is
closed in favour of PR 1. Owner decisions already given for that layer: fix #1479's feature-only predicate ("has
an embedding algorithm and no classifier"); when the pipeline config requests features, every detection gets a
vector (diverging from ADC's classifier-keyed vectors that Antenna's readers do not see).

## 7. Local stack gotchas

`docker-compose.ci.yml` pins `container_name: ami_ci_nats` (override `!reset null` for parallel stacks); Celery's
`watchfiles` reloader dies with "Too many open files" when many stacks run, leaving async jobs PENDING (override the
command with plain `celery … worker`); an image built before `ensure_default_project` existed has an old `/start`.

## 8. Auth, registration and identity: three paths (D5)

Facts: main accepts only `Authorization: Token` (user tokens). #1194 (open, +1250/-119, 5 unresolved threads,
needs a rebase onto #1197's follow-ups) adds hashed, revocable per-service API keys (`Api-Key <prefix>.<secret>`),
identity from the key instead of `processing_service_name`, per-service heartbeat with `client_info`, and its own
`register.py`/`start.sh` that collide with #1252's (add/add). It leaves the `ids_only` job poll on plain object
permissions, so a key-only worker appears unable to list jobs (to verify). ADC needs its #136 to drop the service
name, so #1194 and ADC #136 must deploy together. Today non-superuser tokens cannot call `tasks`/`result` (#1263),
so workers run as superusers. #1011 is the old Celery-broker design, based on a stale branch; only its
`processing.py` split might be worth keeping.

| | (a) Token now, #1194 later | (b) #1194 first | (c) Hybrid (recommended) |
|---|---|---|---|
| Antenna now | #1252 only | finish #1194 + ADC #136 lockstep | #1252 now; later `ensure_default_project` also creates a local processing service and a dev key once #1194 exists |
| Local dev | zero-config (seeded superuser → token) | needs #1194's self-provisioning path (unreviewed) | zero-config now; no password in compose once a dev key is bootstrapped |
| Deployed | user token, name-keyed service, superuser worker (#1263) | per-service hashed keys, revocable, proper heartbeat | same as (a) until #1194, then same as (b) |
| Template auth order | token → login | key | key → token → login (already #1252's order) |
| Effort / risk | none / weak security | medium–large, blocks templates | small now, small switch later |
| Merge order | #1252 → #1194 rebases | #1194 + ADC #136 → #1252 | #1252 → #1194 drops its own `register.py`/`start.sh` (templates have one owner) → ADC #136 |

Recommendation (c): it is the least rework (#1252 is already forward-compatible), keeps local dev unblocked, and
gives deployments per-service keys as soon as #1194 lands. Before relying on #1194: let key-authenticated workers
poll jobs (or add `GET /jobs/next`, #1265, with key support), fix the discarded bootstrap key, and drop the `/tmp`
key cache. Suggest closing #1011 with thanks (owner's call).

PR 1's work (listing fix, CI async job, schema parity) is the same under (a) and (c); only (b) changes it.

## 9. Status (2026-10-13, evening)

| PR | State |
|---|---|
| #1513 (new) | Draft. Probabilities derived from logits on save; reads prefer stored `scores` (class masking rewrites them, keeps logits), then softmax(logits), then nothing; deprecation warning once per algorithm per batch; help-text migration `main/0100`. Full suite 863 OK. |
| #1252 | Pushed (main merged; listing fix; schema parity; tests; drift guard; CI async job). GitHub: lint, test, test-async-processing-service green on 746a74dd. |
| #992 | Pushed (main merged; live weights URL behind `MODEL_BASE_URL`; alignment fix; logits only, rounded to 4 decimals; tests; real CPU run: ~318 KB JSON per detection, 11–14 s warm per image, mostly the OWLv2 detector). Needs #1513 to save. |
| #952 | Pushed (main merged; model cache volume: first job 60 s and 3.6 GB, after recreate 13.7 s). |

**Intermittent lost result (Antenna, found by the new CI job).** First CI run on 2c83fb01: the worker processed all 6
tasks and `/result/` accepted all 6 (`results_queued` 4 + 2), the process stage reached 100%, but only 5 results were
saved and acknowledged (NATS delivery 1 never acked) and the job stayed STARTED at 83% past the 300 s timeout; no
redelivery reached the worker. Re-run on 746a74dd passed; 8 local runs passed. Not yet explained: the dump kept only
the last 80 log lines, so the missing `process_nats_pipeline_result` task's fate (failed and waiting for NATS
redelivery, retrying, or never run) is unknown. The improved dump in `scripts/ci/async_processing_service_e2e.sh`
prints the job's warnings/errors and the result-task lines next time. Candidate ticket; place it in the job-status
failure family before patching.

Open for the owner: auth path (§8, recommend c); #1513 read precedence; #992 logit rounding; whether to file the
lost-result ticket; ADC #149-style payload size for full logits (~318 KB per detection).
