# Operations Runbook

## 1. Deployment

### Development

```bash
make setup
make run          # http://127.0.0.1:5000
```

### Production (reference)

```bash
# 1. Build
docker build -t idrm:1.0.0 .

# 2. Provide configuration
cp .env.example .env
$EDITOR .env      # set SECRET_KEY, DATABASE_URL, SESSION_COOKIE_SECURE=1

# 3. Run behind TLS
docker run -d --name idrm \
  --env-file .env \
  -p 8000:8000 \
  --restart unless-stopped \
  idrm:1.0.0
```

Gunicorn: 4 workers × 4 threads. Tune with `WEB_CONCURRENCY` based on
`(2 × CPU cores) + 1`.

### Post-deploy verification

```bash
curl -fsS https://idrm.example.com/healthz | jq
BASE_URL=https://idrm.example.com bash scripts/smoke.sh
```

## 2. Configuration reference

| Variable | Required | Default | Notes |
|---|---|---|---|
| `SECRET_KEY` | **prod** | dev placeholder | `openssl rand -hex 32` |
| `DATABASE_URL` | yes | `postgresql+psycopg2://idrm:idrm@localhost:5432/idrm` | |
| `REDIS_URL` | no | empty | enables Redis cache |
| `SESSION_COOKIE_SECURE` | prod | `0` | set to `1` behind HTTPS |
| `SESSION_LIFETIME_MINUTES` | no | 480 | |
| `IDRM_DORMANCY_DAYS` | no | 90 | dormancy detection window |
| `IDRM_SLA_CRITICAL_DAYS` | no | 7 | |
| `IDRM_SLA_HIGH_DAYS` | no | 14 | |
| `IDRM_SLA_MEDIUM_DAYS` | no | 30 | |
| `IDRM_SLA_LOW_DAYS` | no | 90 | |
| `IDRM_RUN_SCAN_ON_BOOT` | no | `0` | dev convenience |

`ProductionConfig.__init__` raises if `SECRET_KEY` is still the dev placeholder.

## 3. Backup

### Nightly logical dump

```bash
# crontab
0 2 * * * cd /opt/idrm && make dump && find backups -name '*.sql' -mtime +30 -delete
```

### Restore

```bash
psql -h $PGHOST -U $PGUSER -d idrm -f backups/idrm_20250115_020001.sql
```

### Verify the restore

```sql
SELECT count(*) FROM identity;
SELECT count(*) FROM access_grant WHERE state = 'active';
SELECT count(*) FROM finding WHERE status IN ('open','in_review');
SELECT count(*) FROM audit_event;
SELECT fn_recompute_all_risk_scores();
```

### RPO / RTO

| Metric | Logical dump | WAL archiving (pgBackRest) |
|---|---|---|
| RPO | 24 h | ≤ 5 min |
| RTO | 30–60 min | ≤ 30 min |

Use WAL archiving for production.

## 4. Monitoring

### Health endpoint

```bash
curl -fsS https://idrm.example.com/healthz
```

Returns 200 with `{"status":"ok"}` or 503 with `{"status":"degraded"}`.

### Metrics worth alerting on

| Metric | Warning | Critical |
|---|---|---|
| `findings_open` | > 50 | > 100 |
| `findings_overdue` | > 10 | > 25 |
| `findings_critical` (open) | > 5 | > 10 |
| Last successful scan age | > 26 h | > 50 h |
| `/healthz` response time | > 500 ms | > 2 s |
| DB connection pool saturation | > 80% | > 95% |
| Disk used by `audit_event` | > 100 GB | > 200 GB |

### Log locations

| Log | Path |
|---|---|
| Application | `logs/idrm.log` (rotating, 5 MB × 5) |
| Gunicorn access | stdout |
| PostgreSQL | `/var/log/postgresql/` |

## 5. Scheduled jobs

| Job | Frequency | Command |
|---|---|---|
| Risk scan | hourly or daily | `flask --app run.py risk-scan` |
| Expire stale grants | hourly | `SELECT fn_expire_stale_grants();` |
| Recompute risk scores | after each scan | `SELECT fn_recompute_all_risk_scores();` |
| Audit export | weekly | `make export-audit` |
| `VACUUM ANALYZE` | nightly | `VACUUM ANALYZE;` |
| Backup | nightly | `make dump` |

### Crontab

```cron
# Scan every hour
0 * * * * cd /opt/idrm && .venv/bin/flask --app run.py risk-scan >> logs/scan.log 2>&1

# Backup at 02:00
0 2 * * * cd /opt/idrm && make dump

# Vacuum at 03:00
0 3 * * * psql -U idrm -d idrm -c "VACUUM ANALYZE;"

# Weekly audit export, Mondays at 06:00
0 6 * * 1 cd /opt/idrm && make export-audit
```

## 6. Scaling

| Symptom | Fix |
|---|---|
| High CPU on the app tier | Add Gunicorn workers (stateless; scale horizontally behind a LB) |
| Slow dashboards | `REFRESH MATERIALIZED VIEW CONCURRENTLY mv_kpi` after each scan |
| Slow audit browsing | Partition `audit_event` by month |
| Slow identity search | Confirm `pg_trgm` indexes are being used (`EXPLAIN ANALYZE`) |
| Connection pool exhaustion | Raise `SQLALCHEMY_POOL_SIZE` / add PgBouncer |
| Large audit table | Archive > 2 years to cold storage |

## 7. Incident playbook

### "The dashboard is slow"

```sql
-- 1. Find long-running queries
SELECT pid, now() - query_start AS duration, query
  FROM pg_stat_activity
 WHERE state = 'active' AND query NOT ILIKE '%pg_stat_activity%'
 ORDER BY duration DESC;

-- 2. Check for missing indexes
SELECT relname, seq_scan, idx_scan
  FROM pg_stat_user_tables
 WHERE seq_scan > idx_scan AND seq_scan > 1000
 ORDER BY seq_scan DESC;

-- 3. Kill a runaway query
SELECT pg_cancel_backend(<pid>);
```

### "Findings stopped appearing"

1. Check the last scan: `/admin/` → Last Risk Scan panel.
2. If `status = 'failed'`, read `scan_run.error_text`.
3. If the scan succeeded with `findings_created = 0`, that may be correct.
   Verify by checking a known-bad condition:
   ```sql
   SELECT count(*) FROM identity
    WHERE employment_status = 'terminated'
      AND id IN (SELECT a.identity_id FROM account a
                  JOIN access_grant g ON g.account_id = a.id
                 WHERE g.state = 'active');
   ```
   If that's > 0 but no `RR-COMP-001` finding exists, the engine is broken.

### "The audit trail has a gap"

1. Compare `audit_event.event_time` maxima against `scan_run.started_at`.
2. Check the app log for `Audit flush failed`.
3. Confirm the triggers still exist:
   ```sql
   SELECT tgname, tgrelid::regclass
     FROM pg_trigger
    WHERE tgname LIKE 'trg_audit_%';
   ```
   Expect 7 rows.

### "Users cannot log in"

```sql
-- Is the account locked or inactive?
SELECT username, is_active, failed_logins, locked_until FROM app_user;

-- Does the password hash look right?
SELECT username, left(password_hash, 20) FROM app_user;
-- 'PLACEHOLDER' means `make passwords` was never run
```

## 8. Upgrade procedure

```bash
# 1. Back up
make dump

# 2. Pull
git pull

# 3. Update dependencies
make install

# 4. Apply schema changes (idempotent)
make migrate

# 5. Run tests
make test

# 6. Restart
systemctl restart idrm     # or docker restart idrm

# 7. Verify
curl -fsS https://idrm.example.com/healthz | jq
```

### Rolling back

```bash
git checkout <previous-tag>
make install
psql -U idrm -d idrm -f backups/<pre-upgrade-dump>.sql
systemctl restart idrm
```

## 9. Security operations

| Task | Frequency | Command |
|---|---|---|
| Rotate `SECRET_KEY` | quarterly | update `.env`, restart (invalidates sessions) |
| Rotate DB password | quarterly | `ALTER ROLE idrm PASSWORD '...'` |
| Review `admin` accounts | monthly | `SELECT * FROM app_user WHERE role='admin';` |
| Verify audit immutability | monthly | `UPDATE audit_event SET message='x'; -- expect UPDATE 0` |
| Review `accepted_risk` findings | monthly | `/admin/findings?status=accepted_risk` |

## 10. Disaster recovery

**Scenario: the database host is gone.**

1. Provision a new Postgres instance.
2. Restore the most recent backup:
   ```bash
   psql -h newhost -U idrm -d idrm -f backups/idrm_latest.sql
   ```
3. Replay WAL if using continuous archiving.
4. Update `DATABASE_URL`, restart the app.
5. Verify: `make stats`, then log in and check the dashboard.
6. Record the incident. The gap between the last backup and the failure is
   permanent data loss — document it.

**Scenario: the app tier is gone.**

The app is stateless. Provision a new container from the same image, point it at
the same database, restart. Sessions are lost; users log in again.

## 11. Next

→ [Security & Compliance](11-security-and-compliance.md)

