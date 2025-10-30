#!/bin/bash
#
# Celery Worker Healthcheck Script
#
# This script checks if the Celery worker process is running and responsive.
# It uses two checks:
# 1. Process check - is celery worker process running?
# 2. Redis connectivity - can we connect to the broker?
#
# When used with the autoheal container, unhealthy workers will be
# automatically restarted.

set -e

# Check 1: Is the celery worker process running?
if ! pgrep -f "celery.*worker" > /dev/null 2>&1; then
    echo "ERROR: Celery worker process not found" >&2
    exit 1
fi

# Check 2: Can we connect to Redis (the broker)?
# Use redis-cli if available, otherwise skip
if command -v redis-cli > /dev/null 2>&1; then
    if ! redis-cli -h ${CELERY_BROKER_URL:-redis} ping > /dev/null 2>&1; then
        echo "ERROR: Cannot connect to Redis broker" >&2
        exit 1
    fi
fi

# All checks passed
exit 0
