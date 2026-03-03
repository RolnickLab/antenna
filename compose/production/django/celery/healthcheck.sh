#!/bin/bash
#
# Celery Worker Healthcheck Script (Production)
#
# Checks if the Celery worker process is running and not stopped.
# When used with the autoheal container, unhealthy workers will be
# automatically restarted.

set -e

# Check: Is the celery worker process running and not stopped?
CELERY_PIDS=$(pgrep -f "celery.*worker" || true)
if [ -z "$CELERY_PIDS" ]; then
    echo "ERROR: Celery worker process not found" >&2
    exit 1
fi

for pid in $CELERY_PIDS; do
    state=$(ps -o stat= -p "$pid" 2>/dev/null | awk '{print substr($1,1,1)}')
    if [ "$state" = "T" ]; then
        echo "ERROR: Celery worker process $pid is stopped (state: $state)" >&2
        exit 1
    fi
done

# All checks passed
exit 0
