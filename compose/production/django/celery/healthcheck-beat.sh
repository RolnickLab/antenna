#!/bin/bash
# Celerybeat healthcheck: verify the scheduler is alive by checking heartbeat file age.
#
# Beat doesn't respond to `celery inspect ping` (that's a worker control message),
# and with DatabaseScheduler (django_celery_beat) there's no schedule file whose
# mtime we can watch. So we rely on a dedicated `ami.tasks.beat_heartbeat` task
# that runs every 60s via CELERY_BEAT_SCHEDULE and touches /tmp/beat-heartbeat.
#
# If beat hangs (e.g. scheduler thread deadlocked on a Redis connection blip —
# the 2026-04-16 incident), the task stops firing and the file goes stale.
# Docker flips the container to `unhealthy`, autoheal restarts it.
#
# Window: task runs every 60s, we tolerate up to 2 min of staleness before
# marking unhealthy (one missed tick is fine; two in a row is a hang).
set -e
find /tmp/beat-heartbeat -mmin -2 2>/dev/null | grep -q . || exit 1
