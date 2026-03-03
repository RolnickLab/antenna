#!/bin/bash
# Celery worker healthcheck: verify the worker is responsive via the broker.
# Catches stuck, deadlocked, and crashed workers — not just process existence.
set -e
exec celery -A config.celery_app inspect ping \
    --destination "celery@$(hostname)" \
    --timeout 10 > /dev/null 2>&1
