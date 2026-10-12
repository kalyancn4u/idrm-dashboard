# Security & Compliance

## 1. Threat model

| # | Threat | Impact | Control |
|---|---|---|---|
| T1 | Unauthorised console access | Full compromise | Flask-Login, PBKDF2-SHA256 (600 000 iterations), account lockout columns |
| T2 | Privilege escalation (auditor → admin) | Auditor could cover tracks | `@roles_required` on every route; no client-side role logic; DB role is `SELECT`-only for auditors |
| T3 | CSRF | Attacker triggers a revoke | Flask-WTF CSRF token on every mutating form |
| T4 | XSS | Session theft | Jinja2 autoescaping; strict CSP with no `unsafe-eval`; no third-party JS |
| T5 | SQL injection | Full DB compromise | SQLAlchemy parameter binding everywhere; no f-string SQL with user input |
| T6 | Audit tampering | Loss of non-repudiation | PG rules make `UPDATE`/`DELETE` on `audit_event` no-ops |
| T7 | Repudiation | "I didn't do that" | Actor username + IP captured on every write |
| T8 | Session hijack | Account takeover | `HttpOnly`, `SameSite=Lax`, `Secure` in prod; `session_protection='strong'` |
| T9 | Clickjacking | UI redressing | `X-Frame-Options: DENY`, CSP `frame-ancestors 'none'` |
| T10 | Data exfiltration via export | Bulk data loss | Every export audit-logged with actor and IP |
| T11 | Insider silently closing findings | Controls bypassed | `accepted_risk` / `false_positive` write `notice`-severity audit events |
| T12 | Credential stuffing | Account takeover | `failed_logins` counter and `locked_until` column (policy hook) |

## 2. Authentication

### Password storage

```python
generate_password_hash(password, method="pbkdf2:sha256:600000")
```

600 000 iterations, per OWASP guidance for PBKDF2-SHA256.

### Session

| Setting | Value |
|---|---|
| `SESSION_COOKIE_HTTPONLY` | True |
| `SESSION_COOKIE_SAMESITE` | Lax |
| `SESSION_COOKIE_SECURE` | True in production |
| `PERMANENT_SESSION_LIFETIME` | 8 hours |
| `REMEMBER_COOKIE_DURATION` | 14 days |
| `login_manager.session_protection` | `strong` |

### Login failure handling

Every failure writes a `LOGIN_FAILED` audit event with `flush=True`. The
`failed_logins` counter increments and `locked_until` can be set by a policy
hook (not wired in v1 — the columns exist).

## 3. Authorisation

### The matrix

| Permission | admin | analyst | auditor | viewer |
|---|:-:|:-:|:-:|:-:|
| view.dashboard | ✅ | ✅ | ✅ | ✅ |
| view.identity | ✅ | ✅ | ✅ | ❌ |
| view.account | ✅ | ✅ | ✅ | ❌ |
| view.grant | ✅ | ✅ | ✅ | ❌ |
| view.finding | ✅ | ✅ | ✅ | ✅ |
| view.evidence | ✅ | ✅ | ✅ | ❌ |
| view.audit | ✅ | ✅ | ✅ | ❌ |
| view.campaign | ✅ | ✅ | ✅ | ❌ |
| view.report | ✅ | ✅ | ✅ | ✅ |
| edit.identity | ✅ | ❌ | ❌ | ❌ |
| edit.grant | ✅ | ✅ | ❌ | ❌ |
| edit.finding | ✅ | ✅ | ❌ | ❌ |
| edit.evidence | ✅ | ✅ | ❌ | ❌ |
| edit.campaign | ✅ | ✅ | ❌ | ❌ |
| run.scan | ✅ | ✅ | ❌ | ❌ |
| export.data | ✅ | ✅ | ✅ | ❌ |
| admin.system | ✅ | ❌ | ❌ | ❌ |

### Defence in depth

1. **Route decorator** — `@roles_required(...)`
2. **Permission check** — `has_permission("edit.finding")` for finer decisions
3. **Template guard** — `{% if current_user.can_write %}` hides the button
4. **Database role** — `idrm_auditor` granted `SELECT` only
5. **Audit** — even a successful escalation attempt leaves a trail

Layers 1–2 are authoritative. 3 is cosmetic. 4 is the backstop.

## 4. The audit trail as a control

### Properties

| Property | How |
|---|---|
| **Completeness** | Row triggers on 7 tables + application events for LOGIN/LOGOUT/SCAN/EXPORT/VIEW |
| **Accuracy** | Full `to_jsonb(OLD)` / `to_jsonb(NEW)` snapshots, not just changed fields |
| **Attribution** | `actor_username` + `actor_ip` + optional `actor_user_id` |
| **Immutability** | `CREATE RULE ... DO INSTEAD NOTHING` on UPDATE and DELETE |
| **Timeliness** | Written in the same transaction as the change it describes |
| **Availability** | Standard table; index-only reads for the common filters |

### Proving immutability to an auditor

```sql
-- 1. Count the rows
SELECT count(*) FROM audit_event;

-- 2. Attempt to modify
UPDATE audit_event SET message = 'tampered' WHERE id = 1;
-- Expected: UPDATE 0

-- 3. Confirm nothing changed
SELECT message FROM audit_event WHERE id = 1;

-- 4. Attempt to delete
DELETE FROM audit_event WHERE id = 1;
-- Expected: DELETE 0
```

Run this in front of the auditor. It takes 10 seconds and settles the question.

### Correlation IDs

`correlation_id` groups events from one request. Multi-step operations
(reassign + status change + evidence attach) share a UUID, so the auditor can
reconstruct "everything that happened in that one action".

## 5. Control mapping

### ISO/IEC 27001:2022

| Control | IDRM implementation |
|---|---|
| A.5.15 Access control | `access_grant` with `justification`, `granted_by`, `expires_at` |
| A.5.16 Identity management | `identity` lifecycle with `employment_status` |
| A.5.17 Authentication information | `password_last_changed_at`, `mfa_enabled` |
| A.5.18 Access rights | Provisioning and revocation via `access_grant.state` |
| A.8.2 Privileged access rights | `account_type = 'privileged'`, `entitlement.is_privileged`, rule `RR-PRIV-002` |
| A.8.3 Information access restriction | `entitlement` model + SoD rules |
| A.8.5 Secure authentication | MFA flag + rule `RR-PRIV-001` |
| A.8.15 Logging | `audit_event` |
| A.8.16 Monitoring activities | `risk_rule` + `finding` + `scan_run` |
| A.5.3 Segregation of duties | `sod_rule` + rule `RR-SOD-001` |

### SOX ITGC

| Control | IDRM implementation |
|---|---|
| Access provisioning | `access_grant` + audit trail |
| Access removal | Rule `RR-COMP-001` (terminated identity with active access) |
| Privileged access review | Certification campaigns with `access_grant` scope |
| Segregation of duties | `sod_rule` table, 12 toxic pairs seeded |
| Change log | `audit_event` with before/after snapshots |

### GDPR

| Article | IDRM relevance |
|---|---|
| Art. 5(1)(f) Integrity and confidentiality | RBAC + audit trail |
| Art. 30 Records of processing | `system_app.data_classification` |
| Art. 32 Security of processing | Encryption in transit; access control; audit logging |
| Art. 33 Breach notification | Audit trail supports the 72-hour investigation |

> **Note:** `identity` stores personal data (name, email, department). The
> database must be encrypted at rest, backed up securely, and covered by a
> retention policy. Deleting an identity cascades to its accounts and grants,
> but **audit events are never deleted** — they contain JSONB snapshots. Plan a
> pseudonymisation strategy if erasure requests are in scope.

## 6. Hardening checklist

| Item | Status |
|---|---|
| `SECRET_KEY` is random and ≥ 32 bytes | ⬜ operator |
| `SESSION_COOKIE_SECURE=1` | ⬜ operator |
| TLS terminated in front of the app | ⬜ operator |
| Database not exposed to the internet | ⬜ operator |
| Least-privilege DB roles | ✅ scripted (§11 of the DB guide) |
| No secrets in the repo | ✅ `.gitignore` covers `.env` |
| CSRF on all mutating routes | ✅ Flask-WTF |
| Security headers set | ✅ CSP, X-Frame-Options, Referrer-Policy |
| Parameterised queries only | ✅ SQLAlchemy |
| Audit immutability | ✅ PG rules |
| Dependency pinning | ✅ `requirements.txt` |
| Login failures logged | ✅ |
| Export logging | ✅ |

## 7. Compliance reporting

```bash
# Full audit trail
make export-audit

# Active grants for a privileged-access review
curl -b cookies.txt http://localhost:5000/auditor/export/grants.csv > grants.csv

# Findings register for the audit committee
curl -b cookies.txt http://localhost:5000/auditor/export/findings.csv > findings.csv
```

## 8. Next

→ [Testing Guide](12-testing-guide.md)

