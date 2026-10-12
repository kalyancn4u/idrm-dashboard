# IDRM — Identity Data & Risk Management

> A self-contained reference implementation of an identity-risk platform with
> **two operator consoles** — an **Admin** mode that fixes things and an
> **Auditor** mode that proves things — built on **Flask**, **PostgreSQL**, and a
> **Slate + Emerald, WCAG AAA** design system.

---

## Table of contents

1. [What is this?](#1-what-is-this)
2. [Screens at a glance](#2-screens-at-a-glance)
3. [Quick start](#3-quick-start)
4. [Repository map](#4-repository-map)
5. [The data model in one picture](#5-the-data-model-in-one-picture)
6. [How a risk finding is born](#6-how-a-risk-finding-is-born)
7. [Databases](#7-databases)
8. [Make targets](#8-make-targets)
9. [Documentation map](#9-documentation-map)
10. [Design system](#10-design-system)
11. [Security](#11-security)
12. [Testing](#12-testing)
13. [Troubleshooting](#13-troubleshooting)
14. [License](#14-license)

---

## 1. What is this?

IDRM answers three questions about identity risk, and makes each answer *provable*:

| Question | Where it lives |
|---|---|
| **Who has access to what?** | `identity` → `account` → `access_grant` → `entitlement` |
| **What's wrong with that access?** | `risk_rule` fires → `finding` is raised |
| **Can you prove it?** | `audit_event` — append-only, tamper-evident, forever |

Two consoles read the same data with different powers:

| Mode | Route | Who | Can |
|---|---|---|---|
| **Admin** | `/admin/` | IAM engineers, analysts | Everything: remediate, revoke, certify, scan |
| **Auditor** | `/auditor/` | Internal audit, external audit, compliance | Read, filter, export. **No writes, ever.** |

The auditor's read-only guarantee is *structural*, not a UI convention: a separate
blueprint, hard `@roles_required` decorators, and a `SELECT`-only database role.

## 1.1. Folder Structure

```
idrm/
├── Makefile                          # ← master orchestrator (start here)
├── README.md                         # ← you are here
├── requirements.txt
├── .env.example
├── .gitignore
├── pytest.ini
├── docker-compose.yml
├── Dockerfile
├── run.py                            # Flask entrypoint (app factory)
│
├── sql/
│   ├── 01_schema.sql                 # tables, constraints, comments
│   ├── 02_functions_triggers.sql     # audit triggers, risk scoring, immutability
│   ├── 03_indexes.sql                # performance indexes + partial indexes
│   ├── 04_seed_reference.sql         # systems, entitlements, risk rules, SoD rules
│   ├── 05_seed_sample.sql            # identities, accounts, grants, findings, campaigns
│   └── 99_reset.sql                  # drop everything (destructive)
│
├── app/
│   ├── __init__.py                   # create_app() factory
│   ├── config.py                     # Dev / Test / Prod config objects
│   ├── extensions.py                 # db, login_manager, csrf, cache
│   ├── cli.py                        # flask init-db / seed-users / risk-scan
│   ├── models/
│   │   ├── __init__.py
│   │   ├── user.py
│   │   ├── identity.py
│   │   ├── system_app.py
│   │   ├── account.py
│   │   ├── entitlement.py
│   │   ├── grant.py
│   │   ├── risk.py                   # risk_rule, sod_rule, finding, evidence
│   │   ├── review.py
│   │   └── audit.py
│   ├── security/
│   │   ├── __init__.py
│   │   ├── rbac.py                   # role → permission matrix
│   │   └── decorators.py             # @roles_required, @admin_required …
│   ├── services/
│   │   ├── __init__.py
│   │   ├── audit_service.py          # log_event(), actor context
│   │   ├── risk_engine.py            # rule evaluation, scoring, scan runner
│   │   └── reporting.py              # KPI aggregation, CSV builders
│   ├── blueprints/
│   │   ├── __init__.py
│   │   ├── auth.py                   # /login /logout
│   │   ├── main.py                   # / , /healthz , /dashboard router
│   │   ├── admin.py                  # /admin/…
│   │   ├── auditor.py                # /auditor/…
│   │   └── api.py                    # /api/v1/…
│   ├── templates/
│   │   ├── base.html
│   │   ├── components/
│   │   │   ├── _macros.html          # kpi, badge, alert, empty_state, pager
│   │   │   ├── _sidebar.html
│   │   │   └── _topbar.html
│   │   ├── auth/login.html
│   │   ├── admin/
│   │   │   ├── dashboard.html
│   │   │   ├── identities.html
│   │   │   ├── identity_detail.html
│   │   │   ├── findings.html
│   │   │   ├── finding_detail.html
│   │   │   ├── grants.html
│   │   │   └── reviews.html
│   │   ├── auditor/
│   │   │   ├── dashboard.html
│   │   │   ├── findings.html
│   │   │   ├── finding_detail.html
│   │   │   ├── audit_trail.html
│   │   │   ├── campaigns.html
│   │   │   └── exports.html
│   │   └── errors/
│   │       ├── 403.html  404.html  500.html
│   └── static/
│       ├── css/design-system.css     # tokens + shell + components
│       ├── js/app.js                 # sidebar toggle, filters, copy, confirm
│       └── img/logo.svg
│
├── tests/
│   ├── conftest.py
│   ├── test_models.py
│   ├── test_rbac.py
│   ├── test_risk_engine.py
│   └── test_api.py
│
├── scripts/
│   ├── bootstrap.sh                  # one-shot: venv + db + seed
│   └── smoke.sh                      # curl-based smoke test
│
└── docs/
    ├── README.md                     # documentation map / index
    ├── 01-getting-started.md
    ├── 02-architecture-hld.md
    ├── 03-low-level-design.md
    ├── 04-data-model.md
    ├── 05-database-guide.md
    ├── 06-admin-guide.md
    ├── 07-auditor-guide.md
    ├── 08-design-system.md
    ├── 09-api-reference.md
    ├── 10-operations-runbook.md
    ├── 11-security-and-compliance.md
    ├── 12-testing-guide.md
    ├── 13-troubleshooting-faq.md
    └── 14-glossary.md
```

---

## 1.2. Artifact Index

| # | Artifact | Purpose |
|---|---|---|
| A01 | `Makefile` | One-command lifecycle: setup, db, seed, run, test, reset |
| A02 | `requirements.txt` | Pinned Python deps |
| A03 | `.env.example` | Environment contract |
| A04 | `.gitignore` | Repo hygiene |
| A05 | `pytest.ini` | Test config |
| A06 | `docker-compose.yml` | Postgres (+ optional Redis) |
| A07 | `Dockerfile` | App image |
| A08 | `run.py` | Flask entrypoint |
| A09 | `sql/01_schema.sql` | Full DDL |
| A10 | `sql/02_functions_triggers.sql` | Audit + risk + immutability |
| A11 | `sql/03_indexes.sql` | Indexes |
| A12 | `sql/04_seed_reference.sql` | Reference data |
| A13 | `sql/05_seed_sample.sql` | Sample operational data |
| A14 | `sql/99_reset.sql` | Destructive reset |
| A15 | `app/config.py` | Configuration |
| A16 | `app/extensions.py` | Extension singletons |
| A17 | `app/__init__.py` | App factory |
| A18 | `app/cli.py` | CLI commands |
| A19 | `app/models/*.py` | ORM models |
| A20 | `app/security/*.py` | RBAC |
| A21 | `app/services/*.py` | Domain services |
| A22 | `app/blueprints/*.py` | Routes |
| A23 | `app/templates/**` | UI |
| A24 | `app/static/css/design-system.css` | Design system |
| A25 | `app/static/js/app.js` | Client behaviour |
| A26 | `tests/*.py` | Test suite |
| A27 | `scripts/*.sh` | Bootstrap + smoke |
| A28 | `docs/*.md` | 15 documentation files |
| A29 | `README.md` | Project map |

---

## 1.3. Databases Required

### 1.3.1 PostgreSQL — **REQUIRED** (system of record)

| Attribute | Value |
|---|---|
| Version | 15 or newer (14 works) |
| Database name | `idrm` |
| Default port | `5432` |
| Schema | `public` (kept simple for newcomers) |
| Why | ACID transactions, `JSONB` for before/after audit snapshots, `INET` for IP capture, partial indexes, rich constraint support, PL/pgSQL for server-side audit triggers and risk scoring |
| Role in IDRM | Every table lives here: identities, accounts, grants, findings, evidence, campaigns, audit trail |

### 1.3.2 SQLite — **TEST-ONLY** (optional)

| Attribute | Value |
|---|---|
| File | `instance/idrm_test.db` (in-memory by default) |
| Why | Lets `pytest` run with zero infrastructure |
| Caveat | Postgres-only features (JSONB, triggers, `INET`, partial indexes) are **not** exercised. Tests that need them are marked `@pytest.mark.pg` and skipped unless `IDRM_TEST_DATABASE_URL` points at Postgres |

### 1.3.3 Redis — **OPTIONAL** (performance, not correctness)

| Attribute | Value |
|---|---|
| Port | `6379` |
| Why | Server-side session store, cached KPI aggregates, rate-limiting login attempts |
| Behaviour if absent | App degrades gracefully: falls back to signed cookies + in-process LRU cache. Everything still works |

### 3.4 Databases deliberately **NOT** used (and why)

| Considered | Verdict | Reason |
|---|---|---|
| MongoDB | Rejected | IDRM is deeply relational; referential integrity is a *control*, not a convenience |
| Elasticsearch | Rejected | Free-text search over ~10⁵ rows is well within Postgres `tsvector` + `pg_trgm` |
| Neo4j | Deferred | Entitlement-graph traversal is valuable at scale; a recursive CTE covers v1 |
| DuckDB | Optional add-on | Useful for offline analytics exports; not required to run the app |

---

## 2. Screens at a glance

### Admin — Overview

- Four KPI cards: active identities, active grants, open findings, overdue findings
- Last risk scan panel with a **⚡ Run scan now** action
- Active certification campaign with a progress bar
- Findings by severity and by category, as horizontal bar charts
- Recent findings table, highest-risk identities, overdue findings

### Admin — Identity detail

- Avatar header with privileged / terminated badges and a risk score
- Accounts table (system, username, type, status, MFA, last login)
- Access grants table with inline **Revoke** and **+30d** actions
- Findings list, worst severity first
- Activity timeline drawn from the audit trail

### Admin — Finding detail

- Severity-bordered header with risk points
- Subject / Lifecycle / Ownership columns
- **Resolve** panel: change status, write a note (stored as evidence)
- Evidence list with kind badges and inline content
- Related findings on the same identity or account

### Auditor — Overview

- Same KPIs, **zero action buttons**
- Purple "Read-only assurance mode" banner
- Findings by system
- **Scan provenance** — proof that detection is running continuously

### Auditor — Audit trail

- Filters: actor, entity type, event type, severity, time window
- Every row: time, actor + IP, event, entity, action, severity, message
- A banner explaining the PostgreSQL rules that make it immutable
- **⇩ CSV** export, itself logged

---

## 3. Quick start

```bash
git clone <your-repo-url> idrm
cd idrm
bash scripts/bootstrap.sh
make run
```

Open **http://127.0.0.1:5000**.

### Demo credentials

| Mode | Username | Password |
|---|---|---|
| Admin | `admin` | `Admin#2025` |
| Auditor | `auditor` | `Audit#2025` |
| Analyst | `analyst` | `Analyze#2025` |
| Viewer | `viewer` | `View#2025` |

> These are development credentials. Change them before any real deployment.

### Manual path

```bash
make env install db-up db-create migrate seed passwords
make run
```

### Prerequisites

- Python 3.11+
- Docker (recommended) **or** PostgreSQL 14+
- GNU Make
- `curl` (for the smoke test)

---

## 4. Repository map

```
idrm/
├── Makefile                  ← start here: `make help`
├── README.md                 ← you are here
├── requirements.txt
├── .env.example
├── docker-compose.yml        ← Postgres (+ optional Redis)
├── Dockerfile
├── run.py                    ← Flask entrypoint
│
├── sql/                      ← the database, as reviewable SQL
│   ├── 01_schema.sql              tables, constraints, comments
│   ├── 02_functions_triggers.sql  audit capture, risk scoring, immutability
│   ├── 03_indexes.sql             read-path optimisation
│   ├── 04_seed_reference.sql      systems, entitlements, risk rules, SoD pairs
│   ├── 05_seed_sample.sql         identities, accounts, grants, findings
│   └── 99_reset.sql               destructive rebuild
│
├── app/
│   ├── __init__.py           create_app() factory
│   ├── config.py             Dev / Test / Prod
│   ├── extensions.py         db, login_manager, csrf, cache
│   ├── cli.py                init-db, seed-users, risk-scan, export-audit
│   ├── models/               ORM mirror of the SQL schema
│   ├── security/             RBAC matrix + route guards
│   ├── services/             risk_engine · reporting · audit_service
│   ├── blueprints/           auth · main · admin · auditor · api
│   ├── templates/            Jinja2, extending base.html
│   └── static/
│       ├── css/design-system.css
│       ├── js/app.js
│       └── img/logo.svg
│
├── tests/                    pytest suite
├── scripts/                  bootstrap.sh · smoke.sh
└── docs/                     15 documents, indexed below
```

> **Note on `docker-entrypoint-initdb.d`:** Postgres runs those scripts *only when the data
> volume is empty*. If you already booted the container, use `make migrate seed` instead —
> that is the canonical path and it is idempotent.


---

## 5. The data model in one picture

```
        ┌──────────────┐
        │  system_app  │  SAP · AWS · Okta · AD · Workday · GitHub …
        └───────┬──────┘
                │
     ┌──────────┴──────────┐
     │                     │
┌────▼─────┐        ┌──────▼───────┐
│ account  │        │ entitlement  │  AWS_IAM_ADMIN · SAP_AP_CLERK …
└────┬─────┘        └──────┬───────┘
     │                     │
     │   ┌─────────────────┘
     │   │
┌────▼───▼─────┐          ┌────────────┐
│ access_grant │◀─────────│  sod_rule  │  toxic pairs
└──────┬───────┘          └────────────┘
       │
┌──────▼──────┐           ┌────────────┐
│  identity   │──────────▶│  finding   │◀── risk_rule
└─────────────┘           └──────┬─────┘
                                 │
                          ┌──────▼─────┐
                          │  evidence  │
                          └────────────┘

                    ┌────────────────┐
   everything ────▶ │  audit_event   │  append-only
                    └────────────────┘
```

**The single most important sentence:** an `access_grant` links an *account* to an
*entitlement*. Everything else — risk, certification, remediation — is about that row.

---

## 6. How a risk finding is born

```
1. A rule's condition becomes true
      (e.g. an identity is marked terminated but still holds an AWS admin grant)

2. Someone runs a scan          →  make risk-scan
   or the scheduled job does    →  flask --app run.py risk-scan

3. risk_engine.run_full_scan()
      a. INSERT scan_run
      b. for each active risk_rule:
             hits = REGISTRY[rule.code](dormancy_days)
             for each hit:
                 if no open finding exists for this (rule, subject):
                     INSERT INTO finding ...

4. A BEFORE INSERT trigger on `finding`:
      • generates the code      FIND-2025-0017
      • sets the SLA due date    now() + 7 days (critical)
      • sets the risk score      30 points

5. An AFTER INSERT trigger on `finding` writes an `audit_event` row
      with the full JSONB snapshot of the new finding.

6. fn_recompute_all_risk_scores() recalculates every identity's score.

7. The scan_run row is marked `success` with its counts.
```

Everything after step 3 is automatic. You add a rule; the database does the rest.

---

## 7. Databases

| Database | Status | Role |
|---|---|---|
| **PostgreSQL 14+** | **REQUIRED** | System of record — all tables, triggers, functions, views |
| **SQLite** | Test-only | Lets `pytest` run with zero infrastructure |
| **Redis** | Optional | Server-side sessions and KPI cache; the app degrades gracefully without it |

### Why PostgreSQL

- **Row-level triggers** write `audit_event` — so an ORM bug, a manual `psql`
  `UPDATE`, or a future batch job all get audited identically
- **`JSONB`** stores full before/after row snapshots, GIN-indexable
- **`CREATE RULE ... DO INSTEAD NOTHING`** makes the audit table genuinely immutable
- **`INET`** captures actor IP addresses natively
- **Partial indexes** keep the open-findings and active-grants indexes small and hot
- **PL/pgSQL** puts risk scoring and SLA calculation next to the data

### Why not MongoDB

IDRM is fundamentally relational. Referential integrity here is not a convenience —
it's a control. A dangling grant is a security incident, not a schema anomaly.

---

## 8. Make targets

```
make help              Show every target
make setup             venv + install + db + schema + seed + passwords
make run               Dev server on :5000
make serve             Gunicorn on :8000

make db-up             Start Postgres (docker compose)
make db-down           Stop Postgres
make db-create         Create role + database
make migrate           Apply schema + functions + indexes
make seed              Load reference + sample data
make passwords         Set demo password hashes
make db-reset          DESTRUCTIVE full rebuild
make psql              Interactive SQL prompt
make dump              pg_dump to backups/

make risk-scan         Run the risk engine
make export-audit      Export the audit trail to CSV
make stats             Row counts for every table
make routes            List registered routes

make test              pytest (SQLite, fast)
make test-pg           pytest against real Postgres
make lint              ruff + black --check
make fmt               Auto-format
make smoke             curl-based smoke test

make docs              List the documentation set
make clean             Remove caches
make nuke              Remove venv too
```

---

## 9. Documentation map

| # | Document | Covers |
|---|---|---|
| 1 | [Getting Started](docs/01-getting-started.md) | Install, run, log in, first tour |
| 2 | [Architecture (HLD)](docs/02-architecture-hld.md) | Components, ADRs, data flows, deployment |
| 3 | [Low-Level Design](docs/03-low-level-design.md) | Modules, functions, sequences, extension points |
| 4 | [Data Model](docs/04-data-model.md) | Every table, column, relationship, view, function |
| 5 | [Database Guide](docs/05-database-guide.md) | Postgres setup, triggers, queries, tuning, backup |
| 6 | [Admin Guide](docs/06-admin-guide.md) | Day-to-day operations in Admin mode |
| 7 | [Auditor Guide](docs/07-auditor-guide.md) | Assurance work, worked audit examples |
| 8 | [Design System](docs/08-design-system.md) | Tokens, components, accessibility |
| 9 | [API Reference](docs/09-api-reference.md) | Every JSON endpoint with examples |
| 10 | [Operations Runbook](docs/10-operations-runbook.md) | Deploy, monitor, back up, recover |
| 11 | [Security & Compliance](docs/11-security-and-compliance.md) | Threat model, RBAC, ISO/SOX mapping |
| 12 | [Testing Guide](docs/12-testing-guide.md) | Run, write, and debug tests |
| 13 | [Troubleshooting & FAQ](docs/13-troubleshooting-faq.md) | Symptom → cause → fix |
| 14 | [Glossary](docs/14-glossary.md) | IAM and audit vocabulary |
| — | [Docs index](docs/README.md) | Reading order for newcomers |

---

## 10. Design system

**Slate + Emerald · Light mode · WCAG AAA**

| Token group | Highlights |
|---|---|
| Surfaces | `#f8fafc` page · `#ffffff` card · `#f1f5f9` elevated |
| Text | `#0f172a` heading · `#334155` body · `#64748b` muted |
| Brand | `#059669` emerald · `#047857` hover · `#d1fae5` light |
| Severity | critical `#b91c1c` · high `#c2410c` · medium `#b45309` · low `#047857` |
| Type | Inter, 0.75rem → 2.25rem, weights 400–800 |
| Radius | 0.375rem → 1.5rem, plus full |
| Spacing | 0.25rem → 4rem |

**Accessibility guarantees**

- Body text ≥ 7:1 contrast (AAA)
- Severity always pairs colour with a text label and a dot — never colour alone
- `*:focus-visible` outline on every interactive element
- `prefers-reduced-motion` respected
- Semantic landmarks, labelled inputs, `aria-label` on icon-only buttons
- `role="progressbar"` with `aria-valuenow` on every bar

Full details in [docs/08-design-system.md](docs/08-design-system.md).

---

## 11. Security

| Control | Implementation |
|---|---|
| Password storage | PBKDF2-SHA256, 600 000 iterations |
| Session | HttpOnly, SameSite=Lax, Secure in prod, `session_protection='strong'` |
| CSRF | Flask-WTF token on every mutating form |
| XSS | Jinja2 autoescaping + strict CSP, zero third-party JS |
| SQL injection | SQLAlchemy parameter binding throughout |
| Authorisation | `@roles_required` on every route + `PERMISSIONS` matrix |
| Audit immutability | PostgreSQL `CREATE RULE ... DO INSTEAD NOTHING` |
| Non-repudiation | Actor username + IP captured on every write |
| Export logging | Every CSV download writes an `EXPORT` audit event |
| Security headers | CSP, X-Frame-Options: DENY, Referrer-Policy, Permissions-Policy |

**Defence in depth for the auditor's independence**

1. Route decorator — `@roles_required("auditor", "admin", "viewer")`
2. Template guard — `{% if current_user.can_write %}` hides action buttons
3. Database role — `idrm_auditor` granted `SELECT` only

Full details in [docs/11-security-and-compliance.md](docs/11-security-and-compliance.md).

---

## 12. Testing

```bash
make test          # SQLite — fast, no infrastructure
make test-pg       # PostgreSQL — includes trigger tests
make smoke         # curl-based end-to-end check
```

Coverage:

| Area | Status |
|---|---|
| Model derived properties | ✅ |
| RBAC / permissions | ✅ |
| API response shapes | ✅ |
| Authentication gating | ✅ |
| Risk engine on Postgres | ✅ (marked `@pytest.mark.pg`) |
| Templates / E2E | ⬜ |

See [docs/12-testing-guide.md](docs/12-testing-guide.md).

---

## 13. Troubleshooting

| Symptom | Fix |
|---|---|
| `could not connect to server` | `make db-up` or check `DATABASE_URL` |
| Seeded users can't log in | `make passwords` |
| Risk scores all zero | `make risk-scan` |
| 403 after login | You're an auditor hitting `/admin/*` — that's by design |
| `SECRET_KEY must be set…` | Generate one and put it in `.env` |
| Styles look broken | Check the browser console for CSP errors |

Full list in [docs/13-troubleshooting-faq.md](docs/13-troubleshooting-faq.md).

---

## 14. License

MIT. See `LICENSE` if present, or treat as MIT for evaluation purposes.

---

<div align="center">

**IDRM** · Identity Data & Risk Management
Slate + Emerald · WCAG AAA · Flask 3 · PostgreSQL 16

`make help` to begin.

</div>
