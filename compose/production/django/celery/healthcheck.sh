#!/bin/bash
#
# Celery Worker Healthcheck Script (Production)
#
# This script checks if the Celery worker process is running and responsive.
# It uses two checks:
# 1. Process check - is celery worker process running?
# 2. RabbitMQ broker connectivity - can we connect to the broker?
#
# When used with the autoheal container, unhealthy workers will be
# automatically restarted.

set -e

# Check 1: Is the celery worker process running?
if ! pgrep -f "celery.*worker" > /dev/null 2>&1; then
    echo "ERROR: Celery worker process not found" >&2
    exit 1
fi

# Check 2: Can we connect to RabbitMQ (the broker)?
# Use Python and Celery's connection to test broker connectivity
if command -v python > /dev/null 2>&1; then
    # Use Python to test the connection with a timeout
    # Access CELERY_BROKER_URL from environment within Python for security
    if ! timeout 5 python -c "
import sys
import os
from kombu import Connection
try:
    broker_url = os.environ.get('CELERY_BROKER_URL', 'amqp://rabbituser:rabbitpass@rabbitmq:5672/')
    conn = Connection(broker_url)
    conn.ensure_connection(max_retries=1, timeout=3)
    conn.release()
    sys.exit(0)
except Exception as e:
    print('ERROR: Cannot connect to RabbitMQ broker: {0}'.format(str(e)), file=sys.stderr)
    sys.exit(1)
" 2>&1; then
        echo "ERROR: Cannot connect to RabbitMQ broker" >&2
        exit 1
    fi
fi

# All checks passed
exit 0
