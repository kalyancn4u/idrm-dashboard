# IDRM Documentation — Index

Welcome. This is the map. Read top-to-bottom the first time; use as reference after.

## Reading order for newcomers

| # | Document | What you'll learn | Time |
|---|---|---|---|
| 1 | [Getting Started](01-getting-started.md) | Install, run, log in, click around | 15 min |
| 2 | [Architecture (HLD)](02-architecture-hld.md) | The big picture: components, data flow, boundaries | 20 min |
| 3 | [Low-Level Design](03-low-level-design.md) | Modules, classes, functions, sequence flows | 25 min |
| 4 | [Data Model](04-data-model.md) | Every table, every column, every relationship | 30 min |
| 5 | [Database Guide](05-database-guide.md) | Postgres specifics, triggers, views, tuning | 25 min |
| 6 | [Admin Guide](06-admin-guide.md) | Day-to-day operations in Admin mode | 20 min |
| 7 | [Auditor Guide](07-auditor-guide.md) | Day-to-day assurance work in Auditor mode | 20 min |
| 8 | [Design System](08-design-system.md) | Tokens, components, accessibility rules | 15 min |
| 9 | [API Reference](09-api-reference.md) | Every JSON endpoint with examples | 10 min |
| 10 | [Operations Runbook](10-operations-runbook.md) | Deploy, back up, restore, troubleshoot | 20 min |
| 11 | [Security & Compliance](11-security-and-compliance.md) | RBAC, threat model, control mapping | 20 min |
| 12 | [Testing Guide](12-testing-guide.md) | How to run, write and interpret tests | 15 min |
| 13 | [Troubleshooting & FAQ](13-troubleshooting-faq.md) | Symptoms → causes → fixes | reference |
| 14 | [Glossary](14-glossary.md) | IAM/audit vocabulary | reference |

## The 60-second version

IDRM answers three questions:

1. **Who has access to what?** — `identity` → `account` → `access_grant` → `entitlement`
2. **What's wrong with that access?** — `risk_rule` fires → `finding` is raised
3. **Can you prove it?** — every change lands in `audit_event`, append-only, forever

Two consoles read the same data differently:

- **Admin mode** (`/admin/`) — fix things. Revoke, remediate, certify, scan.
- **Auditor mode** (`/auditor/`) — prove things. Read, filter, export, verify.

## The 5-minute SQL tour

```sql
-- Who has the most risk right now?
SELECT display_name, risk_score
  FROM identity
 ORDER BY risk_score DESC
 LIMIT 10;

-- What is broken?
SELECT code, severity, status, title
  FROM finding
 WHERE status IN ('open','in_review')
 ORDER BY fn_severity_points(severity) DESC;

-- Prove nothing was tampered with.
SELECT event_time, actor_username, event_type, entity_type, entity_id
  FROM audit_event
 ORDER BY event_time DESC
 LIMIT 20;
```
