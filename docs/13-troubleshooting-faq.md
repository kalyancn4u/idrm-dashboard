# Troubleshooting & FAQ

## Installation

### `make db-up` fails — "Cannot connect to the Docker daemon"

Docker Desktop isn't running, or you don't have Docker.

```bash
# Start Docker, or use a native Postgres:
sudo -u postgres psql -c "CREATE ROLE idrm LOGIN PASSWORD 'idrm';"
sudo -u postgres psql -c "CREATE DATABASE idrm OWNER idrm;"
make migrate seed passwords
```

### `psycopg2.OperationalError: could not connect to server`

```bash
# Is Postgres running?
pg_isready -h localhost -p 5432
docker compose ps

# Can you connect manually?
psql -h localhost -U idrm -d idrm -c 'SELECT 1;'

# Does DATABASE_URL match?
grep DATABASE_URL .env
```

Common mismatch: `.env` says `PGPORT=5432` but `DATABASE_URL` says `:5433`.

### `FATAL: password authentication failed for user "idrm"`

```bash
# Reset the role password
sudo -u postgres psql -c "ALTER ROLE idrm PASSWORD 'idrm';"
```

Then confirm `PGPASSWORD` and `DATABASE_URL` agree.

### `ModuleNotFoundError: No module named 'flask'`

The venv isn't active, or dependencies weren't installed.

```bash
make install
.venv/bin/python -c "import flask; print(flask.__version__)"
```

`make` targets use `.venv/bin/…` explicitly, so activation isn't required — but
a bare `python run.py` needs it.

## Database

### `make migrate` fails with `relation "audit_event" does not exist`

The files ran out of order. `02_functions_triggers.sql` references `audit_event`,
which `01_schema.sql` creates.

```bash
make db-reset     # rebuilds in the correct order
```

### `UPDATE audit_event` returns `UPDATE 0`

That's the immutability rule working. To modify an audit row you must drop the rule:

```sql
DROP RULE audit_event_no_update ON audit_event;
-- ... your change ...
CREATE RULE audit_event_no_update AS ON UPDATE TO audit_event DO INSTEAD NOTHING;
```

Do not do this in production.

### Risk scores are all zero

```bash
make risk-scan
# or
psql -U idrm -d idrm -c "SELECT fn_recompute_all_risk_scores();"
```

Scores only count findings in `open` or `in_review`.

### `fn_recompute_all_risk_scores()` returns 0

Either all scores are already correct (idempotent), or there are no findings.

```sql
SELECT count(*) FROM finding WHERE status IN ('open','in_review');
```

### Seeded users can't log in

`password_hash` is still `'PLACEHOLDER'`.

```bash
make passwords
```

Verify:

```sql
SELECT username, left(password_hash, 12) FROM app_user;
-- Expect 'pbkdf2:sha256' not 'PLACEHOLDER'
```

## Application

### `RuntimeError: SECRET_KEY must be set to a strong random value in production`

`ProductionConfig.__init__` refuses to boot with the dev placeholder.

```bash
python -c "import secrets; print(secrets.token_hex(32))"
# Paste into .env as SECRET_KEY
```

### Login redirects back to the login page in a loop

Cookie settings. In production, `SESSION_COOKIE_SECURE=1` requires HTTPS.

```bash
# Behind a TLS proxy with plain HTTP internally:
SESSION_COOKIE_SECURE=0
```

Also check `ProxyFix` if you're behind a reverse proxy that terminates TLS:

```python
from werkzeug.middleware.proxy_fix import ProxyFix
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
```

### 403 on every page after logging in

Check the role:

```sql
SELECT username, role FROM app_user WHERE username = 'auditor';
```

An `auditor` cannot access `/admin/*`. That's the design.

### The dashboard is empty

```bash
make stats        # are there rows?
make seed         # if not
make risk-scan    # to generate findings
```

### Risk scan runs but creates zero findings

The estate may genuinely be clean. Verify with a direct query:

```sql
SELECT count(*)
  FROM identity i
  JOIN account a ON a.identity_id = i.id
  JOIN access_grant g ON g.account_id = a.id
 WHERE i.employment_status = 'terminated' AND g.state = 'active';
```

If that returns > 0 but `RR-COMP-001` has no open finding, the registry is missing
an entry:

```python
from app.services.risk_engine import REGISTRY
print(sorted(REGISTRY.keys()))
```

### `UndefinedError: 'csrf_token' is undefined`

A form is missing the CSRF input, or the template isn't extending `base.html`.
Every POST form needs:

```html
<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
```

### Styles look broken / unstyled

```bash
ls app/static/css/design-system.css    # exists?
curl -I http://localhost:5000/static/css/design-system.css
```

If the CSP blocks it, check the browser console. The CSP allows `'self'` for styles.

## Performance

### The findings page takes 5+ seconds

```sql
ANALYZE finding;
SELECT count(*) FROM finding;
EXPLAIN ANALYZE
SELECT * FROM finding WHERE status IN ('open','in_review')
 ORDER BY detected_at DESC LIMIT 25;
```

Look for `Seq Scan`. If present, the index isn't being used:

```sql
REINDEX INDEX ix_finding_status_sev;
```

### The audit trail is slow to browse

After 10⁷ rows, partition by month (see the DB guide §8).

```sql
SELECT pg_size_pretty(pg_total_relation_size('audit_event'));
```

## FAQ

**Q: Why two consoles instead of one with a role toggle?**
A: Because the auditor's read-only guarantee must be structural. A toggle can be
flipped by a bug or a crafted request; a separate blueprint with a hard
`@roles_required` cannot.

**Q: Why not delete revoked grants instead of setting `state = 'revoked'`?**
A: History. "Who had this access in March?" is answerable only if the row survives.

**Q: Why is the audit table not in a separate database?**
A: Because the audit row must be written in the same transaction as the change it
describes. A separate database means a distributed transaction, which means
either 2PC or an eventual-consistency gap. Neither is acceptable for an audit trail.

**Q: Can I use MySQL?**
A: Not without changes. The immutability rules (`CREATE RULE ... DO INSTEAD NOTHING`)
and the `INET` type are PostgreSQL-specific.

**Q: How do I add a new risk rule?**
A: Two steps. (1) Insert a row into `risk_rule` with a new code. (2) Add a
function to `risk_engine.py` decorated with `@rule("RR-XXX-000")`.

**Q: How do I add a new SoD pair?**
A: One step. Insert a row into `sod_rule`. No code change — `RR-SOD-001` reads
the table.

**Q: Why does `risk_score` cap at 100?**
A: So it reads as a percentage-like band. The raw sum could reach 300+ for a
badly-compromised identity, which is meaningless to a human.

**Q: Where are the passwords?**
A: In `.env` for the database, and PBKDF2 hashes in `app_user.password_hash`.
The demo passwords are documented in the README and are for development only.

**Q: Can I run this without Docker?**
A: Yes. Install PostgreSQL natively and run `make db-create migrate seed passwords`.

**Q: Can I run this without PostgreSQL?**
A: Not in production. The tests run on SQLite, but triggers, `JSONB`, `INET` and
the immutability rules are Postgres-only. The app will partially function but
the audit trail will not.

**Q: Is there an OpenAPI spec?**
A: Not yet. See `docs/09-api-reference.md` for the current contract.

**Q: How do I contribute a new export?**
A: Add a function to `app/services/reporting.py` returning a CSV string, then
add an entry to the `builders` dict in `auditor.export_csv`. It's automatically
audit-logged.

## Getting more help

```bash
make help          # all targets
make db-info       # connection + row counts
make routes        # every registered route
tail -f logs/idrm.log
```
