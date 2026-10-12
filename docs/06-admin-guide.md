# Admin Guide

Everything an operator does in Admin mode.

## 1. Who is this for

| Role | Can do |
|---|---|
| **admin** | Everything, including marking identities privileged and running scans |
| **analyst** | Investigate, annotate, assign, remediate, revoke, certify, scan |

Both land on `/admin/`.

## 2. The Overview page

`/admin/`

### KPI cards

| Card | Meaning | Click-through |
|---|---|---|
| Active Identities | identities with `employment_status = 'active'` | Identities list |
| Active Grants | grants with `state = 'active'` | Grants list |
| Open Findings | findings in `open` or `in_review` | Findings list |
| Overdue Findings | open findings past `due_at` | Findings list |

### Last Risk Scan panel

Shows the most recent `scan_run` row: id, trigger source, duration, rules
evaluated, findings created, findings auto-closed, status.

Click **⚡ Run scan now** to execute immediately. The same button is in the top bar.

### Active Certification panel

The one campaign with `status = 'active'`, showing progress, approval and
revocation counts, and the due date.

## 3. Running a risk scan

**What it does:**

1. Creates a `scan_run` row with `status = 'running'`.
2. Iterates every active `risk_rule`.
3. Calls the matching Python function in `risk_engine.REGISTRY`.
4. For each hit, inserts a `finding` — unless an open finding already exists for
   the same `(rule, identity, account, grant)` tuple.
5. Closes findings whose condition no longer holds.
6. Recomputes every identity's `risk_score`.
7. Marks the `scan_run` as `success`.
8. Writes a `SCAN` audit event.

**How to trigger:**

- Button on the dashboard or top bar
- `make risk-scan`
- `flask --app run.py risk-scan --verbose`

**Reading the output:**

```
✔ Scan #11 complete — 13 rules, 4 new, 2 auto-closed, 18 identities rescored in 0.42s.
```

`4 new` means four conditions became true since the last scan. `2 auto-closed`
means two previously-raised conditions no longer hold.

## 4. Working the identity list

`/admin/identities`

### Filters

| Filter | Effect |
|---|---|
| Search | matches `display_name`, `email`, `external_ref`, `department` (ILIKE `%q%`) |
| Employment | `active` / `leave` / `terminated` |
| Type | `employee` / `contractor` / `vendor` / `service_account` / `robot` |
| Sort by | Risk score · Open findings · Name · Recently added |

### Reading the table

| Column | Meaning |
|---|---|
| Identity | name + email/ref; `priv` badge if privileged |
| Type | identity type |
| Department | |
| Status | employment status badge |
| Accounts | number of accounts owned |
| Open | open + in-review finding count |
| Risk | 0–100 score with a coloured bar |

## 5. Identity detail

`/admin/identities/<id>`

### Header

Avatar, name, privileged/terminated badges, job title, department, email,
identity type, employment status, external reference, risk score.

**Admin only:** a **Mark privileged / Unmark privileged** button.

### Three stat cards

Accounts · Active grants · Open findings.

### Accounts table

System, username, account type, status, MFA on/off, last login, grant count.

### Access Grants table

System, entitlement, account, state, granted date, expiry, last used, and a
**Revoke** action (admin/analyst only).

Privileged rows are highlighted. Grants with no expiry show a `standing` badge —
those are the ones to convert to time-bound.

### Findings list

Every finding ever raised against this identity, worst-severity first.

### Activity Timeline

The last 40 audit events touching this identity, its accounts, or its grants.
This is your "what happened here?" view.

## 6. Working the grants list

`/admin/grants`

### Filters

Search · State · System · **Privileged only** checkbox.

### Actions per row

| Button | Effect |
|---|---|
| **Revoke** | sets `state = 'revoked'`; fires an audit event |
| **+30d** | extends `expires_at` by 30 days |

### When to revoke

- The identity has left the organisation
- The grant is unused (stale)
- The entitlement is privileged and the grant has no expiry
- A certification decision was `revoke`

Revoking is a `state` change, never a `DELETE`. The row remains for history.

## 7. Working findings

`/admin/findings`

### Filters

Search · Status · Severity · System · Assignment (any / me / unassigned).

Default status filter is **open**, which means `open` + `in_review`.

### Reading the table

| Column | Meaning |
|---|---|
| Code | `FIND-YYYY-NNNN` |
| Severity | critical / high / medium / low |
| Title | the finding statement |
| Identity | subject |
| System | where the access lives |
| Rule | which risk rule fired |
| Due | SLA due date; overdue rows are tinted |
| Status | lifecycle state |
| Assignee | owner |

## 8. Finding detail

`/admin/findings/<id>`

### Header

Severity, status, overdue flag, code, rule code, title, description, and the
finding's risk points.

### Three columns

**Subject** — identity, account, system, entitlement.
**Lifecycle** — detected, due (+ days remaining), remediated, remediator.
**Ownership** — assignee, rule name, category, plus a reassignment form.

### Resolve panel (admin / analyst)

Pick a new status and write a note. The note is stored as evidence.

| Status | Meaning | Sets `remediated_at`? |
|---|---|---|
| `open` | newly detected, not yet triaged | no |
| `in_review` | someone is looking at it | no |
| `remediated` | fixed | yes |
| `accepted_risk` | business accepted the risk | no |
| `false_positive` | not actually a problem | no |
| `closed` | resolved (often by auto-close) | yes |

> Choosing `accepted_risk` or `false_positive` writes a `notice`-severity audit
> event. Auditors will see it. Use those statuses deliberately.

### Evidence

Each item shows kind, title, URI and content, plus collector and timestamp.

Click **+ Attach evidence** to add one. Kinds: `note`, `link`, `query`,
`screenshot`, `file`.

### Related findings

Other findings on the same identity or account — useful for spotting a systemic
problem rather than a one-off.

## 9. Certifications

`/admin/reviews`

### Campaign cards

Code, name, scope system, status, progress bar, approval/revocation/pending
counts, due date.

### Active items table

Identity · System · Account · Entitlement · Reviewer · Decision · Decided · Action.

Each row has **Approve** and **Revoke** buttons (admin/analyst).

### Deciding

- **Approve** — access is still needed. `decision = 'approve'`.
- **Revoke** — access is no longer needed. `decision = 'revoke'`.

After a `revoke` decision, go to `/admin/grants` and actually revoke the grant.
The certification records the *decision*; the grant table holds the *state*.

## 10. Interpreting a risk score

`risk_score` = Σ (severity points × rule weight), capped at 100.

| Severity | Points |
|---|---|
| critical | 30 |
| high | 18 |
| medium | 8 |
| low | 3 |

| Band | Range | Meaning |
|---|---|---|
| Critical | ≥ 60 | act now |
| High | 35–59 | act this sprint |
| Medium | 15–34 | schedule |
| Low | < 15 | monitor |

Only `open` and `in_review` findings count. Closing a finding lowers the score.

## 11. Daily / weekly routine

### Daily
1. Open the dashboard. Check **Overdue Findings**.
2. Triage anything new since yesterday's scan.
3. Assign owners to unassigned findings.

### Weekly
1. Run a scan.
2. Work the **Access Grants → privileged only** list.
3. Check certification progress against the due date.

### Monthly
1. Review all `accepted_risk` findings — has the acceptance expired?
2. Export `grants.csv` and look for standing privileges.
3. Verify `make export-audit` produces a coherent trail.

## 12. Next

→ [Auditor Guide](07-auditor-guide.md)

