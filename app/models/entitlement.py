"""A role / permission / group defined on a system."""

from __future__ import annotations

from app.extensions import db


class Entitlement(db.Model):
    __tablename__ = "entitlement"

    id = db.Column(db.BigInteger, primary_key=True)
    system_id = db.Column(db.BigInteger, db.ForeignKey("system_app.id"), nullable=False)
    code = db.Column(db.Text, nullable=False)
    name = db.Column(db.Text, nullable=False)
    description = db.Column(db.Text)
    entitlement_type = db.Column(db.Text, nullable=False, default="role")
    risk_level = db.Column(db.Text, nullable=False, default="low")
    is_privileged = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime(timezone=True))

    system = db.relationship("SystemApp", back_populates="entitlements")
    grants = db.relationship("AccessGrant", back_populates="entitlement", lazy="selectin")

    @property
    def risk_band(self) -> str:
        return self.risk_level

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Entitlement {self.code}>"
