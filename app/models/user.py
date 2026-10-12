"""Console user (login principal)."""

from __future__ import annotations

from datetime import datetime

from flask_login import UserMixin
from werkzeug.security import check_password_hash

from app.extensions import db


class AppUser(UserMixin, db.Model):
    __tablename__ = "app_user"

    id = db.Column(db.BigInteger, primary_key=True)
    username = db.Column(db.Text, nullable=False, unique=True)
    email = db.Column(db.Text, nullable=False, unique=True)
    full_name = db.Column(db.Text, nullable=False)
    password_hash = db.Column(db.Text, nullable=False)
    role = db.Column(db.Text, nullable=False, default="viewer")
    is_active_flag = db.Column("is_active", db.Boolean, nullable=False, default=True)
    last_login_at = db.Column(db.DateTime(timezone=True))
    failed_logins = db.Column(db.Integer, nullable=False, default=0)
    locked_until = db.Column(db.DateTime(timezone=True))
    created_at = db.Column(db.DateTime(timezone=True), default=datetime.utcnow)
    updated_at = db.Column(db.DateTime(timezone=True), default=datetime.utcnow)

    # ---- Flask-Login -------------------------------------------------------
    @property
    def is_active(self) -> bool:  # type: ignore[override]
        return bool(self.is_active_flag)

    def get_id(self) -> str:
        return str(self.id)

    # ---- passwords ---------------------------------------------------------
    def check_password(self, raw: str) -> bool:
        if not self.password_hash or self.password_hash == "PLACEHOLDER":
            return False
        return check_password_hash(self.password_hash, raw)

    # ---- role helpers ------------------------------------------------------
    @property
    def is_admin(self) -> bool:
        return self.role == "admin"

    @property
    def is_auditor(self) -> bool:
        return self.role == "auditor"

    @property
    def is_analyst(self) -> bool:
        return self.role == "analyst"

    @property
    def is_viewer(self) -> bool:
        return self.role == "viewer"

    @property
    def can_write(self) -> bool:
        """Only admin and analyst may mutate governed objects."""
        return self.role in {"admin", "analyst"}

    @property
    def initials(self) -> str:
        parts = [p for p in (self.full_name or self.username).split() if p]
        if not parts:
            return "?"
        if len(parts) == 1:
            return parts[0][:2].upper()
        return (parts[0][0] + parts[-1][0]).upper()

    def __repr__(self) -> str:  # pragma: no cover
        return f"<AppUser {self.username} ({self.role})>"
