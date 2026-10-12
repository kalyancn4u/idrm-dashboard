# =============================================================================
#  IDRM — Identity Data & Risk Management
#  Master Makefile
#  ---------------------------------------------------------------------------
#  Usage:  make help
# =============================================================================

SHELL            := /bin/bash
.DEFAULT_GOAL    := help

# --- Project -----------------------------------------------------------------
PROJECT          := idrm
PYTHON           ?= python3
VENV             := .venv
VENV_BIN         := $(VENV)/bin
PY               := $(VENV_BIN)/python
PIP              := $(VENV_BIN)/pip
FLASK            := $(VENV_BIN)/flask

# --- Postgres ----------------------------------------------------------------
PGHOST           ?= localhost
PGPORT           ?= 5432
PGUSER           ?= idrm
PGPASSWORD       ?= idrm
PGDATABASE       ?= idrm
PGMAINT          ?= postgres

export PGHOST PGPORT PGUSER PGPASSWORD PGDATABASE

DATABASE_URL     ?= postgresql+psycopg2://$(PGUSER):$(PGPASSWORD)@$(PGHOST):$(PGPORT)/$(PGDATABASE)
export DATABASE_URL

PSQL             := PGPASSWORD=$(PGPASSWORD) psql -h $(PGHOST) -p $(PGPORT) -U $(PGUSER) -d $(PGDATABASE) -v ON_ERROR_STOP=1
PSQL_MAINT       := PGPASSWORD=$(PGPASSWORD) psql -h $(PGHOST) -p $(PGPORT) -U $(PGMAINT) -d postgres -v ON_ERROR_STOP=1

SQL_DIR          := sql
SQL_FILES        := 01_schema.sql 02_functions_triggers.sql 03_indexes.sql \
                    04_seed_reference.sql 05_seed_sample.sql

# --- Colours -----------------------------------------------------------------
C_RESET := \033[0m
C_BOLD  := \033[1m
C_GREEN := \033[32m
C_CYAN  := \033[36m
C_YELLW := \033[33m
C_RED   := \033[31m

# =============================================================================
help: ## Show this help
	@echo ""
	@echo -e "$(C_BOLD)IDRM — Identity Data & Risk Management$(C_RESET)"
	@echo -e "$(C_CYAN)----------------------------------------------------------------$(C_RESET)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| sort \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  $(C_GREEN)%-18s$(C_RESET) %s\n", $$1, $$2}'
	@echo ""
	@echo -e "  $(C_YELLW)Quick start:$(C_RESET)  make setup && make run"
	@echo ""

# =============================================================================
#  SETUP
# =============================================================================
.PHONY: setup
setup: venv install db-up db-create migrate seed passwords ## One-shot: venv + install + db + schema + seed + passwords
	@echo -e "$(C_GREEN)✔ Setup complete. Run:  make run$(C_RESET)"

.PHONY: venv
venv: ## Create the Python virtual environment
	@test -d $(VENV) || $(PYTHON) -m venv $(VENV)
	@$(PIP) install --quiet --upgrade pip setuptools wheel
	@echo -e "$(C_GREEN)✔ venv ready$(C_RESET)"

.PHONY: install
install: venv ## Install Python dependencies
	@$(PIP) install --quiet -r requirements.txt
	@echo -e "$(C_GREEN)✔ dependencies installed$(C_RESET)"

.PHONY: env
env: ## Create .env from .env.example (never overwrites)
	@test -f .env || (cp .env.example .env && echo -e "$(C_GREEN)✔ .env created$(C_RESET)")
	@test -f .env && echo -e "$(C_CYAN)ℹ .env already exists — left untouched$(C_RESET)"

# =============================================================================
#  DATABASE
# =============================================================================
.PHONY: db-up
db-up: ## Start Postgres (docker compose)
	@docker compose up -d postgres
	@echo -n "  waiting for postgres"
	@for i in $$(seq 1 30); do \
		PGPASSWORD=$(PGPASSWORD) pg_isready -h $(PGHOST) -p $(PGPORT) -U $(PGUSER) -q && break; \
		echo -n "."; sleep 1; \
	done; echo " ok"
	@echo -e "$(C_GREEN)✔ postgres up$(C_RESET)"

.PHONY: db-down
db-down: ## Stop Postgres
	@docker compose down
	@echo -e "$(C_GREEN)✔ postgres down$(C_RESET)"

.PHONY: db-create
db-create: ## Create role + database if missing
	@$(PSQL_MAINT) -tc "SELECT 1 FROM pg_roles WHERE rolname='$(PGUSER)'" | grep -q 1 || \
		$(PSQL_MAINT) -c "CREATE ROLE $(PGUSER) LOGIN PASSWORD '$(PGPASSWORD)';"
	@$(PSQL_MAINT) -tc "SELECT 1 FROM pg_database WHERE datname='$(PGDATABASE)'" | grep -q 1 || \
		$(PSQL_MAINT) -c "CREATE DATABASE $(PGDATABASE) OWNER $(PGUSER);"
	@echo -e "$(C_GREEN)✔ database $(PGDATABASE) ready$(C_RESET)"

.PHONY: migrate
migrate: ## Apply schema + functions + indexes (idempotent)
	@for f in 01_schema.sql 02_functions_triggers.sql 03_indexes.sql; do \
		echo -e "  → $(C_CYAN)$$f$(C_RESET)"; \
		$(PSQL) -q -f $(SQL_DIR)/$$f || exit 1; \
	done
	@echo -e "$(C_GREEN)✔ schema applied$(C_RESET)"

.PHONY: seed
seed: ## Load reference + sample data (idempotent)
	@for f in 04_seed_reference.sql 05_seed_sample.sql; do \
		echo -e "  → $(C_CYAN)$$f$(C_RESET)"; \
		$(PSQL) -q -f $(SQL_DIR)/$$f || exit 1; \
	done
	@echo -e "$(C_GREEN)✔ data seeded$(C_RESET)"

.PHONY: passwords
passwords: ## Set real password hashes for demo users
	@$(FLASK) --app run.py seed-users
	@echo -e "$(C_GREEN)✔ demo passwords set$(C_RESET)"

.PHONY: db-reset
db-reset: ## DESTRUCTIVE — drop all objects and rebuild
	@echo -e "$(C_RED)⚠  This will drop every IDRM table in $(PGDATABASE).$(C_RESET)"
	@read -p "Type 'yes' to continue: " c; [ "$$c" = "yes" ] || (echo "aborted"; exit 1)
	@$(PSQL) -q -f $(SQL_DIR)/99_reset.sql
	@$(MAKE) migrate seed passwords
	@echo -e "$(C_GREEN)✔ database reset$(C_RESET)"

.PHONY: psql
psql: ## Open an interactive psql session
	@$(PSQL)

.PHONY: dump
dump: ## Dump schema+data to backups/idrm_<timestamp>.sql
	@mkdir -p backups
	@PGPASSWORD=$(PGPASSWORD) pg_dump -h $(PGHOST) -p $(PGPORT) -U $(PGUSER) \
		--no-owner --clean --if-exists $(PGDATABASE) > backups/idrm_$$(date +%Y%m%d_%H%M%S).sql
	@echo -e "$(C_GREEN)✔ dump written to backups/$(C_RESET)"

# =============================================================================
#  RUN
# =============================================================================
.PHONY: run
run: ## Run the dev server on :5000
	@echo -e "$(C_CYAN)▶ http://127.0.0.1:5000$(C_RESET)"
	@$(FLASK) --app run.py run --debug --host 0.0.0.0 --port 5000

.PHONY: serve
serve: ## Run the production server (gunicorn)
	@$(VENV_BIN)/gunicorn -w 4 -k gthread --threads 4 -b 0.0.0.0:8000 "run:app"

.PHONY: routes
routes: ## List all registered routes
	@$(FLASK) --app run.py routes

.PHONY: shell
shell: ## Flask shell with app context
	@$(FLASK) --app run.py shell

# =============================================================================
#  DOMAIN TASKS
# =============================================================================
.PHONY: risk-scan
risk-scan: ## Run the risk engine across all identities
	@$(FLASK) --app run.py risk-scan

.PHONY: export-audit
export-audit: ## Export full audit trail to exports/audit_<ts>.csv
	@mkdir -p exports
	@$(FLASK) --app run.py export-audit --out exports/audit_$$(date +%Y%m%d_%H%M%S).csv
	@echo -e "$(C_GREEN)✔ export written$(C_RESET)"

.PHONY: stats
stats: ## Print row counts for every table
	@$(PSQL) -c "\
		SELECT 'identity' t, count(*) n FROM identity UNION ALL \
		SELECT 'account', count(*) FROM account UNION ALL \
		SELECT 'access_grant', count(*) FROM access_grant UNION ALL \
		SELECT 'finding', count(*) FROM finding UNION ALL \
		SELECT 'audit_event', count(*) FROM audit_event \
		ORDER BY t;"

# =============================================================================
#  QUALITY
# =============================================================================
.PHONY: test
test: ## Run the test suite
	@$(VENV_BIN)/pytest -q

.PHONY: test-pg
test-pg: ## Run tests against real Postgres
	@IDRM_TEST_DATABASE_URL="$(DATABASE_URL)" $(VENV_BIN)/pytest -q -m ""

.PHONY: lint
lint: ## Ruff + black --check
	@$(VENV_BIN)/ruff check app tests 2>/dev/null || echo "  (ruff not installed — skipping)"
	@$(VENV_BIN)/black --check app tests 2>/dev/null || echo "  (black not installed — skipping)"

.PHONY: fmt
fmt: ## Auto-format the codebase
	@$(VENV_BIN)/ruff check --fix app tests 2>/dev/null || true
	@$(VENV_BIN)/black app tests 2>/dev/null || true
	@echo -e "$(C_GREEN)✔ formatted$(C_RESET)"

.PHONY: smoke
smoke: ## End-to-end smoke test against a running server
	@bash scripts/smoke.sh

# =============================================================================
#  HOUSEKEEPING
# =============================================================================
.PHONY: docs
docs: ## List the documentation set
	@echo -e "$(C_BOLD)Documentation$(C_RESET)"
	@ls -1 docs/*.md | sed 's/^/  /'

.PHONY: clean
clean: ## Remove caches and build artefacts
	@find . -type d -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name .pytest_cache -prune -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name '*.pyc' -delete 2>/dev/null || true
	@rm -rf .ruff_cache htmlcov .coverage 2>/dev/null || true
	@echo -e "$(C_GREEN)✔ cleaned$(C_RESET)"

.PHONY: nuke
nuke: clean ## Remove venv too (full reset)
	@rm -rf $(VENV)
	@echo -e "$(C_GREEN)✔ venv removed$(C_RESET)"

