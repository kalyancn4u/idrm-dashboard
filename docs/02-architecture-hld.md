# High-Level Design (HLD)

## 1. Purpose

IDRM gives an organisation a single, auditable answer to three questions about
identity risk:

1. **What access exists?** (identities → accounts → grants → entitlements)
2. **What is risky about it?** (rules → findings)
3. **Can an auditor independently verify both?** (immutable audit trail)

## 2. Scope

### In scope
- Identity, account, entitlement and grant inventory
- Rule-based risk detection with scoring
- Findings lifecycle with evidence
- Periodic access certification campaigns
- Immutable audit trail with before/after snapshots
- Two operator modes: Admin (write) and Auditor (read-only + export)
- REST read API

### Out of scope (v1)
- Live connectors to SAP/AWS/Okta/AD. Data is loaded by SQL seed, a batch job, or the API.
- Automated remediation (creating tickets in ServiceNow, disabling accounts).
- Multi-tenancy.
- Machine-learning risk scoring.

## 3. System context

```
                    ┌──────────────────────────────────────┐
                    │           Operators                  │
                    │  ┌────────┐  ┌──────────┐            │
                    │  │ Admin  │  │ Auditor  │            │
                    │  └───┬────┘  └────┬─────┘            │
                    └──────┼────────────┼──────────────────┘
                           │            │
                    HTTPS  │            │  HTTPS
                           ▼            ▼
        ┌──────────────────────────────────────────────────┐
        │                  IDRM (Flask)                    │
        │  ┌────────────┐ ┌────────────┐ ┌──────────────┐  │
        │  │  Admin BP  │ │ Auditor BP │ │   API BP     │  │
        │  └─────┬──────┘ └──────┬─────┘ └──────┬───────┘  │
        │        │               │              │          │
        │  ┌─────▼───────────────▼──────────────▼───────┐  │
        │  │            Service Layer                    │  │
        │  │  risk_engine · reporting · audit_service    │  │
        │  └─────────────────┬───────────────────────────┘  │
        │                    │                              │
        │  ┌─────────────────▼───────────────────────────┐  │
        │  │        SQLAlchemy ORM / Core                │  │
        │  └─────────────────┬───────────────────────────┘  │
        └────────────────────┼──────────────────────────────┘
                             │
        ┌────────────────────▼───────────────────────────┐
        │              PostgreSQL 14+                     │
        │   Tables · Triggers · Views · Functions         │
        │   (audit triggers live HERE, not in Python)     │
        └─────────────────────────────────────────────────┘

        ┌──────────────────┐
        │  Redis (OPTIONAL)│  sessions · KPI cache
        └──────────────────┘
```

## 4. Component responsibilities

| Component | Responsibility | Does NOT do |
|---|---|---|
| **Flask app factory** (`app/__init__.py`) | Wire config, extensions, blueprints, error handlers | Business logic |
| **Blueprints** | HTTP: parse request, call service, render template | SQL, rules |
| **Services** | Business logic: risk rules, KPIs, CSV builders, audit writes | HTTP, HTML |
| **Models** | Table mapping, relationship navigation, small derived properties | Queries with business meaning |
| **PostgreSQL triggers** | Row-level audit capture; `updated_at`; finding code generation | Application decisions |
| **PostgreSQL functions** | Risk scoring, SLA calculation, grant expiry | Web concerns |
| **Templates** | Presentation | Any data access beyond the view model |

## 5. Key architectural decisions

### ADR-001 — SQL files are the source of truth for the schema
The DDL lives in `sql/01_schema.sql`, not in `db.create_all()`. Reason: a DBA or
an auditor can read the schema without reading Python, and the schema is
reviewable in a pull request as plain text.

### ADR-002 — Audit capture happens in the database, not the ORM
PostgreSQL row triggers write `audit_event` rows. Reason: an application bug, a
manual `UPDATE` from psql, or a future batch job all get audited identically.
Application-level events (LOGIN, EXPORT, SCAN) go through `audit_service`.

### ADR-003 — The audit table is immutable
`CREATE RULE ... DO INSTEAD NOTHING` on UPDATE and DELETE. Reason: an audit log
that can be edited by the application is not an audit log.

### ADR-004 — Risk rules are Python functions, catalogued in SQL
The *catalogue* (`risk_rule`) is data; the *implementation* is code. Reason: SQL
can express the conditions, but the title/description text, the deduplication
logic and the auto-close behaviour need real control flow.

### ADR-005 — Two consoles, one dataset, enforced by decorators
`@roles_required("auditor", "admin")` on the auditor blueprint. Reason: the
auditor's independence is a *technical* guarantee, not a UI convention.

### ADR-006 — Redis is optional
The app functions identically with or without Redis. Reason: a reference
implementation must not require infrastructure it doesn't strictly need.

## 6. Data flow — a risk scan

```
1. Admin clicks "Run Risk Scan"   (POST /admin/scan)
2. admin.trigger_scan()           calls run_full_scan(trigger_source="manual")
3. risk_engine.run_full_scan()
   a. INSERT INTO scan_run (status='running')
   b. SELECT * FROM risk_rule WHERE is_active
   c. for each rule → REGISTRY[code](dormancy_days) → list[hit]
   d. for each hit → INSERT INTO finding IF not already open
   e. _auto_close_stale_findings()  → UPDATE finding SET status='closed'
   f. SELECT fn_recompute_all_risk_scores()
   g. UPDATE scan_run SET status='success', counts...
4. audit_service.log_event("SCAN", ...)
5. flash() + redirect to dashboard
```

Side effects, none of which the engine had to write explicitly:
- Each `INSERT INTO finding` fires `fn_finding_before_insert` → generates
  `FIND-YYYY-NNNN`, sets `due_at` from the SLA table, sets `risk_score`.
- Each `INSERT`/`UPDATE` on `finding` fires `fn_audit_row` → writes `audit_event`.
- Each `UPDATE identity SET risk_score` fires `trg_touch_identity` → `updated_at`.

## 7. Data flow — an auditor export

```
1. Auditor clicks "Download findings.csv"   (GET /auditor/export/findings.csv)
2. auditor.export_csv("findings")
3. reporting.export_findings_csv()   → SELECT ... → CSV string
4. audit_service.log_event("EXPORT", ..., flush=True)
   → INSERT INTO audit_event (actor_username, actor_ip, ...)
5. Response with Content-Disposition: attachment
```

The auditor cannot modify anything, but their *reading* is recorded.

## 8. Deployment topology

### Development
```
developer machine
  ├── Flask dev server (:5000, --debug)
  └── docker compose: postgres (:5432)
```

### Production (reference)
```
                 ┌──────────────┐
   Internet ───▶ │  TLS / WAF   │
                 └──────┬───────┘
                        │
                 ┌──────▼───────┐
                 │  Gunicorn    │  4 workers × 4 threads
                 │  :8000       │
                 └──────┬───────┘
                        │
        ┌───────────────┼────────────────┐
        │               │                │
   ┌────▼────┐    ┌─────▼─────┐   ┌──────▼──────┐
   │Postgres │    │  Redis    │   │  pgBackRest │
   │ primary │    │ (sessions)│   │  (backups)  │
   └─────────┘    └───────────┘   └─────────────┘
```

## 9. Non-functional requirements

| Requirement | Target | How it's met |
|---|---|---|
| Availability | 99.5% | Stateless app tier; DB is the only stateful component |
| Read latency (dashboard) | < 400 ms p95 | Covering indexes on `finding(status, severity)`, `identity(risk_score DESC)` |
| Audit write latency | < 5 ms | Trigger is a single INSERT; indexes kept minimal on hot path |
| Audit durability | Zero loss | Same transaction as the change it describes |
| Audit immutability | Tamper-evident | `CREATE RULE ... DO INSTEAD NOTHING` |
| Accessibility | WCAG AAA | Contrast ≥ 7:1 for body text; see `08-design-system.md` |
| Scale (v1) | 10⁵ identities, 10⁶ grants | Comfortable; see `05-database-guide.md` for the 10⁷ path |

## 10. Security boundaries

| Boundary | Trust level | Control |
|---|---|---|
| Browser → Flask | Untrusted | HTTPS, CSRF token, secure cookies, CSP header |
| Flask → Postgres | Trusted network | Least-privilege DB role, parameterised queries only |
| Flask → Redis | Trusted network | No PII in cache keys or values |
| Auditor → exports | Trusted user, untrusted action | Every export audit-logged with actor + IP |

## 11. Next

→ [Low-Level Design](03-low-level-design.md)

