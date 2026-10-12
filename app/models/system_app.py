"""Governed target system."""

from __future__ import annotations

from app.extensions import db


class SystemApp(db.Model):
    __tablename__ = "system_app"

    id = db.Column(db.BigInteger, primary_key=True)
    code = db.Column(db.Text, nullable=False, unique=True)
    name = db.Column(db.Text, nullable=False)
    description = db.Column(db.Text)
    owner_team = db.Column(db.Text)
    criticality = db.Column(db.Text, nullable=False, default="medium")
    data_classification = db.Column(db.Text, nullable=False, default="internal")
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime(timezone=True))
    updated_at = db.Column(db.DateTime(timezone=True))

    accounts = db.relationship("Account", back_populates="system", lazy="selectin")
    entitlements = db.relationship("Entitlement", back_populates="system", lazy="selectin")

    @property
    def criticality_band(self) -> str:
        return {"critical": "critical", "high": "high", "medium": "medium"}.get(
            self.criticality, "low"
        )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<SystemApp {self.code}>"
