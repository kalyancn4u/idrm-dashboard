# Low-Level Design (LLD)

This document describes every module, its public surface, and the flows that
matter. It is written so that a new developer can trace a request end-to-end.

## 1. Module map

```
app/
├── __init__.py          create_app() — factory
├── config.py            BaseConfig / DevelopmentConfig / TestingConfig / ProductionConfig
├── extensions.py        db, login_manager, csrf, cache
├── cli.py               init-db, seed-users, risk-scan, export-audit, demo-reset, db-info
│
├── models/
│   ├── user.py          AppUser
│   ├── identity.py      Identity
│   ├── system_app.py    SystemApp
│   ├── account.py       Account
│   ├── entitlement.py   Entitlement
│   ├── grant.py         AccessGrant
│   ├── risk.py          RiskRule, SodRule, Finding, Evidence
│   ├── review.py        ReviewCampaign, ReviewItem
│   └── audit.py         AuditEvent, ScanRun
│
├── security/
│   ├── rbac.py          PERMISSIONS dict, has_permission()
│   └── decorators.py    roles_required, admin_required, auditor_required, write_required
│
├── services/
│   ├── audit_service.py log_event(), flush_buffer(), set_actor_context()
│   ├── risk_engine.py   REGISTRY, run_full_scan(), _upsert_findings(), _auto_close_stale_findings()
│   └── reporting.py     kpi_summary(), findings_by_*(), audit_trail(), export_*_csv()
│
└── blueprints/
    ├── auth.py          /auth/login, /auth/logout
    ├── main.py          /, /dashboard, /healthz, /about
    ├── admin.py         /admin/*
    ├── auditor.py       /auditor/*
    └── api.py           /api/v1/*
```

## 2. The application factory

```python
create_app(config_name) →
    1. Flask(__name__)
    2. app.config.from_object(get_config(config_name))
    3. _configure_logging(app)
    4. db.init_app(app); login_manager.init_app(app); csrf.init_app(app)
    5. ext.cache = build_cache()          # Redis if REDIS_URL, else NullCache
    6. register 5 blueprints
    7. register_cli(app)
    8. import app.models                   # registers mappers
    9. _register_request_hooks(app)
   10. _register_error_handlers(app)
   11. _register_security_headers(app)
   12. optional boot-time risk scan
   → app
```

**Request hooks**

| Hook | Effect |
|---|---|
| `before_request` | initialises `g` |
| `after_request` (audit) | flushes `g.audit_buffer` into `audit_event` |
| `after_request` (headers) | CSP, X-Frame-Options, Referrer-Policy, Permissions-Policy |
| `context_processor` | injects `app_name`, `app_tagline`, `now_utc`, `current_year`, `nav_active` |

## 3. Authentication flow

```
GET /auth/login
  → render auth/login.html

POST /auth/login
  → AuthBlueprint.login()
      1. lookup AppUser by username OR email
      2. user.check_password(raw)
         └── Werkzeug pbkdf2:sha256:600000
      3. on failure:
           audit_service.log_event("LOGIN_FAILED", flush=True)
           flash("Invalid credentials"); return 401
      4. on success:
           login_user(user, remember=...)
           user.last_login_at = now(); commit()
           audit_service.set_actor_context(user.username)
               └── SELECT set_config('idrm.actor', :u, true)
                   ↳ every DB trigger from here on records this actor
           audit_service.log_event("LOGIN", flush=True)
           redirect(next or /dashboard)
```

`/dashboard` dispatches by role:

| Role | Destination |
|---|---|
| admin, analyst | `admin.dashboard` |
| auditor | `auditor.dashboard` |
| viewer | `auditor.dashboard` |

## 4. RBAC

`app/security/rbac.py` holds a `PERMISSIONS` dict: role → set of permission strings.

```python
PERMISSIONS = {
  "admin":   {... full set ...},
  "analyst": {... no admin.system, no edit.identity ...},
  "auditor": {... view.* + export.data only ...},
  "viewer":  {"view.dashboard", "view.finding", "view.report"},
}
```

Enforcement:

```python
@admin_bp.route("/identities/<int:identity_id>/toggle-privileged", methods=["POST"])
@admin_required
def toggle_privileged(identity_id): ...
```

The decorator returns **JSON 403** for paths starting `/api/`, **HTML 403** otherwise.

## 5. Risk engine internals

### 5.1 Rule registry

```python
REGISTRY: dict[str, callable] = {}

def rule(code):
    def deco(fn): REGISTRY[code] = fn; return fn
    return deco

@rule("RR-SOD-001")
def _sod_conflicts(dormancy_days): ...   # returns list[hit]
```

A **hit** is:

```python
{
  "identity_id":     int | None,
  "account_id":      int | None,
  "access_grant_id": int | None,
  "system_id":       int | None,
  "title":           str,
  "description":     str,
}
```

### 5.2 Scan algorithm

```
run_full_scan(trigger_source, triggered_by):
  t0 = now()
  scan_id = INSERT scan_run(status='running') RETURNING id

  for rule in SELECT * FROM risk_rule WHERE is_active ORDER BY code:
      fn = REGISTRY.get(rule.code)
      if fn is None: continue                   # catalogued but unimplemented
      hits = fn(dormancy_days)
      created += _upsert_findings(rule, hits)

  closed    = _auto_close_stale_findings(set(REGISTRY))
  rescored  = SELECT fn_recompute_all_risk_scores()
  duration  = now() - t0

  UPDATE scan_run SET finished_at=now(), status='success', counts...
  log_event("SCAN", ...)

  return summary
```

### 5.3 Deduplication

`_upsert_findings` will not create a second open finding for the same
`(risk_rule_id, identity_id, account_id, access_grant_id)` tuple:

```sql
SELECT 1 FROM finding
 WHERE risk_rule_id = :rid
   AND status IN ('open','in_review')
   AND COALESCE(identity_id, 0)     = COALESCE(:iid, 0)
   AND COALESCE(account_id, 0)      = COALESCE(:aid, 0)
   AND COALESCE(access_grant_id, 0) = COALESCE(:gid, 0)
```

The `COALESCE(..., 0)` pattern makes `NULL` comparable, which raw `=` cannot do.

### 5.4 Auto-close

`_auto_close_stale_findings` re-runs every rule, builds a set of live
`(rule_id, identity_id, account_id, grant_id)` tuples, and closes any open
finding whose tuple is absent.

### 5.5 Scoring

Two layers:

- **Per-finding**: `fn_finding_before_insert` sets `risk_score = fn_severity_points(severity)`
  (critical 30, high 18, medium 8, low 3).
- **Per-identity**: `fn_identity_risk_score(id)` sums `severity_points × rule.weight`
  over open/in-review findings, capped at 100. `fn_recompute_all_risk_scores()`
  applies it to every identity.

## 6. Audit architecture

### 6.1 Two write paths

| Path | Trigger | Used for |
|---|---|---|
| **DB trigger** `fn_audit_row` | AFTER INSERT/UPDATE/DELETE on `identity`, `account`, `access_grant`, `finding`, `review_campaign`, `review_item`, `evidence` | Row-level changes |
| **App call** `log_event()` | Explicit | LOGIN, LOGOUT, LOGIN_FAILED, SCAN, EXPORT, VIEW |

### 6.2 Actor attribution

Triggers read `current_setting('idrm.actor', true)`. The app sets it after login:

```python
db.session.execute(text("SELECT set_config('idrm.actor', :a, true)"), {"a": username})
```

The `true` third argument makes it transaction-local, so it cannot leak between
requests sharing a pooled connection.

### 6.3 Buffering

`log_event` appends to `g.audit_buffer` unless `flush=True`. The after-request
hook writes the buffer. If the view raises before that hook, nothing is written —
which is correct: a failed operation should not leave an audit row claiming success.

Security-critical events (`LOGIN`, `LOGIN_FAILED`, `EXPORT`, `SCAN`) pass
`flush=True` and are written immediately.

### 6.4 Immutability

```sql
CREATE RULE audit_event_no_update AS ON UPDATE TO audit_event DO INSTEAD NOTHING;
CREATE RULE audit_event_no_delete AS ON DELETE TO audit_event DO INSTEAD NOTHING;
```

Consequence: `UPDATE audit_event ...` silently affects 0 rows. `TRUNCATE` still
works — an intentional operational escape hatch for dev/test.

## 7. Reporting service

Every aggregate query lives in `reporting.py`. Blueprints receive plain dicts.

| Function | Returns |
|---|---|
| `kpi_summary()` | 9 scalar counts in one query |
| `findings_by_severity()` | `[{severity, n}]` ordered critical→low |
| `findings_by_category()` | `[{category, n}]` |
| `findings_by_system()` | `[{system_code, system_name, n, critical_n}]` |
| `recent_findings(limit)` | joined finding rows |
| `top_risky_identities(limit)` | identities + open-finding count |
| `overdue_findings(limit)` | findings past `due_at` |
| `active_campaign()` | one campaign + progress maths |
| `last_scan()` / `scan_history()` | scan_run rows |
| `audit_trail(...)` | `(rows, total)` |
| `evidence_register(limit)` | joined evidence rows |
| `campaign_list()` | campaigns + progress |
| `export_*_csv()` | CSV strings |

## 8. Sequence: Admin revokes a grant

```
Browser      admin_bp          audit_service        PostgreSQL
   │              │                   │                  │
   │ POST /admin/grants/42/revoke      │                  │
   ├─────────────▶│                   │                  │
   │              │ CSRF check        │                  │
   │              │ @write_required   │                  │
   │              │ db.session.get(AccessGrant, 42)       │
   │              ├──────────────────────────────────────▶│
   │              │ grant.state = 'revoked'               │
   │              │ db.session.commit()                   │
   │              ├──────────────────────────────────────▶│
   │              │                   │   trg_audit_access_grant
   │              │                   │   (BEFORE→AFTER row)│
   │              │                   │   INSERT audit_event│
   │              │ log_event("UPDATE", ...)               │
   │              ├──────────────────▶│                  │
   │              │                   │ buffer → after_request
   │              │ flash("Grant revoked")               │
   │◀─────────────┤ 302 → referrer    │                  │
```

## 9. Sequence: Auditor opens a finding

```
Browser      auditor_bp         audit_service        PostgreSQL
   │              │                   │                  │
   │ GET /auditor/findings/17         │                  │
   ├─────────────▶│                   │                  │
   │              │ @roles_required("auditor","admin","viewer")
   │              │ db.session.get(Finding, 17)           │
   │              ├──────────────────────────────────────▶│
   │              │ log_event("VIEW", "Finding examined") │
   │              ├──────────────────▶│                  │
   │              │ history = SELECT audit_event WHERE entity_type='finding' AND entity_id=17
   │              ├──────────────────────────────────────▶│
   │              │ render auditor/finding_detail.html    │
   │◀─────────────┤ 200               │                  │
```

The *reading* is audited. An auditor cannot modify data, but their access to it is provable.

## 10. Template inheritance

```
base.html
├── components/_sidebar.html     (role-aware nav)
├── components/_topbar.html      (breadcrumb, scan button, user chip)
├── components/_macros.html      (imported, not extended)
│
├── auth/login.html              (uses anon_content block)
├── admin/dashboard.html
├── admin/identities.html
├── admin/identity_detail.html
├── admin/findings.html
├── admin/finding_detail.html
├── admin/grants.html
├── admin/reviews.html
├── auditor/dashboard.html
├── auditor/findings.html
├── auditor/finding_detail.html
├── auditor/audit_trail.html
├── auditor/campaigns.html
├── auditor/exports.html
└── errors/{403,404,500}.html
```

**Macros available** (`components/_macros.html`):

`kpi`, `sev_badge`, `status_badge`, `risk_band`, `empty_state`, `pager`,
`progress`, `reltime`, `section`, `page_head`.

## 11. Error handling

| Status | Handler | Renders |
|---|---|---|
| 403 | `_forbidden` | `errors/403.html` |
| 404 | `_not_found` | `errors/404.html` |
| 500 | `_server_error` | rollback, `errors/500.html` |

API paths receive JSON 403 from the decorator, not HTML.

## 12. Extension points

| I want to… | Add to… |
|---|---|
| New risk rule | `@rule("RR-XXX-000")` in `risk_engine.py` + a row in `risk_rule` |
| New SoD pair | A row in `sod_rule` (no code change) |
| New console role | `PERMISSIONS` in `rbac.py` + the `CHECK` constraint in `01_schema.sql` |
| New export | A function in `reporting.py` + an entry in the `builders` dict in `auditor.export_csv` |
| New page | A blueprint route + a template extending `base.html` |
| New API endpoint | A route in `api.py` |

## 13. Next

→ [Data Model](04-data-model.md)

