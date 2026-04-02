#!/usr/bin/env bash
# Smoke test — verify the API is reachable and responding.
# Usage: ./scripts/smoke_test.sh [--full] [base_url]
#
# Without --full: checks health + state + events + agent-messages endpoints.
# With --full:    also seeds state, triggers er-admission, and verifies completion.

set -euo pipefail

FULL_MODE=false

# Parse arguments
for arg in "$@"; do
  case "$arg" in
    --full)
      FULL_MODE=true
      shift
      ;;
  esac
done

BASE_URL="${1:-http://localhost:8000}"
FAILED=0

check_endpoint() {
  local path="$1"
  local url="${BASE_URL}${path}"
  echo "==> GET ${url}"
  HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "${url}")
  if [ "$HTTP_CODE" -eq 200 ]; then
    echo "    ✅ ${path} returned 200 OK"
  else
    echo "    ❌ ${path} returned HTTP ${HTTP_CODE}"
    FAILED=1
  fi
}

echo "── Basic endpoint checks ──"
check_endpoint "/health"
check_endpoint "/api/state"
check_endpoint "/api/events"
check_endpoint "/api/agent-messages"

if [ "$FULL_MODE" = true ]; then
  echo ""
  echo "── Full scenario check (er-admission) ──"

  # Seed state
  echo "==> POST ${BASE_URL}/api/scenario/seed"
  SEED_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 -X POST "${BASE_URL}/api/scenario/seed")
  if [ "$SEED_CODE" -eq 200 ]; then
    echo "    ✅ Seed returned 200"
  else
    echo "    ❌ Seed returned HTTP ${SEED_CODE}"
    FAILED=1
  fi

  # Trigger er-admission
  echo "==> POST ${BASE_URL}/api/scenario/er-admission"
  HP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 -X POST "${BASE_URL}/api/scenario/er-admission")
  if [ "$HP_CODE" -eq 202 ]; then
    echo "    ✅ ER-admission returned 202 Accepted"
  else
    echo "    ❌ ER-admission returned HTTP ${HP_CODE}"
    FAILED=1
  fi

  # Poll for PlacementComplete event (timeout after 30 seconds)
  echo "==> Waiting for scenario completion..."
  TIMEOUT=30
  ELAPSED=0
  COMPLETED=false
  while [ "$ELAPSED" -lt "$TIMEOUT" ]; do
    EVENTS=$(curl -s --max-time 5 "${BASE_URL}/api/events")
    if echo "$EVENTS" | grep -q "PlacementComplete"; then
      COMPLETED=true
      break
    fi
    sleep 2
    ELAPSED=$((ELAPSED + 2))
  done

  if [ "$COMPLETED" = true ]; then
    echo "    ✅ PlacementComplete event detected"
  else
    echo "    ❌ PlacementComplete not found within ${TIMEOUT}s"
    FAILED=1
  fi

  # Verify agent messages were generated
  echo "==> GET ${BASE_URL}/api/agent-messages"
  MSG_COUNT=$(curl -s --max-time 5 "${BASE_URL}/api/agent-messages" | python3 -c "import sys,json; print(len(json.load(sys.stdin)))" 2>/dev/null || echo "0")
  if [ "$MSG_COUNT" -ge 10 ]; then
    echo "    ✅ ${MSG_COUNT} agent messages generated"
  else
    echo "    ❌ Only ${MSG_COUNT} agent messages (expected ≥10)"
    FAILED=1
  fi
fi

echo ""
if [ "$FAILED" -ne 0 ]; then
  echo "❌ Smoke test FAILED — one or more checks did not pass."
  exit 1
fi

echo "✅ All smoke tests passed."
exit 0
