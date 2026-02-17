#!/usr/bin/env bash
#
# PSv2 Integration Test
#
# Creates a collection + async job on the local Antenna stack,
# starts the ADC worker, streams logs from both sides, and
# monitors for errors.
#
# Usage: ./scripts/psv2_integration_test.sh [NUM_IMAGES]
#
# Requirements:
#   - Antenna stack running (docker compose up -d)
#   - conda env ami-py311 with ami-data-companion installed
#   - .env in ami-data-companion with AMI_ANTENNA_API_AUTH_TOKEN set
#
set -euo pipefail

# --- Config ---
NUM_IMAGES="${1:-20}"
PROJECT_ID=18
PIPELINE_ID=3  # Quebec & Vermont moths
API_BASE="http://localhost:8000/api/v2"
TOKEN="644a0e28e2c09bda87c9ab3f6a002516f3dfb7ff"
ADC_DIR="/home/michael/Projects/AMI/ami-data-companion"
CONDA_BASE="$HOME/miniforge3"
LOG_DIR="/tmp/psv2-integration-test-$(date +%Y%m%d-%H%M%S)"

mkdir -p "$LOG_DIR"

ANTENNA_LOG="$LOG_DIR/antenna.log"
WORKER_LOG="$LOG_DIR/worker.log"
SUMMARY_LOG="$LOG_DIR/summary.log"

# Cleanup function
cleanup() {
    echo ""
    echo "=== Cleaning up ==="
    # Kill background processes
    if [[ -n "${WORKER_PID:-}" ]] && kill -0 "$WORKER_PID" 2>/dev/null; then
        echo "Stopping ADC worker (PID $WORKER_PID)..."
        kill "$WORKER_PID" 2>/dev/null || true
        wait "$WORKER_PID" 2>/dev/null || true
    fi
    if [[ -n "${ANTENNA_LOG_PID:-}" ]] && kill -0 "$ANTENNA_LOG_PID" 2>/dev/null; then
        kill "$ANTENNA_LOG_PID" 2>/dev/null || true
    fi
    echo "Logs saved to: $LOG_DIR"
    echo "  - Antenna logs:  $ANTENNA_LOG"
    echo "  - Worker logs:   $WORKER_LOG"
    echo "  - Register logs: $LOG_DIR/register.log"
    echo "  - Summary:       $SUMMARY_LOG"
}
trap cleanup EXIT

auth_header="Authorization: Token $TOKEN"

api_get() {
    curl -sf -H "$auth_header" "$API_BASE$1"
}

api_post() {
    curl -sf -H "$auth_header" -H "Content-Type: application/json" -X POST "$API_BASE$1" -d "$2"
}

api_post_empty() {
    curl -sf -H "$auth_header" -X POST "$API_BASE$1"
}

log() {
    local msg="[$(date '+%H:%M:%S')] $1"
    echo "$msg"
    echo "$msg" >> "$SUMMARY_LOG"
}

# --- Preflight checks ---
log "PSv2 Integration Test - $NUM_IMAGES images, project $PROJECT_ID, pipeline $PIPELINE_ID"
log "Log directory: $LOG_DIR"
echo ""

echo "Checking Antenna API..."
if ! curl -sf -o /dev/null "$API_BASE/"; then
    echo "ERROR: Antenna API not reachable at $API_BASE"
    echo "Run: docker compose up -d"
    exit 1
fi
echo "  Antenna API: OK"

echo "Checking Docker services..."
DJANGO_STATUS=$(docker compose ps --format json django 2>/dev/null | jq -r '.State // .status' 2>/dev/null || echo "unknown")
CELERY_STATUS=$(docker compose ps --format json celeryworker 2>/dev/null | jq -r '.State // .status' 2>/dev/null || echo "unknown")
NATS_STATUS=$(docker compose ps --format json nats 2>/dev/null | jq -r '.State // .status' 2>/dev/null || echo "unknown")
echo "  django: $DJANGO_STATUS"
echo "  celeryworker: $CELERY_STATUS"
echo "  nats: $NATS_STATUS"

if [[ "$NATS_STATUS" != "running" ]]; then
    echo "WARNING: NATS does not appear to be running. async_api dispatch requires NATS."
fi
echo ""

# --- Step 1: Stream Antenna logs ---
log "Starting Antenna log stream..."
docker compose logs -f django celeryworker nats --since 0s > "$ANTENNA_LOG" 2>&1 &
ANTENNA_LOG_PID=$!

# --- Step 2: Register pipelines with Antenna ---
log "Registering pipelines with Antenna for project $PROJECT_ID..."
REGISTER_LOG="$LOG_DIR/register.log"
(
    source "$CONDA_BASE/etc/profile.d/conda.sh"
    conda activate ami-py311
    cd "$ADC_DIR"
    ami worker register "PSv2 integration test" --project "$PROJECT_ID" 2>&1
) > "$REGISTER_LOG" 2>&1
REGISTER_EXIT=$?

if [[ "$REGISTER_EXIT" -eq 0 ]]; then
    log "Pipeline registration: OK"
else
    log "WARNING: Pipeline registration failed (exit $REGISTER_EXIT)"
    tail -10 "$REGISTER_LOG" | tee -a "$SUMMARY_LOG"
fi
cat "$REGISTER_LOG" >> "$SUMMARY_LOG"

# Verify registration via API
PIPELINES_AFTER=$(api_get "/ml/pipelines/?projects=$PROJECT_ID" | jq '.count')
log "Pipelines available for project $PROJECT_ID: $PIPELINES_AFTER"

# --- Step 3: Start ADC worker ---
# Kill any stale workers from previous test runs to avoid task competition
if pgrep -f "ami worker" > /dev/null 2>&1; then
    log "Killing stale ADC worker processes..."
    pkill -f "ami worker" 2>/dev/null || true
    sleep 2
fi
log "Starting ADC worker..."
(
    source "$CONDA_BASE/etc/profile.d/conda.sh"
    conda activate ami-py311
    cd "$ADC_DIR"
    AMI_NUM_WORKERS=0 ami worker --pipeline quebec_vermont_moths_2023 2>&1
) > "$WORKER_LOG" 2>&1 &
WORKER_PID=$!
sleep 3

if ! kill -0 "$WORKER_PID" 2>/dev/null; then
    log "ERROR: ADC worker failed to start. Check $WORKER_LOG"
    tail -20 "$WORKER_LOG"
    exit 1
fi
log "ADC worker started (PID $WORKER_PID)"

# --- Step 4: Create collection ---
log "Creating collection with $NUM_IMAGES random images..."
COLLECTION_RESP=$(api_post "/captures/collections/" "{
    \"name\": \"PSv2 integration test $(date '+%H:%M:%S')\",
    \"project\": $PROJECT_ID,
    \"method\": \"random\",
    \"kwargs\": {\"size\": $NUM_IMAGES}
}")
COLLECTION_ID=$(echo "$COLLECTION_RESP" | jq -r '.id')
log "Created collection $COLLECTION_ID"

# --- Step 5: Populate collection ---
log "Populating collection $COLLECTION_ID..."
POPULATE_RESP=$(api_post_empty "/captures/collections/$COLLECTION_ID/populate/")
POPULATE_JOB_ID=$(echo "$POPULATE_RESP" | jq -r '.job_id // .id // empty')
log "Populate job: $POPULATE_JOB_ID"

# Wait for population to finish
for i in $(seq 1 30); do
    sleep 2
    COLL_INFO=$(api_get "/captures/collections/$COLLECTION_ID/")
    IMG_COUNT=$(echo "$COLL_INFO" | jq -r '.source_images_count')
    if [[ "$IMG_COUNT" -gt 0 ]]; then
        log "Collection populated: $IMG_COUNT images"
        break
    fi
    if [[ $i -eq 30 ]]; then
        log "ERROR: Collection not populated after 60s"
        exit 1
    fi
done

# --- Step 6: Create and start the ML job ---
log "Creating async ML job..."
JOB_RESP=$(api_post "/jobs/?start_now=true" "{
    \"name\": \"PSv2 integration test $(date '+%H:%M:%S')\",
    \"project_id\": $PROJECT_ID,
    \"pipeline_id\": $PIPELINE_ID,
    \"source_image_collection_id\": $COLLECTION_ID,
    \"delay\": 0,
    \"shuffle\": true
}")
JOB_ID=$(echo "$JOB_RESP" | jq -r '.id')
JOB_STATUS=$(echo "$JOB_RESP" | jq -r '.status')
log "Created job $JOB_ID (status: $JOB_STATUS)"

# --- Step 7: Poll job progress ---
log "Polling job progress..."
PREV_STATUS=""
PREV_PROGRESS=""
POLL_INTERVAL=3
MAX_POLLS=200  # ~10 minutes

for i in $(seq 1 $MAX_POLLS); do
    sleep "$POLL_INTERVAL"

    JOB_INFO=$(api_get "/jobs/$JOB_ID/")
    STATUS=$(echo "$JOB_INFO" | jq -r '.status')
    DISPATCH=$(echo "$JOB_INFO" | jq -r '.dispatch_mode')
    PROGRESS_PCT=$(echo "$JOB_INFO" | jq -r '.progress.summary.progress // 0')
    STAGE_INFO=$(echo "$JOB_INFO" | jq -r '
        [.progress.stages[]? |
         (.params // [] | map({(.key): .value}) | add // {}) as $p |
         "\(.name): \(.progress // 0 | . * 100 | round)% (processed=\($p.processed // "?"), remaining=\($p.remaining // "?"), failed=\($p.failed // "?"))"]
        | join(" | ")')

    # Only print when something changes
    if [[ "$STATUS" != "$PREV_STATUS" || "$PROGRESS_PCT" != "$PREV_PROGRESS" ]]; then
        log "  [$i] status=$STATUS dispatch=$DISPATCH progress=$PROGRESS_PCT $STAGE_INFO"
        PREV_STATUS="$STATUS"
        PREV_PROGRESS="$PROGRESS_PCT"
    fi

    if [[ "$STATUS" == "SUCCESS" || "$STATUS" == "FAILURE" || "$STATUS" == "REVOKED" ]]; then
        break
    fi

    # Check worker is still alive
    if ! kill -0 "$WORKER_PID" 2>/dev/null; then
        log "WARNING: ADC worker died during job processing!"
        log "Last 20 lines of worker log:"
        tail -20 "$WORKER_LOG" | tee -a "$SUMMARY_LOG"
    fi
done

# --- Step 8: Final job state ---
echo ""
JOB_FINAL=$(api_get "/jobs/$JOB_ID/")
FINAL_STATUS=$(echo "$JOB_FINAL" | jq -r '.status')
FINAL_DISPATCH=$(echo "$JOB_FINAL" | jq -r '.dispatch_mode')
STARTED_AT=$(echo "$JOB_FINAL" | jq -r '.started_at // "N/A"')
FINISHED_AT=$(echo "$JOB_FINAL" | jq -r '.finished_at // "N/A"')

log "=== Job $JOB_ID Final State ==="
log "  Status: $FINAL_STATUS"
log "  Dispatch: $FINAL_DISPATCH"
log "  Started: $STARTED_AT"
log "  Finished: $FINISHED_AT"

# Print stage details
echo "$JOB_FINAL" | jq -r '.progress.stages[]? | (.params // [] | map({(.key): .value}) | add // {}) as $p | "  Stage \(.name): progress=\(.progress // 0 | . * 100 | round)% processed=\($p.processed // "?") remaining=\($p.remaining // "?") failed=\($p.failed // "?")"' | while read -r line; do
    log "$line"
done

# --- Step 9: Scan logs for errors ---
echo ""
log "=== Log Analysis ==="

ANTENNA_ERRORS=$(grep -ciE 'ERROR|Traceback|CRITICAL' "$ANTENNA_LOG" 2>/dev/null || echo 0)
ANTENNA_WARNINGS=$(grep -ciE 'WARNING' "$ANTENNA_LOG" 2>/dev/null || echo 0)
WORKER_ERRORS=$(grep -ciE 'ERROR|Traceback|CRITICAL' "$WORKER_LOG" 2>/dev/null || echo 0)
WORKER_WARNINGS=$(grep -ciE 'WARNING' "$WORKER_LOG" 2>/dev/null || echo 0)

log "Antenna logs: $ANTENNA_ERRORS errors, $ANTENNA_WARNINGS warnings"
log "Worker logs:  $WORKER_ERRORS errors, $WORKER_WARNINGS warnings"

if [[ "$ANTENNA_ERRORS" -gt 0 ]]; then
    echo ""
    log "--- Antenna Errors ---"
    grep -iE 'ERROR|Traceback|CRITICAL' "$ANTENNA_LOG" | grep -v "NoSuchKey\|image dimensions" | head -30 | tee -a "$SUMMARY_LOG"
fi

if [[ "$WORKER_ERRORS" -gt 0 ]]; then
    echo ""
    log "--- Worker Errors ---"
    grep -iE 'ERROR|Traceback|CRITICAL' "$WORKER_LOG" | head -30 | tee -a "$SUMMARY_LOG"
fi

# --- Step 10: Final verdict ---
echo ""
if [[ "$FINAL_STATUS" == "SUCCESS" && "$WORKER_ERRORS" -eq 0 ]]; then
    log "RESULT: PASS - Job completed successfully with no worker errors"
    exit 0
elif [[ "$FINAL_STATUS" == "SUCCESS" ]]; then
    log "RESULT: WARN - Job completed but worker had $WORKER_ERRORS errors (check logs)"
    exit 0
else
    log "RESULT: FAIL - Job status: $FINAL_STATUS"
    exit 1
fi
