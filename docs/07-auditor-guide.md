# Auditor Guide

Everything an assurance professional does in Auditor mode.

## 1. The independence guarantee

Auditor mode is **read-only by construction**, not by convention:

- Every route in `app/blueprints/auditor.py` is gated by
  `@roles_required("auditor", "admin", "viewer")` or `@auditor_required`.
- No auditor route performs an `INSERT`, `UPDATE` or `DELETE` on a governed table.
- The only writes are **audit events** recording that you looked or exported.
- The PostgreSQL role `idrm_auditor` can be granted `SELECT` only.

If you see a button that changes data, you are not in Auditor mode.

## 2. What you can do

| Capability | Where |
|---|---|
| See the risk posture | `/auditor/` |
| Browse the findings register | `/auditor/findings` |
| Examine a single finding, its evidence and its full change history | `/auditor/findings/<id>` |
| Read the immutable audit trail, filtered | `/auditor/audit-trail` |
| Review certification campaigns | `/auditor/campaigns` |
| Browse the evidence register | `/auditor/evidence` |
| Export CSV datasets | `/auditor/exports` |

## 3. The Overview page

`/auditor/`

Same KPIs as Admin, minus every action button. Plus:

- A purple **"Read-only assurance mode"** banner explaining that your reads are logged.
- **Findings by System** — useful for scoping an audit.
- **Scan Provenance** — the last five scans. This is your evidence that risk
  detection is running continuously, not just when someone remembered.
- **Certification Status** — progress against the active campaign.

## 4. Findings register

`/auditor/findings`

Identical filters to Admin mode. Every row links to the detail page.

Note that opening a finding writes a `VIEW` audit event. This is intentional:
in a real audit, "who looked at this and when" is itself evidence.

## 5. Finding detail — the important page

`/auditor/findings/<id>`

### Header
Severity, status, overdue flag, code, rule code, title, description, risk points.

### Three columns
**Subject** — identity, reference, account, system.
**Lifecycle** — detected, due, remediated, remediation note.
**Rule** — code, name, category, and the `logic_hint` describing the detection logic.

### Evidence
Every attached item with kind, title, URI/content, collector, timestamp and
SHA-256 where present.

### Full Change History — the centrepiece

Every audit event for this finding, newest first, each showing:

- Who (`actor_username`)
- When (`event_time`)
- What (`event_type`)
- The human message
- **A before/after JSON diff** — expand "Show state diff"

This answers "was this finding quietly downgraded?" definitively. If the severity
was changed from `critical` to `low`, there are two JSON snapshots proving it and
a username attached.

## 6. Audit trail

`/auditor/audit-trail`

### Filters

| Filter | Effect |
|---|---|
| Actor | `ILIKE %username%` |
| Entity | `identity`, `account`, `access_grant`, `finding`, … |
| Event | `INSERT`, `UPDATE`, `DELETE`, `LOGIN`, `SCAN`, `EXPORT`, `VIEW` |
| Severity | `info`, `notice`, `warning`, `critical` |
| Window | All time / 24h / 7d / 30d / 90d |

### Reading a row

| Column | Meaning |
|---|---|
| Time | `event_time` |
| Actor | username + IP address |
| Event | the operation type |
| Entity | table + row id |
| Action | human-readable verb |
| Severity | `notice`/`warning` get a coloured row |
| Message | the description |

### Why this table cannot be edited

```sql
CREATE RULE audit_event_no_update AS ON UPDATE TO audit_event DO INSTEAD NOTHING;
CREATE RULE audit_event_no_delete AS ON DELETE TO audit_event DO INSTEAD NOTHING;
```

Try it:

```sql
UPDATE audit_event SET severity = 'info' WHERE severity = 'critical';
-- UPDATE 0
```

Prove it to yourself. Then prove it to your auditee.

## 7. Certification campaigns

`/auditor/campaigns`

For each campaign: code, name, scope system, status, progress bar, approval and
revocation counts, start and due dates.

**What to look for:**

- A campaign past `due_at` with `status = 'active'` → the control failed
- A high `revoked` count → access was granted too liberally
- `total = 0` → the campaign was created but never populated
- No campaign for a critical system in the last 12 months → a gap

## 8. Exports

`/auditor/exports`

| Export | Columns |
|---|---|
| **Findings** | code, title, severity, status, risk_score, detected_at, due_at, remediated_at, identity_name, identity_ref, system_code, rule_code, assigned_to |
| **Identities** | external_ref, display_name, email, identity_type, department, job_title, employment_status, is_privileged, risk_score, accounts, active_grants, open_findings |
| **Active Grants** | identity_name, external_ref, system_code, username, account_type, entitlement_code, is_privileged, state, granted_at, expires_at, last_used_at, granted_by, justification |
| **Audit Trail** | id, event_time, actor_username, actor_ip, event_type, entity_type, entity_id, action, severity, message |

### Every export is logged

Downloading writes an `EXPORT` audit event with your username, IP, the dataset
and the byte size. Verify it: download `findings.csv`, then filter the audit
trail to `event_type = EXPORT`.

This is deliberate. In a regulated environment, "the auditor exported the full
grant list" is a fact that must be provable.

## 9. Evidence register

`/auditor/exports` (bottom section) and `/auditor/evidence`

Every piece of evidence across all findings: kind, title, finding code, severity,
collector, timestamp, and whether it's a link or inline content.

Use this to answer "what documentation exists for this control?"

## 10. A worked audit

**Question:** *"Can terminated staff still access production systems?"*

1. Go to `/auditor/findings?status=all&q=terminated`
2. Note the findings raised by rule `RR-COMP-001` ("Terminated Identity With Active Access").
3. Open one. Read the **Subject** column — which system, which entitlement.
4. Expand the **Full Change History**. When was it detected? Has it been remediated?
   If remediated, who did it and when?
5. Go to `/auditor/audit-trail?entity_type=access_grant&since=90`.
   Filter to the revoked grants. Confirm the revocation events exist.
6. Export `grants.csv`. Filter for `is_privileged = true`. Cross-check that no
   terminated identity appears with an active privileged grant.
7. If a finding was marked `accepted_risk`, look for a `notice`-severity audit
   event recording who accepted it and when.

**Question:** *"Is risk detection running continuously?"*

1. Go to `/auditor/` and read **Scan Provenance**.
2. Check the intervals. Daily scans = `trigger_source = 'scheduled'`.
3. Note the `findings_created` trend. Zero every time could mean the estate is
   clean — or that the rules aren't firing. Cross-check by opening a finding and
   confirming it was raised by a scan.

**Question:** *"Was this finding tampered with?"*

1. Open the finding.
2. Expand **Full Change History**.
3. Every status change, severity change and reassignment is there with a before
   and after JSON snapshot.
4. Cross-reference the audit trail by `entity_type = finding`, `entity_id = <id>`.

## 11. What you cannot do (and why)

| Cannot | Why |
|---|---|
| Change a finding status | Separation of duties: the auditee remediates, the auditor verifies |
| Revoke a grant | Same |
| Mark an identity privileged | Same |
| Run a risk scan | The scan is an operational action; you verify its output |
| Delete anything | Nothing in IDRM is deleted — rows are state-changed |

If you need a change made, you raise it with the Admin. The change itself then
appears in the audit trail, attributable to someone else. That is the point.

## 12. Next

→ [Design System](08-design-system.md)

