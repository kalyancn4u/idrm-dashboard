"""Authentication routes."""

from __future__ import annotations

from datetime import datetime, timezone

from flask import (
    Blueprint,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy import text

from app.extensions import db
from app.models.user import AppUser
from app.services.audit_service import log_event, set_actor_context

auth_bp = Blueprint("auth", __name__, template_folder="../templates")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    if request.method == "POST":
        username = (request.form.get("username") or "").strip().lower()
        password = request.form.get("password") or ""
        remember = bool(request.form.get("remember"))

        user: AppUser | None = db.session.execute(
            text(
                "SELECT * FROM app_user WHERE lower(username) = :u OR lower(email) = :u LIMIT 1"
            ),
            {"u": username},
        ).mappings().first()

        user = AppUser.query.filter(
            (AppUser.username == username) | (AppUser.email == username)
        ).first()

        if user is None or not user.check_password(password):
            log_event(
                "LOGIN_FAILED",
                "Failed sign-in attempt",
                entity_type="app_user",
                entity_id=getattr(user, "id", None),
                severity="warning",
                message=f"Failed sign-in for '{username}'",
                flush=True,
            )
            flash("Invalid credentials. Please try again.", "error")
            return render_template("auth/login.html"), 401

        if not user.is_active:
            flash("This account is disabled. Contact your administrator.", "error")
            return render_template("auth/login.html"), 403

        login_user(user, remember=remember)
        user.last_login_at = datetime.now(timezone.utc)
        user.failed_logins = 0
        db.session.commit()

        set_actor_context(user.username)
        log_event(
            "LOGIN",
            "User signed in",
            entity_type="app_user",
            entity_id=user.id,
            message=f"{user.username} signed in as {user.role}",
            flush=True,
        )

        nxt = request.args.get("next")
        if nxt and nxt.startswith("/"):
            return redirect(nxt)
        return redirect(url_for("main.dashboard"))

    return render_template("auth/login.html")


@auth_bp.route("/logout")
@login_required
def logout():
    log_event(
        "LOGOUT",
        "User signed out",
        entity_type="app_user",
        entity_id=current_user.id,
        flush=True,
    )
    logout_user()
    flash("You have been signed out.", "success")
    return redirect(url_for("auth.login"))
