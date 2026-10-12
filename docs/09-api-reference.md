# API Reference

Base path: `/api/v1`

All endpoints except `/health` require an authenticated session cookie.
The API is currently **read-only**; mutations go through the HTML blueprints so
that CSRF protection and RBAC remain in one place.

## Authentication

The API uses the same session cookie as the web UI:

```bash
# 1. Fetch the login page to obtain a CSRF token and session cookie
curl -c cookies.txt http://localhost:5000/auth/login

# 2. Extract the csrf_token from the HTML, then POST
curl -b cookies.txt -c cookies.txt \
     -d "csrf_token=<TOKEN>&username=admin&password=Admin#2025" \
     http://localhost:5000/auth/login

# 3. Call the API
curl -b cookies.txt http://localhost:5000/api/v1/kpis
```

---

## `GET /health`

Public. No authentication.

**Response 200**
```json
{
  "status": "ok",
  "components": {
    "database": { "ok": true, "detail": "ok" }
  }
}
```

**Response 503** when the database is unreachable.

---

## `GET /kpis`

Dashboard aggregates in one call.

**Response 200**
```json
{
  "kpi": {
    "identities_active": 16,
    "identities_terminated": 2,
    "accounts_active": 29,
    "grants_active": 40,
    "findings_open": 15,
    "findings_critical": 6,
    "findings_overdue": 4,
    "remediated_30d": 1,
    "high_risk_identities": 5
  },
  "severity": [
    { "severity": "critical", "n": 6 },
    { "severity": "high",     "n": 5 },
    { "severity": "medium",   "n": 3 },
    { "severity": "low",      "n": 1 }
  ],
  "categories": [
    { "category": "sod",       "n": 4 },
    { "category": "orphan",    "n": 3 },
    { "category": "privilege", "n": 4 }
  ],
  "last_scan": {
    "id": 11,
    "started_at": "2025-01-15T09:00:00+00:00",
    "finished_at": "2025-01-15T09:00:42+00:00",
    "trigger_source": "manual",
    "status": "success",
    "rules_evaluated": 13,
    "findings_created": 4,
    "findings_closed": 2,
    "duration_s": 42.11
  }
}
```

---

## `GET /findings`

**Query parameters**

| Name | Type | Default | Notes |
|---|---|---|---|
| `status` | string | `open` | `open` = open + in_review; `all` = everything |
| `page` | int | 1 | |
| `per_page` | int | 25 | max 200 |

**Response 200**
```json
{
  "page": 1,
  "per_page": 25,
  "count": 15,
  "items": [
    {
      "id": 17,
      "code": "FIND-2025-0017",
      "title": "Terminated identity retains AWS admin access",
      "severity": "critical",
      "status": "open",
      "risk_score": 30.0,
      "detected_at": "2025-01-03T08:12:00+00:00",
      "due_at": "2025-01-10T08:12:00+00:00",
      "identity_name": "Lars Petersen",
      "system_code": "AWS"
    }
  ]
}
```

---

## `GET /identities`

**Query parameters**

| Name | Type | Default |
|---|---|---|
| `page` | int | 1 |
| `per_page` | int | 25 (max 200) |

Sorted by `risk_score DESC`, then `display_name`.

**Response 200**
```json
{
  "page": 1,
  "per_page": 25,
  "count": 18,
  "items": [
    {
      "id": 11,
      "external_ref": "E1011",
      "display_name": "Lars Petersen",
      "email": "lars.petersen@acme.example",
      "identity_type": "employee",
      "department": "Engineering",
      "employment_status": "terminated",
      "is_privileged": true,
      "risk_score": 78.5,
      "open_findings": 5
    }
  ]
}
```

---

## `GET /audit-events`

**Requires `auditor` or `admin`.**

**Query parameters**

| Name | Type | Notes |
|---|---|---|
| `entity_type` | string | `identity`, `account`, `access_grant`, `finding`, … |
| `event_type` | string | `INSERT`, `UPDATE`, `DELETE`, `LOGIN`, `SCAN`, `EXPORT`, `VIEW` |
| `actor` | string | `ILIKE %actor%` |
| `severity` | string | `info`/`notice`/`warning`/`critical` |
| `page`, `per_page` | int | |

**Response 200**
```json
{
  "page": 1,
  "per_page": 50,
  "total": 1284,
  "items": [
    {
      "id": 8832,
      "event_time": "2025-01-15T09:04:11+00:00",
      "actor_username": "admin",
      "actor_ip": "10.0.0.42",
      "event_type": "UPDATE",
      "entity_type": "finding",
      "entity_id": 17,
      "action": "Finding status → remediated",
      "severity": "info",
      "message": "FIND-2025-0017 moved to remediated",
      "before_state": { "status": "open" },
      "after_state":  { "status": "remediated" },
      "correlation_id": "b3f1e2a4-..."
    }
  ]
}
```

**Response 403** for `viewer` role:
```json
{
  "error": "forbidden",
  "message": "Role 'viewer' may not access this resource.",
  "required_roles": ["auditor", "admin"]
}
```

---

## `GET /campaigns`

```json
{
  "items": [
    {
      "id": 1,
      "code": "RC-2025-Q1-AP",
      "name": "Q1 2025 — Finance Access Certification",
      "status": "active",
      "scope_code": "SAP",
      "starts_at": "2025-01-01T00:00:00+00:00",
      "due_at": "2025-01-29T00:00:00+00:00",
      "total": 12,
      "decided": 7,
      "revoked": 2,
      "approved": 5,
      "progress_pct": 58
    }
  ]
}
```

---

## Error envelope

| Status | Body |
|---|---|
| 401 / 302 | Redirect to `/auth/login` |
| 403 | `{"error":"forbidden","message":"...","required_roles":[...]}` |
| 404 | `{"error":"not_found"}` |
| 500 | `{"error":"server_error"}` |

## Rate limiting

Not implemented in v1. Recommended at the edge: 60 requests/minute per IP for
authenticated endpoints, 10/minute for `/auth/login`.

## Versioning

The path carries the version (`/api/v1`). Breaking changes get a new prefix.

## Next

→ [Operations Runbook](10-operations-runbook.md)

