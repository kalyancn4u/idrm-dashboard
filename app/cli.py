"""
IDRM — custom Flask CLI commands.

    flask --app run.py init-db
    flask --app run.py seed-users
    flask --app run.py risk-scan
    flask --app run.py export-audit --out exports/audit.csv
    flask --app run.py demo-reset
"""

from __future__ import annotations

import csv
import sys
from datetime import datetime, timezone
from pathlib import Path

import click
from flask import Flask
from flask.cli import with_appcontext
from werkzeug.security import generate_password_hash

from app.extensions import db

# ---------------------------------------------------------------------------
# Demo passwords.  Documented in README + docs/01-getting-started.md.
# ---------------------------------------------------------------------------
DEMO_PASSWORDS = {
    "admin": "Admin#2025",
    "auditor": "Audit#2025",
    "analyst": "Analyze#2025",
    "viewer": "View#2025",
}

SQL_DIR = Path(__file__).resolve().parent.parent / "sql"


def register_cli(app: Flask) -> None:
    app.cli.add_command(init_db)
    app.cli.add_command(seed_users)
    app.cli.add_command(risk_scan)
    app.cli.add_command(export_audit)
    app.cli.add_command(demo_reset)
    app.cli.add_command(db_info)


# ===========================================================================
# init-db
# ===========================================================================
@click.command("init-db")
@click.option("--seed/--no-seed", default=True, help="Load sample data after schema.")
@with_appcontext
def init_db(seed: bool) -> None:
    """Apply sql/*.sql in order (schema → functions → indexes → data)."""
    files = [
        "01_schema.sql",
        "02_functions_triggers.sql",
        "03_indexes.sql",
    ]
    if seed:
        files += ["04_seed_reference.sql", "05_seed_sample.sql"]

    _run_sql_files(files)
    click.secho("✔ Database initialised.", fg="green")


# ===========================================================================
# seed-users
# ===========================================================================
@click.command("seed-users")
@with_appcontext
def seed_users() -> None:
    """Set real password hashes for the four demo console users."""
    from sqlalchemy import text

    updated = 0
    for username, password in DEMO_PASSWORDS.items():
        result = db.session.execute(
            text(
                "UPDATE app_user SET password_hash = :h, updated_at = now() "
                "WHERE username = :u"
            ),
            {"h": generate_password_hash(password, method="pbkdf2:sha256:600000"), "u": username},
        )
        updated += result.rowcount or 0

    db.session.commit()

    if updated == 0:
        click.secho(
            "⚠  No demo users found. Did you run `make seed` first?", fg="yellow"
        )
        return

    click.secho(f"✔ Passwords set for {updated} user(s).", fg="green")
    click.echo("")
    click.secho("  Demo credentials", bold=True)
    for username, password in DEMO_PASSWORDS.items():
        click.echo(f"    {username:<9} / {password}")


# ===========================================================================
# risk-scan
# ===========================================================================
@click.command("risk-scan")
@click.option("--verbose", is_flag=True, help="Print per-rule hit counts.")
@with_appcontext
def risk_scan(verbose: bool) -> None:
    """Run the risk engine and refresh identity risk scores."""
    from app.services.risk_engine import run_full_scan

    click.echo("Running risk scan…")
    result = run_full_scan(trigger_source="manual")

    if verbose:
        for rule, count in sorted(result["by_rule"].items()):
            click.echo(f"  {rule:<14} {count:>4} finding(s)")

    click.secho(
        f"✔ Scan #{result['scan_id']} complete — "
        f"{result['rules_evaluated']} rules, "
        f"{result['findings_created']} new, "
        f"{result['findings_closed']} auto-closed, "
        f"{result['identities_rescored']} identities rescored "
        f"in {result['duration_s']:.2f}s.",
        fg="green",
    )


# ===========================================================================
# export-audit
# ===========================================================================
@click.command("export-audit")
@click.option("--out", required=True, help="Destination CSV path.")
@click.option("--limit", default=100_000, show_default=True, help="Max rows.")
@with_appcontext
def export_audit(out: str, limit: int) -> None:
    """Stream the full audit trail to CSV."""
    from sqlalchemy import text

    rows = db.session.execute(
        text(
            """
            SELECT id, event_time, actor_username, actor_ip, event_type,
                   entity_type, entity_id, action, severity, message
              FROM audit_event
             ORDER BY event_time DESC
             LIMIT :lim
            """
        ),
        {"lim": limit},
    ).mappings()

    path = Path(out)
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(
            [
                "id",
                "event_time",
                "actor_username",
                "actor_ip",
                "event_type",
                "entity_type",
                "entity_id",
                "action",
                "severity",
                "message",
            ]
        )
        n = 0
        for r in rows:
            writer.writerow([r[c] for c in writer.fieldnames if False] or list(r.values()))
            n += 1

    click.secho(f"✔ Wrote {n} audit events to {path}", fg="green")


# ===========================================================================
# demo-reset
# ===========================================================================
@click.command("demo-reset")
@click.option("--yes", is_flag=True, help="Skip the confirmation prompt.")
@with_appcontext
def demo_reset(yes: bool) -> None:
    """Drop everything and rebuild with fresh sample data."""
    if not yes:
        click.confirm("This drops all IDRM tables. Continue?", abort=True)

    _run_sql_files(["99_reset.sql"])
    _run_sql_files(
        [
            "01_schema.sql",
            "02_functions_triggers.sql",
            "03_indexes.sql",
            "04_seed_reference.sql",
            "05_seed_sample.sql",
        ]
    )
    seed_users.callback()  # type: ignore[attr-defined]
    click.secho("✔ Demo database reset.", fg="green")


# ===========================================================================
# db-info
# ===========================================================================
@click.command("db-info")
@with_appcontext
def db_info() -> None:
    """Print the effective database URL and row counts."""
    from sqlalchemy import text

    from app.extensions import db as _db

    url = _db.engine.url
    safe = url.render_as_string(hide_password=True)
    click.secho(f"Database : {safe}", fg="cyan")

    tables = [
        "app_user",
        "system_app",
        "identity",
        "account",
        "entitlement",
        "access_grant",
        "risk_rule",
        "sod_rule",
        "finding",
        "evidence",
        "review_campaign",
        "review_item",
        "audit_event",
        "scan_run",
    ]
    click.secho(f"{'table':<20} {'rows':>10}", bold=True)
    click.echo("-" * 32)
    for t in tables:
        try:
            n = db.session.execute(text(f"SELECT count(*) FROM {t}")).scalar_one()
            click.echo(f"{t:<20} {n:>10}")
        except Exception:
            click.echo(f"{t:<20} {'—':>10}")


# ===========================================================================
# helpers
# ===========================================================================
def _run_sql_files(filenames: list[str]) -> None:
    """Execute SQL files against the current engine, splitting on statements."""
    from sqlalchemy import text

    for name in filenames:
        path = SQL_DIR / name
        if not path.exists():
            click.secho(f"  ⚠  missing {path}", fg="yellow")
            continue

        click.echo(f"  → {name}")
        sql = path.read_text(encoding="utf-8")

        # SQLAlchemy's text() cannot run multi-statement scripts portably, so we
        # hand the raw string to the DBAPI driver via exec_driver_sql.
        try:
            db.session.execute(text("SELECT 1"))  # sanity
            raw = db.session.connection().connection
            with raw.cursor() as cur:
                cur.execute(sql)
            raw.commit()
        except Exception as exc:
            db.session.rollback()
            click.secho(f"  ✗ {name} failed: {exc}", fg="red", err=True)
            sys.exit(1)

    db.session.commit()
