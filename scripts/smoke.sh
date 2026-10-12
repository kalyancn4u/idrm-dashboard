#!/usr/bin/env bash
# =============================================================================
#  IDRM — smoke test
#  Requires the app to be running on BASE_URL (default http://127.0.0.1:5000).
# =============================================================================
set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:5000}"
PASS=0; FAIL=0
GREEN=$'\033[32m'; RED=$'\033[31m'; CYAN=$'\033[36m'; RESET=$'\033[0m'

check() {
  local label="$1" expected="$2" actual="$3"
  if [[ "$actual" == "$expected" ]]; then
    echo -e "  ${GREEN}✔${RESET} $label ($actual)"
    PASS=$((PASS+1))
  else
    echo -e "  ${RED}✖${RESET} $label (expected $expected, got $actual)"
    FAIL=$((FAIL+1))
  fi
}

echo -e "${CYAN}IDRM smoke test → $BASE_URL${RESET}"
echo

echo "Public endpoints"
check "GET /healthz"          200 "$(curl -s -o /dev/null -w '%{http_code}' "$BASE_URL/healthz")"
check "GET /api/v1/health"    200 "$(curl -s -o /dev/null -w '%{http_code}' "$BASE_URL/api/v1/health")"
check "GET /auth/login"       200 "$(curl -s -o /dev/null -w '%{http_code}' "$BASE_URL/auth/login")"

echo
echo "Auth-gated endpoints (expect redirect to login)"
check "GET /admin/  (anon)"        302 "$(curl -s -o /dev/null -w '%{http_code}' "$BASE_URL/admin/")"
check "GET /auditor/ (anon)"       302 "$(curl -s -o /dev/null -w '%{http_code}' "$BASE_URL/auditor/")"
check "GET /api/v1/kpis (anon)"    302 "$(curl -s -o /dev/null -w '%{http_code}' "$BASE_URL/api/v1/kpis")"

echo
echo -e "${CYAN}Result: ${GREEN}${PASS} passed${RESET}, ${RED}${FAIL} failed${RESET}"
[[ "$FAIL" -eq 0 ]] || exit 1
