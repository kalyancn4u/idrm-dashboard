# Database Guide

## 1. Which databases, and why

| Database | Status | Role |
|---|---|---|
| **PostgreSQL 14+** | **REQUIRED** | System of record. Everything lives here. |
| **SQLite** | Test-only | Lets `pytest` run without infrastructure. Not a deployment target. |
| **Redis** | Optional | Sessions + KPI cache. The app works without it. |

### Why PostgreSQL and not MySQL / MongoDB?

| Requirement | PostgreSQL | MySQL | MongoDB |
|---|---|---|---|
| Row-level triggers writing an audit table | ✅ Mature | ✅ | ❌ |
| `JSONB` with GIN indexing for before/after snapshots | ✅ | ⚠️ JSON only | ✅ |
| `INET` type for IP capture | ✅ | ❌ | ❌ |
| Partial indexes (`WHERE status IN (...)`) | ✅ | ❌ | ⚠️ |
| `CREATE RULE ... DO INSTEAD NOTHING` for true immutability | ✅ | ❌ | ❌ |
| Enforced foreign keys with `ON DELETE` semantics | ✅ | ✅ | ❌ |
| Recursive CTEs for entitlement graphs | ✅ | ✅ | ❌ |

The audit-immutability rule alone justifies the choice.

## 2. Getting PostgreSQL running

### Docker (recommended)

```bash
make db-up        # docker compose up -d postgres
```

Connects as `idrm` / `idrm` on `localhost:5432`, database `idrm`.

### Native install

```bash
sudo -u postgres psql
CREATE ROLE idrm LOGIN PASSWORD 'idrm';
CREATE DATABASE idrm OWNER idrm;
\q
```

Then set `DATABASE_URL` in `.env`:

```
DATABASE_URL=postgresql+psycopg2://idrm:idrm@localhost:5432/idrm
```

## 3. Applying the schema

The files in `sql/` are numbered and **must run in order**:

| File | Contains | Idempotent? |
|---|---|---|
| `01_schema.sql` | Tables, constraints, comments | ✅ (`CREATE TABLE IF NOT EXISTS`) |
| `02_functions_triggers.sql` | Functions, triggers, immutability rules | ✅ (`CREATE OR REPLACE`, `DROP TRIGGER IF EXISTS`) |
| `03_indexes.sql` | All indexes | ✅ (`CREATE INDEX IF NOT EXISTS`) |
| `04_seed_reference.sql` | Systems, entitlements, risk rules, SoD rules | ✅ (`ON CONFLICT DO NOTHING`) |
| `05_seed_sample.sql` | Identities, accounts, grants, findings, campaigns | ✅ (guarded by `NOT EXISTS`) |
| `99_reset.sql` | Drops everything | ❌ **destructive** |

```bash
make migrate      # 01 → 02 → 03
make seed         # 04 → 05
make db-reset     # 99 → 01 → 02 → 03 → 04 → 05 → passwords
```

## 4. Triggers explained

### 4.1 `updated_at` maintenance

```sql
CREATE TRIGGER trg_touch_identity
    BEFORE UPDATE ON identity
    FOR EACH ROW EXECUTE FUNCTION fn_touch_updated_at();
```

Applied to: `app_user`, `system_app`, `identity`, `account`, `access_grant`,
`finding`, `review_campaign`.

### 4.2 Audit capture

```sql
CREATE TRIGGER trg_audit_access_grant
    AFTER INSERT OR UPDATE OR DELETE ON access_grant
    FOR EACH ROW EXECUTE FUNCTION fn_audit_row();
```

Applied to: `identity`, `account`, `access_grant`, `finding`, `review_campaign`,
`review_item`, `evidence`.

`fn_audit_row` branches on `TG_OP`:

```plpgsql
IF TG_OP = 'INSERT' THEN
    v_id := NEW.id; v_after := to_jsonb(NEW);
ELSIF TG_OP = 'UPDATE' THEN
    v_id := NEW.id; v_before := to_jsonb(OLD); v_after := to_jsonb(NEW);
ELSE  -- DELETE
    v_id := OLD.id; v_before := to_jsonb(OLD);
END IF;
```

Referencing `NEW` in a DELETE branch would raise at runtime — hence the branch.

### 4.3 Finding auto-population

```sql
CREATE TRIGGER trg_finding_before_insert
    BEFORE INSERT ON finding
    FOR EACH ROW EXECUTE FUNCTION fn_finding_before_insert();
```

Sets: `code` (if blank), `due_at` (if NULL), `risk_score`.

## 5. Setting the audit actor

The trigger reads `current_setting('idrm.actor', true)`:

```sql
SELECT set_config('idrm.actor', 'alice', true);
```

The third argument `true` = **transaction-local**. Without it, the setting would
persist on the pooled connection and misattribute the next user's changes.

From Python:

```python
db.session.execute(text("SELECT set_config('idrm.actor', :a, true)"), {"a": username})
```

## 6. Common queries

### Open findings, worst first

```sql
SELECT f.code, f.severity, f.title, i.display_name
  FROM finding f
  LEFT JOIN identity i ON i.id = f.identity_id
 WHERE f.status IN ('open','in_review')
 ORDER BY fn_severity_points(f.severity) DESC, f.detected_at DESC;
```

### Terminated identities still holding active access

```sql
SELECT i.external_ref, i.display_name, sa.code AS system, e.code AS entitlement
  FROM identity i
  JOIN account      a  ON a.identity_id = i.id
  JOIN access_grant g  ON g.account_id  = a.id AND g.state = 'active'
  JOIN entitlement  e  ON e.id          = g.entitlement_id
  JOIN system_app   sa ON sa.id         = a.system_id
 WHERE i.employment_status = 'terminated'
 ORDER BY sa.code, i.display_name;
```

### Segregation-of-duties conflicts

```sql
SELECT i.display_name, sa.code,
       ea.code AS entitlement_a, eb.code AS entitlement_b, sr.description
  FROM sod_rule sr
  JOIN system_app  sa ON sa.id = sr.system_id
  JOIN entitlement ea ON ea.id = sr.entitlement_a_id
  JOIN entitlement eb ON eb.id = sr.entitlement_b_id
  JOIN access_grant g1 ON g1.entitlement_id = ea.id AND g1.state = 'active'
  JOIN access_grant g2 ON g2.entitlement_id = eb.id AND g2.state = 'active'
  JOIN account  a ON a.id = g1.account_id AND a.id = g2.account_id
  JOIN identity i ON i.id = a.identity_id
 WHERE sr.is_active;
```

### Privileged accounts without MFA

```sql
SELECT sa.code, a.username, i.display_name
  FROM account a
  JOIN system_app sa ON sa.id = a.system_id
  JOIN identity   i  ON i.id  = a.identity_id
 WHERE a.account_type = 'privileged'
   AND a.status = 'active'
   AND a.mfa_enabled = FALSE;
```

### What changed on a finding?

```sql
SELECT event_time, actor_username, action,
       before_state->>'status' AS was,
       after_state->>'status'  AS now
  FROM audit_event
 WHERE entity_type = 'finding' AND entity_id = 17
 ORDER BY event_time;
```

### Who did what in the last 24 hours?

```sql
SELECT event_time, actor_username, actor_ip, event_type, entity_type, message
  FROM audit_event
 WHERE event_time > now() - INTERVAL '24 hours'
 ORDER BY event_time DESC;
```

### Prove the audit table is immutable

```sql
UPDATE audit_event SET message = 'tampered' WHERE id = 1;
-- UPDATE 0
SELECT message FROM audit_event WHERE id = 1;
-- original value, unchanged
```

## 7. Index strategy

| Query pattern | Index |
|---|---|
| Dashboard severity counts | `ix_finding_status_sev (status, severity)` |
| Overdue findings | `ix_finding_due` (partial: `WHERE status IN ('open','in_review')`) |
| Identity leaderboard | `ix_identity_risk (risk_score DESC)` |
| Grant expiry sweep | `ix_grant_expires` (partial: `WHERE state='active'`) |
| Audit trail browsing | `ix_audit_time (event_time DESC)` |
| Entity history | `ix_audit_entity (entity_type, entity_id)` |
| Name search | `ix_identity_name_trgm` (GIN, `pg_trgm`) |
| JSONB field search | `ix_audit_after_gin` (GIN, `jsonb_path_ops`) |
| Dormancy sweep | `ix_account_last_login` (partial: `WHERE status='active'`) |

### Why partial indexes matter

`ix_finding_due` only indexes open findings. Overdue queries only ever look at
open findings, so the index is a fraction of the size of a full index and stays
hot in cache.

## 8. Performance notes

### Current scale expectations

| Table | v1 target | Notes |
|---|---|---|
| `identity` | 10⁵ | |
| `account` | 3 × 10⁵ | |
| `access_grant` | 10⁶ | largest table |
| `finding` | 10⁴ active, 10⁶ lifetime | archive closed findings annually |
| `audit_event` | 10⁷/year | partition by month beyond 10⁷ |

### When you outgrow v1

**Partition the audit table by month:**

```sql
CREATE TABLE audit_event (
    ...
) PARTITION BY RANGE (event_time);

CREATE TABLE audit_event_2025_01 PARTITION OF audit_event
    FOR VALUES FROM ('2025-01-01') TO ('2025-02-01');
```

**Archive closed findings:**

```sql
CREATE TABLE finding_archive (LIKE finding INCLUDING ALL);
INSERT INTO finding_archive
SELECT * FROM finding
 WHERE status IN ('closed','false_positive')
   AND updated_at < now() - INTERVAL '2 years';
DELETE FROM finding
 WHERE status IN ('closed','false_positive')
   AND updated_at < now() - INTERVAL '2 years';
```

**Materialise the KPI view if the dashboard gets slow:**

```sql
CREATE MATERIALIZED VIEW mv_kpi AS SELECT ...;
CREATE UNIQUE INDEX ON mv_kpi (id);
-- refresh after each scan
REFRESH MATERIALIZED VIEW CONCURRENTLY mv_kpi;
```

## 9. Backup and restore

### Logical dump

```bash
make dump
# → backups/idrm_20250115_143022.sql
```

### Restore

```bash
psql -h localhost -U idrm -d idrm -f backups/idrm_20250115_143022.sql
```

### Continuous archiving (production)

Use `pgBackRest` or WAL-G with `archive_mode = on`. Target: RPO ≤ 5 minutes,
RTO ≤ 30 minutes.

### Verify a backup restored correctly

```sql
SELECT count(*) FROM audit_event;
SELECT count(*) FROM finding WHERE status IN ('open','in_review');
SELECT fn_recompute_all_risk_scores();
```

## 10. Housekeeping jobs

| Job | Frequency | Command |
|---|---|---|
| Expire stale grants | hourly | `SELECT fn_expire_stale_grants();` |
| Recompute risk scores | after each scan | `SELECT fn_recompute_all_risk_scores();` |
| `VACUUM ANALYZE` | nightly | `VACUUM ANALYZE;` |
| Audit partition rollover | monthly | see §8 |
| Finding archive | annually | see §8 |

## 11. Role and privilege model

```sql
-- Application role: read/write on data, no DDL
CREATE ROLE idrm_app LOGIN PASSWORD '...';
GRANT CONNECT ON DATABASE idrm TO idrm_app;
GRANT USAGE ON SCHEMA public TO idrm_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO idrm_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO idrm_app;

-- Auditor role: read-only, everywhere
CREATE ROLE idrm_auditor LOGIN PASSWORD '...';
GRANT CONNECT ON DATABASE idrm TO idrm_auditor;
GRANT USAGE ON SCHEMA public TO idrm_auditor;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO idrm_auditor;

-- Explicitly deny audit tampering (belt and braces)
REVOKE UPDATE, DELETE ON audit_event FROM idrm_app;
```

## 12. Next

→ [Admin Guide](06-admin-guide.md)

