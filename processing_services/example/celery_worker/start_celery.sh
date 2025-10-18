#!/bin/bash
set -e

QUEUES=$(python -m celery_worker.get_queues)

echo "Starting Celery with queues: $QUEUES"
celery -A celery_worker.worker worker --queues="$QUEUES" --loglevel=info --pool=solo # --concurrency=1
