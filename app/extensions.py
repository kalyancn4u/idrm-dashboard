"""
IDRM — extension singletons.

Kept in their own module so that models, blueprints and the app factory can all
import them without circular-import pain.
"""

from __future__ import annotations

import logging

from flask import current_app
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
db = SQLAlchemy()

# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------
login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.login_message = "Please sign in to continue."
login_manager.login_message_category = "info"
login_manager.session_protection = "strong"


@login_manager.user_loader
def _load_user(user_id: str):
    from app.models.user import AppUser

    try:
        return db.session.get(AppUser, int(user_id))
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# CSRF
# ---------------------------------------------------------------------------
csrf = CSRFProtect()


# ---------------------------------------------------------------------------
# Optional Redis cache — degrades to an in-process dict
# ---------------------------------------------------------------------------
class _NullCache:
    """Minimal TTL-less cache used when Redis is not configured."""

    def __init__(self) -> None:
        self._store: dict[str, object] = {}

    def get(self, key):
        return self._store.get(key)

    def set(self, key, value, timeout=None):  # noqa: ARG002
        self._store[key] = value
        return True

    def delete(self, key):
        self._store.pop(key, None)
        return True

    def clear(self):
        self._store.clear()


def build_cache():
    """Return a Redis-backed cache if REDIS_URL is set, else a NullCache."""
    url = current_app.config.get("REDIS_URL")
    if not url:
        return _NullCache()
    try:
        import redis  # local import — optional dependency

        client = redis.Redis.from_url(url, decode_responses=True)
        client.ping()

        class _RedisCache:
            def __init__(self, c):
                self._c = c

            def get(self, key):
                import json

                raw = self._c.get(key)
                return json.loads(raw) if raw is not None else None

            def set(self, key, value, timeout=300):
                import json

                self._c.setex(key, timeout, json.dumps(value, default=str))
                return True

            def delete(self, key):
                self._c.delete(key)
                return True

            def clear(self):
                self._c.flushdb()

        log.info("Redis cache enabled: %s", url)
        return _RedisCache(client)
    except Exception as exc:  # pragma: no cover - environment dependent
        log.warning("Redis unavailable (%s) — falling back to in-process cache", exc)
        return _NullCache()


cache = None  # populated in create_app()
