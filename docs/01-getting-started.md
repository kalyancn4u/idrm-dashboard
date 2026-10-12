# Getting Started

A complete beginner can go from zero to a running IDRM in about ten minutes.

## 1. What you are about to build

A web application with two consoles:

- **Admin mode** — an operator who manages identities, access and risk findings.
- **Auditor mode** — an auditor who inspects the same data without being able to change it.

Everything lives in PostgreSQL. A sample dataset ships with the repo so the
screens are populated the moment you log in.

## 2. Prerequisites

| Requirement | Why | Check |
|---|---|---|
| Python 3.11+ | Runs the Flask app | `python3 --version` |
| Docker (recommended) | Runs Postgres in one command | `docker --version` |
| **or** PostgreSQL 14+ | If you'd rather install it natively | `psql --version` |
| GNU Make | Drives every task | `make --version` |
| `curl` | Smoke test | `curl --version` |

**No Python knowledge is required to run it.** You only need it to modify the code.

## 3. Install — the one-command path

```bash
git clone <your-repo-url> idrm
cd idrm
bash scripts/bootstrap.sh
```

`bootstrap.sh` performs, in order:

1. Creates `.env` from `.env.example`
2. Creates `.venv/` and installs Python dependencies
3. Starts Postgres via `docker compose up -d postgres`
4. Creates the `idrm` role and database
5. Applies `sql/01_schema.sql`, `02_functions_triggers.sql`, `03_indexes.sql`
6. Loads `sql/04_seed_reference.sql` and `sql/05_seed_sample.sql`
7. Sets real password hashes for the four demo users

## 4. Install — the manual path

```bash
make env          # .env
make venv         # .venv/
make install      # pip install -r requirements.txt
make db-up        # docker compose up -d postgres
make db-create    # CREATE ROLE + CREATE DATABASE
make migrate      # schema + functions + indexes
make seed         # reference + sample data
make passwords    # set demo password hashes
```

## 5. Run it

```bash
make run
```

Open **http://127.0.0.1:5000**.

## 6. Log in

| Mode | Username | Password | What you can do |
|---|---|---|---|
| **Admin** | `admin` | `Admin#2025` | Everything |
| **Auditor** | `auditor` | `Audit#2025` | Read + export |
| **Analyst** | `analyst` | `Analyze#2025` | Investigate + remediate findings |
| **Viewer** | `viewer` | `View#2025` | Dashboards only |

> **Tip:** log in as `admin`, look at the dashboard, then log out and log in as
> `auditor`. The navigation changes and every mutation button disappears.

## 7. What to look at first

### As Admin

1. **Overview** — KPI cards, the last scan, the active certification campaign.
2. **Identities** → sort by *Risk score*. Click one.
   You'll see its accounts, grants, findings and an activity timeline.
3. **Findings** → open one. Read the evidence. Change its status.
4. **Access Grants** → filter *privileged only*. Revoke something.
5. **Certifications** → approve or revoke a review item.

### As Auditor

1. **Overview** — the same numbers, minus every action button.
2. **Findings** → open one. Note the *Full Change History* section.
3. **Audit Trail** → filter by entity `finding`. This is the immutable log.
4. **Exports** → download `findings.csv`. Now check the Audit Trail for an
   `EXPORT` event. Your download was recorded.

## 8. Make the data move

```bash
make risk-scan
```

The engine re-evaluates every risk rule. Watch the "Findings created" number on
the admin dashboard change.

## 9. Reset to a clean slate

```bash
make db-reset     # asks for confirmation
```

## 10. Common next steps

| I want to… | Command |
|---|---|
| See every route | `make routes` |
| Open a SQL prompt | `make psql` |
| Run the tests | `make test` |
| Export the audit trail | `make export-audit` |
| See table row counts | `make stats` |
| Dump the database | `make dump` |
| Get help | `make help` |

## 11. Where things live

```
sql/                ← the database, in plain SQL (readable by a DBA)
app/models/         ← Python classes that mirror those tables
app/services/       ← business logic (risk engine, reporting, audit)
app/blueprints/     ← URL routes
app/templates/      ← HTML
app/static/css/     ← the design system
docs/               ← you are here
```

## 12. Next

→ [Architecture (HLD)](02-architecture-hld.md)

