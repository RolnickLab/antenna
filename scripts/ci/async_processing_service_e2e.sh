#!/usr/bin/env bash
# End-to-end check of pull (async) mode: Antenna queues an async_api job, the minimal
# processing service's worker pulls its tasks, and the results are saved. Run from the
# repository root after building the CI stack. Extra compose arguments (for example
# "-p name -f override.yml") can be passed in COMPOSE_ARGS.
set -euo pipefail

DC="docker compose -f docker-compose.ci.yml ${COMPOSE_ARGS:-} --profile async"
PIPELINE=constant

# Django migrates and creates the default project and image collection before serving.
$DC up -d django celeryworker
echo "Waiting for Antenna to serve requests..."
for attempt in $(seq 1 120); do
    if $DC exec -T django python -c '
import urllib.error, urllib.request
try:
    urllib.request.urlopen("http://localhost:8000/api/v2/", timeout=5)
except urllib.error.HTTPError:
    pass
' 2>/dev/null; then
        break
    fi
    if [ "$attempt" = 120 ]; then
        echo "Antenna did not start" >&2
        $DC logs --tail 50 django >&2
        exit 1
    fi
    sleep 5
done

$DC up -d ml_backend_worker

PROJECT_ID=$($DC exec -T django python manage.py shell -c \
    "from ami.main.models import Project; print(Project.objects.get(name='Default Project').pk)" 2>/dev/null | tail -1)

show_failure() {
    echo "--- worker" >&2
    $DC logs ml_backend_worker 2>&1 | grep -vE "GET /livez" | tail -40 >&2
    echo "--- celery: result tasks, retries and errors" >&2
    $DC logs celeryworker 2>&1 | grep -E "process_nats_pipeline_result|Pending images|acknowledged|ERROR|WARNING|Traceback|[Rr]etry" | tail -120 >&2
    echo "--- job log (warnings and errors)" >&2
    $DC exec -T django python manage.py shell -c \
        "from ami.jobs.models import JobLog; [print(l.level, l.message) for l in JobLog.objects.exclude(level__in=['INFO','DEBUG']).order_by('pk')]" >&2 || true
}

if ! $DC exec -T django python manage.py test_ml_job_e2e --project "$PROJECT_ID" --collection "Default Collection" \
    --pipeline "$PIPELINE" --dispatch-mode async_api --timeout 300; then
    show_failure
    exit 1
fi

$DC exec -T django python manage.py shell -c "
from ami.main.models import Classification, Detection, SourceImageCollection
images = SourceImageCollection.objects.get(project_id=$PROJECT_ID, name='Default Collection').images.all()
detections = Detection.objects.filter(source_image__in=images)
classifications = Classification.objects.filter(detection__in=detections, algorithm__key='constant-classifier')
assert images.exists(), 'The default collection has no images'
assert detections.values('source_image').distinct().count() == images.count(), 'Some images have no detections'
assert classifications.count() == detections.count(), f'{classifications.count()} classifications for {detections.count()} detections'
print(f'Async mode saved {detections.count()} detections and classifications for {images.count()} images')
"
