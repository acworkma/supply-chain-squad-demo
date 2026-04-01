#!/usr/bin/env bash
# Smoke test for the Supply Chain Management API.
# Usage: scripts/smoke_test.sh [BASE_URL]

set -euo pipefail

BASE_URL="${1:-http://localhost:8000}"

echo "🔍 Running smoke test against: $BASE_URL"

# Health check
echo -n "  /health ... "
STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/health")
if [[ "$STATUS" == "200" ]]; then
  echo "✅ $STATUS"
else
  echo "❌ $STATUS"
  exit 1
fi

# Config endpoint
echo -n "  /api/config ... "
STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/api/config")
if [[ "$STATUS" == "200" ]]; then
  echo "✅ $STATUS"
else
  echo "❌ $STATUS"
  exit 1
fi

# Metrics endpoint (empty state returns 200)
echo -n "  /api/metrics ... "
STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/api/metrics")
if [[ "$STATUS" == "200" ]]; then
  echo "✅ $STATUS"
else
  echo "❌ $STATUS"
  exit 1
fi

echo ""
echo "✅ All smoke tests passed!"
