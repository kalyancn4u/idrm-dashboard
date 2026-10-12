# Testing Guide

## 1. Running the tests

```bash
make test          # SQLite, fast, no infrastructure
make test-pg       # Postgres, includes trigger tests
```

Or directly:

```bash
.venv/bin/pytest -q
.venv/bin/pytest -v tests/test_rbac.py
.venv/bin/pytest -k "rbac"
.venv/bin/pytest -m pg            # only Postgres-marked tests
.venv/bin/pytest --cov=app        # coverage
```

## 2. Test database strategy

| Mode | Database | What it covers |
|---|---|---|
| Default | SQLite in-memory | Models, RBAC, services that don't need PL/pgSQL |
| `IDRM_TEST_DATABASE_URL` set | PostgreSQL | Everything, including triggers and immutability rules |

```bash
IDRM_TEST_DATABASE_URL="postgresql+psycopg2://idrm:idrm@localhost:5432/idrm_test" \
  make test-pg
```

Create the test database first:

```bash
createdb -h localhost -U idrm idrm_test
```

## 3. Test layout

| File | Covers |
|---|---|
| `conftest.py` | `app`, `client`, `db`, `runner` fixtures; minimal seed |
| `test_models.py` | Model helpers: `is_admin`, `can_write`, `initials`, `risk_band`, `is_terminated` |
| `test_rbac.py` | Anonymous redirects, role 403s, permission matrix |
| `test_risk_engine.py` | Registry completeness, severity points, Postgres scan |
| `test_api.py` | Health, auth gates, response envelopes, 403 shape |

## 4. Fixtures

```python
@pytest.fixture(scope="session")
def app():
    application = create_app("testing")
    with application.app_context():
        db.create_all()
        _seed_minimal(db)
        yield application
        db.session.remove()
        db.drop_all()

@pytest.fixture()
def client(app):
    return app.test_client()
```

`_seed_minimal` inserts 3 users, 1 system, 2 identities — just enough to
exercise every model without making tests slow.

## 5. Writing a test

### A model test

```python
def test_identity_risk_band(app):
    with app.app_context():
        person = Identity.query.filter_by(external_ref="T001").first()
        person.risk_score = 72
        assert person.risk_band == "critical"
```

### An RBAC test

```python
@pytest.mark.rbac
def test_auditor_forbidden_from_admin(client, app):
    with app.app_context():
        _login(client, "testauditor")
    assert client.get("/admin/").status_code == 403
```

### An API test

```python
def test_findings_pagination_envelope(client, app):
    _login(client, app, "testadmin")
    resp = client.get("/api/v1/findings?page=1&per_page=5")
    payload = resp.get_json()
    assert set(payload) >= {"page", "per_page", "count", "items"}
```

### A Postgres-only test

```python
@pytest.mark.pg
def test_audit_table_is_immutable(app):
    with app.app_context():
        db.session.execute(text(
            "INSERT INTO audit_event (event_type, action) VALUES ('TEST','test')"
        ))
        db.session.commit()

        result = db.session.execute(text(
            "UPDATE audit_event SET message='tampered' WHERE event_type='TEST'"
        ))
        assert result.rowcount == 0
```

## 6. Markers

| Marker | Meaning |
|---|---|
| `pg` | Requires a real PostgreSQL instance |
| `slow` | Takes more than a second |
| `rbac` | Role-based access control |

Run without a marker: `pytest -m "not pg"`.

## 7. What's well covered vs. not

### Well covered
- Role/permission logic
- Model-derived properties
- API response shapes
- Authentication gating

### Thinly covered (add as needed)
- The full risk engine against real data
- Template rendering
- CSV export content
- Concurrency

### Not covered in v1
- Load testing
- Browser/E2E tests
- Fuzzing

## 8. Smoke test

```bash
make run &                    # in one shell
BASE_URL=http://127.0.0.1:5000 bash scripts/smoke.sh
```

Checks 9 endpoints: 3 public 200s, 3 auth redirects, plus a summary line.

## 9. CI pipeline sketch

```yaml
# .github/workflows/ci.yml
name: CI
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16-alpine
        env:
          POSTGRES_USER: idrm
          POSTGRES_PASSWORD: idrm
          POSTGRES_DB: idrm_test
        ports: ['5432:5432']
        options: >-
          --health-cmd pg_isready --health-interval 5s
          --health-timeout 5s --health-retries 10

    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.12' }

      - run: make install
      - run: make lint
      - run: make test
      - run: make test-pg
        env:
          IDRM_TEST_DATABASE_URL: postgresql+psycopg2://idrm:idrm@localhost:5432/idrm_test
```

## 10. Debugging a failing test

```bash
# Full traceback
.venv/bin/pytest tests/test_rbac.py::test_auditor_forbidden_from_admin -vv

# Drop into pdb on failure
.venv/bin/pytest --pdb

# Show print() output
.venv/bin/pytest -s
```

Common causes:

| Symptom | Cause |
|---|---|
| `no such table` | `db.create_all()` didn't run — check the `app` fixture scope |
| `RuntimeError: working outside app context` | Wrap in `with app.app_context():` |
| 403 where 200 expected | Test logged in as the wrong role |
| `fn_severity_points does not exist` | Running on SQLite; mark the test `@pytest.mark.pg` |

## 11. Next

→ [Troubleshooting & FAQ](13-troubleshooting-faq.md)

