"""Landing, health and shared pages."""

from __future__ import annotations

from flask import Blueprint, jsonify, redirect, render_template, url_for
from flask_login import current_user, login_required
from sqlalchemy import text

from app.extensions import db

main_bp = Blueprint("main", __name__, template_folder="../templates")


@main_bp.route("/")
def index():
    if not current_user.is_authenticated:
        return redirect(url_for("auth.login"))
    return redirect(url_for("main.dashboard"))


@main_bp.route("/dashboard")
@login_required
def dashboard():
    """Route each role to its own home."""
    if current_user.role == "auditor":
        return redirect(url_for("auditor.dashboard"))
    if current_user.role in {"admin", "analyst"}:
        return redirect(url_for("admin.dashboard"))
    return redirect(url_for("auditor.dashboard"))   # viewer → read-only view


@main_bp.route("/healthz")
def healthz():
    """Liveness + readiness probe."""
    db_ok, db_detail = True, "ok"
    try:
        db.session.execute(text("SELECT 1"))
    except Exception as exc:  # pragma: no cover
        db_ok, db_detail = False, str(exc)

    payload = {
        "status": "ok" if db_ok else "degraded",
        "components": {
            "database": {"ok": db_ok, "detail": db_detail},
        },
    }
    return jsonify(payload), (200 if db_ok else 503)


@main_bp.route("/about")
def about():
    return render_template("about.html")
