#!/usr/bin/env bash
# End-to-end check of pull (async) mode: Antenna queues an async_api job, the minimal
# processing service's worker pulls its tasks, and the results, including feature vectors,
# are saved. Run from the repository root after building the CI stack. Extra compose
# arguments (for example "-p name -f override.yml") can be passed in COMPOSE_ARGS.
set -euo pipefail

DC="docker compose -f docker-compose.ci.yml ${COMPOSE_ARGS:-} --profile async"
PIPELINE=constant-with-feature-extractor
VECTOR_ALGORITHM=constant-feature-extractor
VECTOR_LENGTH=8

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

if ! $DC exec -T django python manage.py test_ml_job_e2e --project "$PROJECT_ID" --collection "Default Collection" \
    --pipeline "$PIPELINE" --dispatch-mode async_api --timeout 300; then
    $DC logs --tail 80 ml_backend_worker celeryworker >&2
    exit 1
fi

$DC exec -T django python manage.py shell -c "
from ami.main.models import Detection
from ami.ml.models.embedding import DetectionEmbedding
detections = Detection.objects.filter(source_image__project_id=$PROJECT_ID, source_image__collections__name='Default Collection')
vectors = DetectionEmbedding.objects.filter(detection__in=detections, algorithm__key='$VECTOR_ALGORITHM')
lengths = {len(vector) for vector in vectors.values_list('vector', flat=True)}
assert detections.exists(), 'The async job saved no detections'
assert vectors.count() == detections.count(), f'{vectors.count()} vectors for {detections.count()} detections'
assert lengths == {$VECTOR_LENGTH}, f'Unexpected vector lengths: {lengths}'
print(f'Async mode stored {vectors.count()} vectors of length $VECTOR_LENGTH for {detections.count()} detections')
"
