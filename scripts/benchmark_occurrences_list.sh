#!/usr/bin/env bash
# Benchmark the /api/v2/occurrences/ list endpoint under concurrent load.
#
# Used to A/B compare a deployment with PR #1274 (occurrence list N+1 fix)
# against a baseline. Each request uses a randomized offset to bypass
# django-cachalot. Reports avg / p50 / p95 / p99 / max plus error counts.
#
# Usage:
#   ./scripts/benchmark_occurrences_list.sh <base_url> <project_id> <concurrency> <total> <limit>
#
# Example (prod):
#   ./scripts/benchmark_occurrences_list.sh https://api.antenna.insectai.org 18 10 30 25
#
# Example (staging A/B):
#   ./scripts/benchmark_occurrences_list.sh https://arctia.dev.antenna.insectai.org 5 10 30 25
#   ./scripts/benchmark_occurrences_list.sh https://serbia.dev.antenna.insectai.org 5 10 30 25

set -euo pipefail

BASE_URL="${1:?base_url required, e.g. https://api.antenna.insectai.org}"
PROJECT_ID="${2:?project_id required}"
CONCURRENCY="${3:-10}"
TOTAL="${4:-30}"
LIMIT="${5:-25}"

# Probe project size so the random offset stays within the dataset
COUNT=$(curl -s "${BASE_URL}/api/v2/occurrences/?project_id=${PROJECT_ID}&limit=1" | jq -r '.count')
if [[ -z "${COUNT}" || "${COUNT}" == "null" ]]; then
  echo "Failed to probe occurrence count at ${BASE_URL} project ${PROJECT_ID}" >&2
  exit 1
fi
MAX_OFFSET=$(( COUNT > LIMIT ? COUNT - LIMIT : 0 ))

OUT=$(mktemp)
trap 'rm -f "${OUT}"' EXIT

echo "Benchmark: ${BASE_URL} project=${PROJECT_ID} count=${COUNT} concurrency=${CONCURRENCY} total=${TOTAL} limit=${LIMIT}"

START=$(date +%s.%N)
seq 1 "${TOTAL}" | xargs -n1 -P"${CONCURRENCY}" -I{} bash -c "
  offset=\$(( RANDOM % ${MAX_OFFSET} ))
  curl -s -o /dev/null -w '%{http_code} %{time_total}\n' \
    '${BASE_URL}/api/v2/occurrences/?project_id=${PROJECT_ID}&limit=${LIMIT}&offset='\${offset}
" > "${OUT}"
END=$(date +%s.%N)
WALL=$(awk "BEGIN {printf \"%.3f\", ${END} - ${START}}")

ERRS=$(awk '$1!=200{print}' "${OUT}" | wc -l | tr -d ' ')
ERR_CODES=$(awk '$1!=200{print $1}' "${OUT}" | sort | uniq -c | tr '\n' ' ')

OK_TIMES=$(awk '$1==200{print $2}' "${OUT}" | sort -n)
OK_COUNT=$(echo "${OK_TIMES}" | grep -c . || echo 0)

if [[ "${OK_COUNT}" -eq 0 ]]; then
  echo "wall=${WALL}s errors=${ERRS}/${TOTAL} (${ERR_CODES})"
  exit 1
fi

P50=$(echo "${OK_TIMES}" | awk -v n="${OK_COUNT}" 'NR==int(n*0.5)+1 {printf "%.3f", $1}')
P95=$(echo "${OK_TIMES}" | awk -v n="${OK_COUNT}" 'NR==int(n*0.95) {printf "%.3f", $1}')
P99=$(echo "${OK_TIMES}" | awk -v n="${OK_COUNT}" 'NR==int(n*0.99) {printf "%.3f", $1}')
AVG=$(echo "${OK_TIMES}" | awk '{s+=$1} END{printf "%.3f", s/NR}')
MIN=$(echo "${OK_TIMES}" | head -1 | awk '{printf "%.3f", $1}')
MAX=$(echo "${OK_TIMES}" | tail -1 | awk '{printf "%.3f", $1}')

echo "wall=${WALL}s avg=${AVG}s min=${MIN}s p50=${P50}s p95=${P95}s p99=${P99}s max=${MAX}s errors=${ERRS}/${TOTAL} (${ERR_CODES:-none})"
