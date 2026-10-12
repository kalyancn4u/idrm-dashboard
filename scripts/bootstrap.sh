#!/usr/bin/env bash
# =============================================================================
#  IDRM — one-shot bootstrap
#  Usage:  bash scripts/bootstrap.sh
# =============================================================================
set -euo pipefail

BOLD=$'\033[1m'; GREEN=$'\033[32m'; CYAN=$'\033[36m'; RED=$'\033[31m'; RESET=$'\033[0m'

step() { echo -e "${CYAN}▶ $*${RESET}"; }
ok()   { echo -e "${GREEN}✔ $*${RESET}"; }
die()  { echo -e "${RED}✖ $*${RESET}" >&2; exit 1; }

cd "$(dirname "$0")/.."

step "Checking prerequisites"
command -v python3 >/dev/null || die "python3 is required"
command -v docker  >/dev/null || echo "  (docker not found — you will need a local Postgres)"

step "Creating .env"
make env

step "Creating virtualenv and installing dependencies"
make install

step "Starting Postgres"
if command -v docker >/dev/null 2>&1; then
  make db-up || echo "  (docker compose failed — assuming an external Postgres)"
else
  echo "  skipped"
fi

step "Creating database"
make db-create

step "Applying schema"
make migrate

step "Seeding data"
make seed

step "Setting demo passwords"
make passwords

echo
ok "Bootstrap complete."
echo
echo -e "${BOLD}Next:${RESET}"
echo "    make run"
echo "    open http://127.0.0.1:5000"
echo
echo -e "${BOLD}Demo logins${RESET}"
echo "    admin   / Admin#2025      (full control)"
echo "    auditor / Audit#2025      (read-only assurance)"
echo "    analyst / Analyze#2025    (investigate + remediate)"
echo "    viewer  / View#2025       (dashboards only)"
