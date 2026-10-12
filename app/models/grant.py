"""Assignment of an entitlement to an account — the core governed object."""

from __future__ import annotations

from app.extensions import db


class AccessGrant(db.Model):
    __tablename__ = "access_grant"

    id = db.Column(db.BigInteger, primary_key=True)
    account_id = db.Column(db.BigInteger, db.ForeignKey("account.id"), nullable=False)
    entitlement_id = db.Column(db.BigInteger, db.ForeignKey("entitlement.id"), nullable=False)
    granted_by = db.Column(db.Text)
    granted_at = db.Column(db.DateTime(timezone=True))
    expires_at = db.Column(db.DateTime(timezone=True))
    last_used_at = db.Column(db.DateTime(timezone=True))
    state = db.Column(db.Text, nullable=False, default="active")
    justification = db.Column(db.Text)
    created_at = db.Column(db.DateTime(timezone=True))
    updated_at = db.Column(db.DateTime(timezone=True))

    account = db.relationship("Account", back_populates="grants")
    entitlement = db.relationship("Entitlement", back_populates="grants")
    findings = db.relationship("Finding", back_populates="grant", lazy="selectin")
    review_items = db.relationship("ReviewItem", back_populates="grant", lazy="selectin")

    @property
    def identity(self):
        return self.account.identity if self.account else None

    @property
    def system(self):
        return self.account.system if self.account else None

    @property
    def is_expired(self) -> bool:
        from datetime import datetime, timezone

        if self.state == "expired":
            return True
        if self.state != "active" or not self.expires_at:
            return False
        exp = self.expires_at
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        return exp < datetime.now(timezone.utc)

    @property
    def is_standing_privilege(self) -> bool:
        return (
            self.state == "active"
            and self.entitlement is not None
            and self.entitlement.is_privileged
            and self.expires_at is None
        )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<AccessGrant a={self.account_id} e={self.entitlement_id} {self.state}>"
