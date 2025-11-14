#!/bin/bash
#
# Celery Worker Healthcheck Script
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
    # Extract host and port from CELERY_BROKER_URL (format: amqp://user:pass@host:port/vhost)
    # Default to rabbitmq:5672 if not set
    BROKER_URL="${CELERY_BROKER_URL:-amqp://rabbituser:rabbitpass@rabbitmq:5672/}"
    
    # Use Python to test the connection with a timeout
    if ! timeout 5 python -c "
import sys
from kombu import Connection
try:
    conn = Connection('${BROKER_URL}')
    conn.ensure_connection(max_retries=1, timeout=3)
    conn.release()
    sys.exit(0)
except Exception as e:
    print(f'ERROR: Cannot connect to RabbitMQ broker: {e}', file=sys.stderr)
    sys.exit(1)
" 2>&1; then
        echo "ERROR: Cannot connect to RabbitMQ broker" >&2
        exit 1
    fi
fi

# All checks passed
exit 0
