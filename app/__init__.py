"""
IDRM — application factory.
"""

from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler

from flask import Flask, g, render_template, request
from flask_login import current_user

from app.config import get_config
from app.extensions import build_cache, csrf, db, login_manager
from app.extensions import cache as _cache_placeholder  # noqa: F401


def create_app(config_name: str | None = None) -> Flask:
    app = Flask(__name__, instance_relative_config=False)

    cfg = get_config(config_name)
    app.config.from_object(cfg)
    if isinstance(cfg, type) and config_name == "production":
        cfg()  # triggers the SECRET_KEY guard

    _configure_logging(app)

    # ---- extensions ---------------------------------------------------------
    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    import app.extensions as ext

    ext.cache = build_cache()

    # ---- blueprints ---------------------------------------------------------
    from app.blueprints.admin import admin_bp
    from app.blueprints.api import api_bp
    from app.blueprints.auditor import auditor_bp
    from app.blueprints.auth import auth_bp
    from app.blueprints.main import main_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(auditor_bp, url_prefix="/auditor")
    app.register_blueprint(api_bp, url_prefix="/api/v1")

    # ---- CLI ----------------------------------------------------------------
    from app.cli import register_cli

    register_cli(app)

    # ---- models must be imported so SQLAlchemy sees them ---------------------
    from app import models  # noqa: F401

    # ---- request lifecycle --------------------------------------------------
    _register_request_hooks(app)

    # ---- error handlers -----------------------------------------------------
    _register_error_handlers(app)

    # ---- security headers ---------------------------------------------------
    _register_security_headers(app)

    # ---- optional boot-time scan -------------------------------------------
    if app.config.get("IDRM_RUN_SCAN_ON_BOOT"):
        with app.app_context():
            try:
                from app.services.risk_engine import run_full_scan

                run_full_scan(trigger_source="boot")
                app.logger.info("Boot risk scan completed.")
            except Exception as exc:  # pragma: no cover
                app.logger.warning("Boot risk scan skipped: %s", exc)

    return app


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
def _configure_logging(app: Flask) -> None:
    level = logging.DEBUG if app.config.get("DEBUG") else logging.INFO
    fmt = logging.Formatter(
        "[%(asctime)s] %(levelname)-7s %(name)s :: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    stream = logging.StreamHandler()
    stream.setFormatter(fmt)
    stream.setLevel(level)

    app.logger.handlers.clear()
    app.logger.addHandler(stream)
    app.logger.setLevel(level)

    log_dir = os.path.join(app.root_path, "..", "logs")
    os.makedirs(log_dir, exist_ok=True)
    try:
        fileh = RotatingFileHandler(
            os.path.join(log_dir, "idrm.log"), maxBytes=5_000_000, backupCount=5
        )
        fileh.setFormatter(fmt)
        fileh.setLevel(logging.INFO)
        app.logger.addHandler(fileh)
    except OSError:  # read-only FS
        pass


# ---------------------------------------------------------------------------
# Request hooks
# ---------------------------------------------------------------------------
def _register_request_hooks(app: Flask) -> None:
    @app.before_request
    def _stash_request_context():
        g.request_started = True

    @app.after_request
    def _persist_audit_buffer(response):
        """
        Flush any audit events buffered during the request.

        Services append to ``g.audit_buffer``; we write them here so that a
        failed request does not leave partial audit rows behind.
        """
        buffered = getattr(g, "audit_buffer", None)
        if buffered:
            from app.services.audit_service import flush_buffer

            try:
                flush_buffer(buffered)
            except Exception as exc:  # pragma: no cover
                app.logger.error("Audit flush failed: %s", exc)
            finally:
                g.audit_buffer = []
        return response

    @app.context_processor
    def _inject_globals():
        from datetime import datetime, timezone

        def current_year():
            return datetime.now(timezone.utc).year

        return {
            "app_name": app.config["APP_NAME"],
            "app_tagline": app.config["APP_TAGLINE"],
            "now_utc": datetime.now(timezone.utc),
            "current_year": current_year,
            "nav_active": lambda *prefixes: any(
                request.path.startswith(p) for p in prefixes
            ),
        }


# ---------------------------------------------------------------------------
# Error handlers
# ---------------------------------------------------------------------------
def _register_error_handlers(app: Flask) -> None:
    @app.errorhandler(403)
    def _forbidden(err):  # noqa: ARG001
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def _not_found(err):  # noqa: ARG001
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def _server_error(err):  # noqa: ARG001
        db.session.rollback()
        return render_template("errors/500.html"), 500


# ---------------------------------------------------------------------------
# Security headers
# ---------------------------------------------------------------------------
def _register_security_headers(app: Flask) -> None:
    @app.after_request
    def _headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault(
            "Permissions-Policy", "geolocation=(), microphone=(), camera=()"
        )
        # Tight CSP — the app ships zero third-party JS. Google Fonts is the
        # only external origin and it is style-only.
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com data:; "
            "img-src 'self' data:; "
            "script-src 'self'; "
            "connect-src 'self'; "
            "form-action 'self'; "
            "frame-ancestors 'none'; "
            "base-uri 'self'",
        )
        return response
