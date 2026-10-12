"""
IDRM — configuration objects.

Selection order:
    FLASK_ENV=development|testing|production   (default: development)
"""

from __future__ import annotations

import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def _bool(key: str, default: bool = False) -> bool:
    return os.getenv(key, str(int(default))).strip().lower() in {"1", "true", "yes", "on"}


def _int(key: str, default: int) -> int:
    try:
        return int(os.getenv(key, default))
    except (TypeError, ValueError):
        return default


class BaseConfig:
    # ---- Flask --------------------------------------------------------------
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-not-secret-change-me")
    APP_NAME = os.getenv("APP_NAME", "IDRM")
    APP_TAGLINE = os.getenv("APP_TAGLINE", "Identity Data & Risk Management")
    JSON_SORT_KEYS = False
    TEMPLATES_AUTO_RELOAD = False

    # ---- Database -----------------------------------------------------------
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL", "postgresql+psycopg2://idrm:idrm@localhost:5432/idrm"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_size": _int("SQLALCHEMY_POOL_SIZE", 10),
        "max_overflow": _int("SQLALCHEMY_MAX_OVERFLOW", 20),
        "pool_recycle": _int("SQLALCHEMY_POOL_RECYCLE", 1800),
    }

    # ---- Cache / session ----------------------------------------------------
    REDIS_URL = os.getenv("REDIS_URL") or None

    # ---- Session ------------------------------------------------------------
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = _bool("SESSION_COOKIE_SECURE", False)
    PERMANENT_SESSION_LIFETIME = timedelta(
        minutes=_int("SESSION_LIFETIME_MINUTES", 480)
    )
    REMEMBER_COOKIE_DURATION = timedelta(days=_int("REMEMBER_COOKIE_DAYS", 14))
    REMEMBER_COOKIE_HTTPONLY = True

    # ---- CSRF ---------------------------------------------------------------
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = None

    # ---- Domain knobs -------------------------------------------------------
    IDRM_DORMANCY_DAYS = _int("IDRM_DORMANCY_DAYS", 90)
    IDRM_RUN_SCAN_ON_BOOT = _bool("IDRM_RUN_SCAN_ON_BOOT", False)
    IDRM_SLA_DAYS = {
        "critical": _int("IDRM_SLA_CRITICAL_DAYS", 7),
        "high": _int("IDRM_SLA_HIGH_DAYS", 14),
        "medium": _int("IDRM_SLA_MEDIUM_DAYS", 30),
        "low": _int("IDRM_SLA_LOW_DAYS", 90),
    }

    # ---- Pagination ---------------------------------------------------------
    PAGE_SIZE = 25
    MAX_PAGE_SIZE = 200


class DevelopmentConfig(BaseConfig):
    DEBUG = True
    TEMPLATES_AUTO_RELOAD = True
    SQLALCHEMY_ECHO = _bool("SQLALCHEMY_ECHO", False)


class TestingConfig(BaseConfig):
    TESTING = True
    DEBUG = True
    WTF_CSRF_ENABLED = False
    SECRET_KEY = "testing-secret"
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "IDRM_TEST_DATABASE_URL", "sqlite+pysqlite:///:memory:"
    )
    SQLALCHEMY_ENGINE_OPTIONS = {}   # in-memory SQLite dislikes pooling options
    PAGE_SIZE = 10


class ProductionConfig(BaseConfig):
    DEBUG = False
    SESSION_COOKIE_SECURE = True
    PREFERRED_URL_SCHEME = "https"

    def __init__(self) -> None:
        if self.SECRET_KEY.startswith("dev-only"):
            raise RuntimeError(
                "SECRET_KEY must be set to a strong random value in production."
            )


CONFIG_MAP = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}


def get_config(name: str | None = None):
    key = (name or os.getenv("FLASK_ENV", "development")).lower()
    return CONFIG_MAP.get(key, DevelopmentConfig)
