#!/bin/bash
# Container entrypoint. Dispatches one of three modes via the MODE env var:
#
#   MODE=api          FastAPI server only (default; CI uses this for existing /process tests)
#   MODE=worker       Poll loop only (register.py runs once, then worker_main.py polls)
#   MODE=api+worker   FastAPI + register.py + worker loop (local dev default; exercises both v1 and v2)
#
# See docs/claude/planning/2026-04-17-minimal-worker-design.md for the rationale.

set -e

MODE="${MODE:-api}"

# Signal forwarding so compose can stop us cleanly.
PIDS=()
cleanup() {
    for pid in "${PIDS[@]}"; do
        kill -TERM "$pid" 2>/dev/null || true
    done
    wait "${PIDS[@]}" 2>/dev/null || true
}
trap cleanup TERM INT

start_api() {
    echo "[start.sh] Starting FastAPI server (MODE=$MODE)"
    python /app/main.py &
    PIDS+=("$!")
}

start_register() {
    # register.py imports pipelines from the api module directly (no HTTP to
    # self), self-provisions a ProcessingService, and registers pipelines
    # with Antenna. Its retry loop handles "Antenna not up yet".
    # Skip if registration env vars aren't set — the container still works
    # as a pure v1 push service without them.
    if [ -z "${ANTENNA_API_URL:-}" ]; then
        echo "[start.sh] Skipping registration (ANTENNA_API_URL not set)"
        return
    fi
    if [ -z "${ANTENNA_PROJECT_ID:-}" ] && [ -z "${ANTENNA_DEFAULT_PROJECT_NAME:-}" ]; then
        echo "[start.sh] Skipping registration (no ANTENNA_PROJECT_ID or ANTENNA_DEFAULT_PROJECT_NAME)"
        return
    fi
    echo "[start.sh] Running registration"
    python /app/register.py || echo "[start.sh] Registration failed, continuing"
}

start_worker() {
    echo "[start.sh] Starting worker poll loop"
    python /app/worker_main.py &
    PIDS+=("$!")
}

case "$MODE" in
    api)
        start_api
        ;;
    worker)
        start_register
        start_worker
        ;;
    api+worker)
        # FastAPI first so /process is available even while register.py is
        # still retrying against a not-yet-ready Antenna. register.py doesn't
        # depend on FastAPI (imports pipeline configs directly), so there's
        # no startup race here.
        start_api
        start_register
        start_worker
        ;;
    *)
        echo "[start.sh] Unknown MODE: $MODE (expected: api | worker | api+worker)" >&2
        exit 2
        ;;
esac

# Block on any child; if any exits, cleanup and exit so compose restarts us.
wait -n "${PIDS[@]}"
cleanup
