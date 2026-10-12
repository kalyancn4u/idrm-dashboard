"""A concrete login on a system, belonging to an identity."""

from __future__ import annotations

from datetime import datetime, timezone

from app.extensions import db


class Account(db.Model):
    __tablename__ = "account"

    id = db.Column(db.BigInteger, primary_key=True)
    identity_id = db.Column(db.BigInteger, db.ForeignKey("identity.id"), nullable=False)
    system_id = db.Column(db.BigInteger, db.ForeignKey("system_app.id"), nullable=False)
    username = db.Column(db.Text, nullable=False)
    account_type = db.Column(db.Text, nullable=False, default="standard")
    status = db.Column(db.Text, nullable=False, default="active")
    mfa_enabled = db.Column(db.Boolean, nullable=False, default=False)
    last_login_at = db.Column(db.DateTime(timezone=True))
    password_last_changed_at = db.Column(db.DateTime(timezone=True))
    created_at = db.Column(db.DateTime(timezone=True))
    updated_at = db.Column(db.DateTime(timezone=True))

    identity = db.relationship("Identity", back_populates="accounts")
    system = db.relationship("SystemApp", back_populates="accounts")
    grants = db.relationship(
        "AccessGrant", back_populates="account", cascade="all, delete-orphan", lazy="selectin"
    )

    @property
    def is_privileged(self) -> bool:
        return self.account_type in {"privileged", "emergency"}

    @property
    def days_since_login(self) -> int | None:
        if not self.last_login_at:
            return None
        now = datetime.now(timezone.utc)
        ref = self.last_login_at
        if ref.tzinfo is None:
            ref = ref.replace(tzinfo=timezone.utc)
        return (now - ref).days

    def is_dormant(self, threshold_days: int = 90) -> bool:
        d = self.days_since_login
        return d is None or d >= threshold_days

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Account {self.username}@{self.system_id}>"
