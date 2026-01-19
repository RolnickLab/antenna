# Celery Worker Monitoring Guide

This guide explains how to monitor Celery worker health and detect issues like memory leaks or hung workers.

## Worker Protections In Place

The workers are configured with automatic protections to prevent long-running issues:

- **`--max-tasks-per-child=100`** - Each worker process restarts after 100 tasks
  - Prevents memory leaks from accumulating over time
  - Clean slate every 100 tasks ensures consistent performance

- **`--max-memory-per-child=2097152`** - Each worker process restarts if it exceeds 2 GiB
  - Measured in KB (2097152 KB = 2 GiB)
  - With prefork pool (default), this is **per worker process**
  - Example: 8 CPUs = 8 worker processes × 2 GiB = 16 GiB max total

These protections cause workers to gracefully restart before problems occur.

## Monitoring Tools

### 1. Flower (http://localhost:5555)

**Active Tasks View:**
- Shows currently running tasks
- Look for tasks stuck in "running" state for unusually long periods
- Your `CELERY_TASK_TIME_LIMIT` is 4 days, so anything approaching that is suspicious

**Worker Page:**
- Shows last heartbeat timestamp for each worker
- Stale heartbeat (> 60 seconds) indicates potential issue
- Shows worker status, active tasks, and resource usage

**Task Timeline:**
- Sort tasks by duration to find long-running ones
- Filter by state (SUCCESS, FAILURE, RETRY, etc.)
- See task arguments and return values

**Limitations:**
- Cannot detect workers in deadlock that stop sending heartbeats
- Shows task status but not detailed memory usage

### 2. New Relic APM

**Transaction Traces:**
- Automatic instrumentation via `newrelic-admin` wrapper
- See detailed task execution times and database queries
- Identify slow tasks that might cause memory buildup

**Infrastructure Monitoring:**
- Monitor container CPU and memory usage
- Set alerts for high memory usage approaching limits
- Track worker process count and restarts

**Custom Instrumentation:**
- Add custom metrics for task-specific monitoring
- Track business metrics (images processed, detections created, etc.)

### 3. Docker Monitoring

**Check worker health:**
```bash
# View running containers and resource usage
docker stats

# Check worker logs for restart messages
docker compose logs celeryworker | grep -i "restart\|warm shutdown\|cool shutdown"

# See recent worker activity
docker compose logs --tail=100 celeryworker
```

**Worker restart patterns:**
When a worker hits limits, you'll see:
```
[INFO/MainProcess] Warm shutdown (MainProcess)
[INFO/MainProcess] Celery worker: Restarting pool processes
```

## Detecting Hung Workers

### Signs of a hung worker:

1. **Tasks stuck in "started" state** (Flower active tasks page)
   - Task shows as running but makes no progress
   - Duration keeps increasing without completion

2. **Stale worker heartbeats** (Flower workers page)
   - Last heartbeat > 60 seconds ago
   - Worker shows as offline or unresponsive

3. **Queue backlog building up** (Flower or RabbitMQ management)
   - Tasks accumulating in queue but not being processed
   - Check: http://localhost:15672 (RabbitMQ management UI)
   - Default credentials: `rabbituser` / `rabbitpass`

4. **Container health** (Docker stats)
   - CPU stuck at 100% with no task progress
   - Memory at ceiling without task completion

### Manual investigation:

```bash
# Attach to worker container
docker compose exec celeryworker bash

# Check running Python processes
ps aux | grep celery

# Check memory usage of worker processes
ps aux --sort=-%mem | grep celery | head -10

# See active connections to RabbitMQ
netstat -an | grep 5672
```

## Recommended Monitoring Setup

### Flower Alerts (Manual Checks)

Visit Flower periodically and check:
1. Workers page - all workers showing recent heartbeats?
2. Tasks page - any tasks running > 1 hour?
3. Queue length - is it growing unexpectedly?

### New Relic Alerts (Automated)

Set up alerts for:
- Container memory > 80% for > 5 minutes
- Task duration > 1 hour (customize based on your use case)
- Worker process restarts > 10 per hour
- Queue depth > 100 tasks

### RabbitMQ Management UI

Access at: http://localhost:15672
- Monitor queue lengths
- Check consumer counts (should match number of worker processes)
- View connection status and channels

## Troubleshooting Common Issues

### Workers appear connected but tasks don't execute

**Symptoms:**
- Worker logs show "Connected to amqp://..." and "celery@... ready"
- `celery inspect` times out: "No nodes replied within time constraint"
- Flower shows "no workers connected"
- Task publishing hangs indefinitely
- RabbitMQ UI shows connections in "blocked" state

**Possible cause: RabbitMQ Disk Space Alarm**

When RabbitMQ runs low on disk space, it triggers an alarm and **blocks ALL connections** from publishing or consuming. This alarm is not prominently displayed in standard monitoring.

**Diagnosis:**

1. Check RabbitMQ Management UI (http://rabbitmq-server:15672) → Connections tab
   - Look for State = "blocked" or "blocking"

2. Check for active alarms on RabbitMQ server:
   ```bash
   rabbitmqctl list_alarms
   # Note: "rabbitmqctl status | grep alarms" is unreliable
   ```

3. Check disk space:
   ```bash
   df -h
   ```

4. Check RabbitMQ logs:
   ```bash
   journalctl -u rabbitmq-server -n 100 | grep -i "alarm\|block"
   ```

**Resolution:**

1. Free up disk space on RabbitMQ server
2. Verify alarm cleared: `rabbitmqctl list_alarms`
3. Adjust disk limit if needed: `rabbitmqctl set_disk_free_limit 5GB`
4. Restart RabbitMQ: `systemctl restart rabbitmq-server`
5. Restart workers: `docker compose restart celeryworker`

**Prevention:**
- Monitor disk space on RabbitMQ server (alert at 80% usage)
- Set reasonable disk free limit: `rabbitmqctl set_disk_free_limit 5GB`
- Configure log rotation for RabbitMQ logs
- Purge stale queues regularly (see below)

### Stale worker queues breaking celery inspect

**Symptoms:**
- `celery inspect` times out even after fixing RabbitMQ issues
- Multiple `celery@<old-container-id>.celery.pidbox` queues in RabbitMQ

**Cause:**
Worker restarts create new pidbox control queues but old ones persist. `celery inspect` broadcasts to ALL and waits, timing out on dead workers.

**Resolution:**
1. Go to RabbitMQ Management UI → Queues
2. Delete old `celery@<old-container-id>.celery.pidbox` queues
3. Keep only current worker's pidbox queue

**Alternative:** Target specific worker:
```bash
celery -A config.celery_app inspect stats -d celery@<current-worker-id>
```

### Worker keeps restarting every 100 tasks

**This is normal behavior** with `--max-tasks-per-child=100`.

If you see too many restarts:
- Check task complexity - are tasks heavier than expected?
- Consider increasing the limit: `--max-tasks-per-child=200`
- Monitor if specific task types cause issues

### Worker hitting memory limit frequently

If workers constantly hit the 2 GiB limit:
- Review which tasks use the most memory
- Optimize data loading (use streaming for large datasets)
- Consider increasing limit: `--max-memory-per-child=3145728` (3 GiB)
- Check for memory leaks in task code

### Tasks timing out

Current limits:
- `CELERY_TASK_TIME_LIMIT = 4 * 60 * 60 * 24` (4 days)
- `CELERY_TASK_SOFT_TIME_LIMIT = 3 * 60 * 60 * 24` (3 days)

These are very generous. If tasks timeout:
- Check task logs for errors
- Review data volume being processed
- Consider breaking large jobs into smaller tasks

### Queue backlog growing

Possible causes:
1. Workers offline - check `docker compose ps`
2. Tasks failing and retrying - check Flower failures
3. Task creation rate > processing rate - scale up workers
4. Tasks hung - restart workers: `docker compose restart celeryworker`

## Scaling Workers

### Horizontal scaling (more containers):

```bash
# Local development
docker compose up -d --scale celeryworker=3

# Production (docker-compose.worker.yml)
docker compose -f docker-compose.worker.yml up -d --scale celeryworker=3
```

### Vertical scaling (more processes per container):

Add concurrency flag to worker start command:
```bash
celery -A config.celery_app worker --queues=antenna --concurrency=16
```

Default is number of CPUs. Increase if CPU is underutilized.

## Memory Tuning Guidelines

Based on your ML workload:

**Current setting:** 2 GiB per worker process (production), 1 GiB (local dev)
**Task requirement:** JSON orchestration with large request/response payloads

This provides adequate headroom for JSON processing and HTTP overhead.

**If tasks consistently use more:**
- Increase: `--max-memory-per-child=3145728` (3 GiB)
- Ensure container/host has sufficient memory
- Monitor total memory: (num CPUs) × (limit per child)

**If tasks use much less:**
- Decrease: `--max-memory-per-child=1048576` (1 GiB)
- Allows more workers on same hardware
- Faster to detect actual memory leaks

## Best Practices

1. **Monitor regularly** - Check Flower dashboard daily during active development
2. **Log memory-intensive tasks** - Add logging for tasks processing large datasets
3. **Test limits locally** - Verify worker restarts work correctly in development
4. **Set New Relic alerts** - Automate detection of worker issues
5. **Review worker logs** - Look for patterns in restarts and failures
6. **Tune limits based on reality** - Adjust after observing actual task behavior
