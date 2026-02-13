# NATS Infrastructure TODO

Tracked improvements for the NATS JetStream setup used by async ML pipeline jobs.

## Urgent

### Add `NATS_URL` to worker-2 env file

- **Status:** DONE (env var added, container reloaded, connection verified)
- **Root cause of job 2226 failure:** worker-2 was missing `NATS_URL` in `.envs/.production/.django`, so it defaulted to `nats://localhost:4222`. Every NATS ack from worker-2 failed with `Connect call failed ('127.0.0.1', 4222)`.
- **Fix applied in code:** Changed default in `config/settings/base.py:268` from `nats://localhost:4222` to `nats://nats:4222` (matches the hostname mapped via `extra_hosts` in all compose files).
- **Still needed on server:**
  ```bash
  ssh ami-cc "ssh ami-worker-2 'echo NATS_URL=nats://nats:4222 >> ~/ami-platform/.envs/.production/.django'"
  ssh ami-cc "ssh ami-worker-2 'cd ~/ami-platform && docker compose -f docker-compose.worker.yml restart celeryworker'"
  ```

## Error Handling

### Don't retry permanent errors

- **File:** `ami/ml/orchestration/nats_queue.py:118`
- **Current:** `max_deliver=5` retries every failed message, including permanent errors (404 image not found, malformed data, etc.)
- **Problem:** NATS has no way to distinguish transient vs permanent failures. If a task fails because the image URL is broken, it will be redelivered 5 times, wasting processing service time.
- **Proposed fix:** The error handling should happen in the celery task (`process_nats_pipeline_result`) and in the processing service, not in NATS redelivery. If the processing service returns an error result, the celery task should ack the NATS message (removing it from the queue) and record the error on the job. NATS redelivery should only cover the case where a consumer crashes mid-processing (no result posted at all).
- **Consider:** Reducing `max_deliver` to 2-3 since the only legitimate redelivery scenario is consumer crash/timeout, not application errors.

### Detect and surface exhausted messages (dead letters)

- **Current:** When a message hits `max_deliver`, NATS silently drops it. The job hangs forever with remaining images never processed and no error shown to the user.
- **Problem:** There's no feedback loop. The `process_nats_pipeline_result` celery task only runs when the processing service posts a result. If NATS stops delivering a message (because it hit `max_deliver`), no celery task fires, no log is written, and the job just stalls.
- **Proposed approach — poll consumer state from the celery job:**
  The `run_job` celery task currently returns immediately after queuing images. Instead, it could poll the NATS consumer state periodically until the job completes or stalls:

  ```python
  # In the run_job task or a separate watchdog task:
  async with TaskQueueManager() as manager:
      info = await js.consumer_info(stream_name, consumer_name)
      delivered = info.num_delivered
      ack_floor = info.ack_floor.stream_seq
      pending = info.num_pending
      ack_pending = info.num_ack_pending

      if pending == 0 and ack_pending == 0 and ack_floor < total_images:
          # Messages exhausted max_deliver — they're dead
          dead_count = total_images - ack_floor
          job.logger.error(
              f"{dead_count} tasks exceeded max delivery attempts "
              f"and will not be retried. {ack_floor}/{total_images} completed."
          )
          job.update_status(JobState.FAILURE)
  ```

  This would surface a clear error in the job logs visible in Django admin.

- **Alternative — NATS advisory subscription:**
  Subscribe to `$JS.EVENT.ADVISORY.CONSUMER.MAX_DELIVERIES.job_{id}.*` and log each dead message individually. More complex but gives per-message visibility.
- **Where to implement:** Either as a polling loop in `run_job` (simplest), or as a separate Celery Beat task that checks all active async jobs.
- **Files:** `ami/jobs/tasks.py` (run_job or new watchdog task), `ami/ml/orchestration/nats_queue.py` (add `get_consumer_info` method)

## Infrastructure

### Review NATS compose file on ami-redis-1

- **Location:** `docker-compose.yml` on ami-redis-1
- **Current config is mostly good:** ports exposed (4222, 8222), healthcheck configured, restart=always, JetStream enabled
- **Missing: Persistent volume.** JetStream stores data in `/tmp/nats/jetstream` (container temp dir). Server logs warn: `Temporary storage directory used, data could be lost on system reboot`. Add a volume mount:
  ```yaml
  nats:
    image: nats:2.10-alpine
    volumes:
      - nats-data:/data/jetstream
    command: ["-js", "-m", "8222", "-sd", "/data/jetstream"]
  volumes:
    nats-data:
  ```
- **Consider:** Adding memory/storage limits to JetStream config (`-js --max_mem_store`, `--max_file_store`) to prevent unbounded growth
- **Consider:** Adding NATS config file instead of CLI flags for more control (auth, logging level, connection limits)

### Clean up stale streams

- **Current:** 95 streams exist on the server, all but one are empty (from old jobs)
- **Cleanup runs on job completion** (`cleanup_async_job_resources` in `ami/ml/orchestration/jobs.py`), but only if the job fully completes. Failed/stuck jobs leave orphan streams.
- **Proposed fix:** Add a periodic Celery Beat task to clean up streams older than 24h (matching the `max_age=86400` retention on streams). Or clean up streams for jobs that are in a final state (SUCCESS, FAILURE, REVOKED).

### Expose NATS monitoring for dashboard access

- **Port 8222 is already exposed** on ami-redis-1, so `http://192.168.123.176:8222` should work from the VPN
- **For browser dashboard** (https://natsdashboard.com/): Needs the monitoring endpoint reachable from your browser. Use SSH tunnel if not on VPN:
  ```bash
  ssh -L 8222:localhost:8222 ami-cc -t "ssh -L 8222:localhost:8222 ami-redis-1"
  ```
  Then open https://natsdashboard.com/ with server URL `http://localhost:8222`

## Reliability

### Connection handling in ack path

- **Status:** DONE (PR #1130, branch `carlosg/natsconn` on `uw-ssec` remote)
- **What was done:** Added `retry_on_connection_error` decorator with exponential backoff. Replaced connection pool with async context manager pattern — each `async_to_sync()` call scopes one connection. Added `reconnected_cb`/`disconnected_cb` logging callbacks.
- **Commit:** `c384199f` refactor: simplify NATS connection handling — keep retry decorator, drop pool

### `check_processing_services_online` causing worker instability

- **Observed on both ami-live and worker-2:** This periodic Beat task hits soft time limit (10s) and hard time limit (20s) on every run, causing ForkPoolWorker processes to be SIGKILL'd.
- **Service #13 "Zero Shot Detector Pipelines"** at `https://ml-zs.dev.insectai.org/` consistently times out.
- **Impact:** Worker pool instability, killed processes may have been mid-task. This could contribute to unreliable task processing.
- **Fix:** Either increase the time limit, skip known-offline services, or handle the timeout more gracefully.

## Source Code References

| File                                 | Line                               | What                                                       |
| ------------------------------------ | ---------------------------------- | ---------------------------------------------------------- |
| `config/settings/base.py`            | 268                                | `NATS_URL` setting (default changed to `nats://nats:4222`) |
| `ami/ml/orchestration/nats_queue.py` | 97-108                             | `TaskQueueManager` context manager + connection setup      |
| `ami/ml/orchestration/nats_queue.py` | 42-94                              | `retry_on_connection_error` decorator                      |
| `ami/ml/orchestration/nats_queue.py` | 191-215                            | Consumer config (`max_deliver`, `ack_wait`)                |
| `ami/jobs/tasks.py`                  | 134-149                            | `_ack_task_via_nats()`                                     |
| `ami/ml/orchestration/jobs.py`       | 14-55                              | `cleanup_async_job_resources()`                            |
| `ami/ml/tasks.py`                    | `check_processing_services_online` | Periodic health check (causing SIGKILL)                    |

## DevOps

### Move triage steps to `ami-devops` repo and create a Claude skill

- Port `docs/claude/debugging/nats-triage.md` to the `ami-devops` repo
- Create a Claude Code skill (slash command) for NATS triage that can run the diagnostic commands interactively
- Skill should accept a job ID and walk through the triage steps: check job logs, inspect NATS stream state, test connectivity from workers

## Other

- Processing service failing on batches with different image sizes
- How can we mark an image/task as failed and say don't retry?
- Processing service still needs to batch classifications (like prevous methods)
- Nats jobs appear stuck if there are any task failures: https://antenna.insectai.org/projects/18/jobs/2228
- If a task crashes, the whole worker seems to reset
- Then no tasks are found remaining for the job in NATS
  2026-02-09 18:23:49 [info ] No jobs found, sleeping for 5 seconds
  2026-02-09 18:23:54 [info ] Checking for jobs for pipeline panama_moths_2023
  2026-02-09 18:23:55 [info ] Checking for jobs for pipeline panama_moths_2024
  2026-02-09 18:23:55 [info ] Checking for jobs for pipeline quebec_vermont_moths_2023
  2026-02-09 18:23:55 [info ] Processing job 2229 with pipeline quebec_vermont_moths_2023
  2026-02-09 18:23:55 [info ] Worker 0/2 starting iteration for job 2229
  2026-02-09 18:23:55 [info ] Worker 1/2 starting iteration for job 2229
  2026-02-09 18:23:59 [info ] Worker 0: No more tasks for job 2229
  2026-02-09 18:23:59 [info ] Worker 0: Iterator finished
  2026-02-09 18:24:03 [info ] Worker 1: No more tasks for job 2229
  2026-02-09 18:24:03 [info ] Worker 1: Iterator finished
  2026-02-09 18:24:03 [info ] Done, detections: 0. Detecting time: 0.0, classification time: 0.0, dl time: 0.0, save time: 0.0

- Would love some logs like "no task has been picked up in X minutes" or "last seen", etc.
- Skip jobs that hbs no tasks in the initial query

- test in a SLUM job! yeah! in Victoria?

- jumps around between jobs - good thing? annoying? what about when there is only one job open? 
- time for time estimates

- bring back vectors asap
