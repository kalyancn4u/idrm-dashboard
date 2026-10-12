"""Risk rules and findings."""

from __future__ import annotations

from app.extensions import db


class RiskRule(db.Model):
    __tablename__ = "risk_rule"

    id = db.Column(db.BigInteger, primary_key=True)
    code = db.Column(db.Text, nullable=False, unique=True)
    name = db.Column(db.Text, nullable=False)
    description = db.Column(db.Text)
    category = db.Column(db.Text, nullable=False)
    severity = db.Column(db.Text, nullable=False, default="medium")
    weight = db.Column(db.Numeric(4, 2), nullable=False, default=1.0)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    logic_hint = db.Column(db.Text)
    created_at = db.Column(db.DateTime(timezone=True))

    findings = db.relationship("Finding", back_populates="rule", lazy="dynamic")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<RiskRule {self.code}>"


class SodRule(db.Model):
    __tablename__ = "sod_rule"

    id = db.Column(db.BigInteger, primary_key=True)
    system_id = db.Column(db.BigInteger, db.ForeignKey("system_app.id"), nullable=False)
    entitlement_a_id = db.Column(db.BigInteger, db.ForeignKey("entitlement.id"), nullable=False)
    entitlement_b_id = db.Column(db.BigInteger, db.ForeignKey("entitlement.id"), nullable=False)
    description = db.Column(db.Text)
    severity = db.Column(db.Text, nullable=False, default="high")
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime(timezone=True))

    system = db.relationship("SystemApp")
    entitlement_a = db.relationship("Entitlement", foreign_keys=[entitlement_a_id])
    entitlement_b = db.relationship("Entitlement", foreign_keys=[entitlement_b_id])

    def __repr__(self) -> str:  # pragma: no cover
        return f"<SodRule {self.entitlement_a_id}×{self.entitlement_b_id}>"


class Finding(db.Model):
    __tablename__ = "finding"

    id = db.Column(db.BigInteger, primary_key=True)
    code = db.Column(db.Text, unique=True)
    risk_rule_id = db.Column(db.BigInteger, db.ForeignKey("risk_rule.id"))
    identity_id = db.Column(db.BigInteger, db.ForeignKey("identity.id"))
    account_id = db.Column(db.BigInteger, db.ForeignKey("account.id"))
    access_grant_id = db.Column(db.BigInteger, db.ForeignKey("access_grant.id"))
    system_id = db.Column(db.BigInteger, db.ForeignKey("system_app.id"))
    title = db.Column(db.Text, nullable=False)
    description = db.Column(db.Text)
    severity = db.Column(db.Text, nullable=False, default="medium")
    status = db.Column(db.Text, nullable=False, default="open")
    risk_score = db.Column(db.Numeric(5, 2), nullable=False, default=0)
    detected_at = db.Column(db.DateTime(timezone=True))
    due_at = db.Column(db.DateTime(timezone=True))
    assigned_to = db.Column(db.BigInteger, db.ForeignKey("app_user.id"))
    remediated_at = db.Column(db.DateTime(timezone=True))
    remediated_by = db.Column(db.BigInteger, db.ForeignKey("app_user.id"))
    remediation_note = db.Column(db.Text)
    created_at = db.Column(db.DateTime(timezone=True))
    updated_at = db.Column(db.DateTime(timezone=True))

    rule = db.relationship("RiskRule", back_populates="findings")
    identity = db.relationship("Identity", back_populates="findings")
    account = db.relationship("Account")
    grant = db.relationship("AccessGrant", back_populates="findings")
    system = db.relationship("SystemApp")
    assignee = db.relationship("AppUser", foreign_keys=[assigned_to])
    remediator = db.relationship("AppUser", foreign_keys=[remediated_by])
    evidence = db.relationship(
        "Evidence",
        back_populates="finding",
        cascade="all, delete-orphan",
        order_by="Evidence.collected_at.desc()",
        lazy="selectin",
    )

    OPEN_STATES = ("open", "in_review")

    @property
    def is_open(self) -> bool:
        return self.status in self.OPEN_STATES

    @property
    def is_overdue(self) -> bool:
        from datetime import datetime, timezone

        if not self.is_open or not self.due_at:
            return False
        due = self.due_at
        if due.tzinfo is None:
            due = due.replace(tzinfo=timezone.utc)
        return due < datetime.now(timezone.utc)

    @property
    def sla_days_remaining(self) -> int | None:
        from datetime import datetime, timezone

        if not self.due_at:
            return None
        due = self.due_at
        if due.tzinfo is None:
            due = due.replace(tzinfo=timezone.utc)
        return (due - datetime.now(timezone.utc)).days

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Finding {self.code} {self.severity} {self.status}>"


class Evidence(db.Model):
    __tablename__ = "evidence"

    id = db.Column(db.BigInteger, primary_key=True)
    finding_id = db.Column(db.BigInteger, db.ForeignKey("finding.id"), nullable=False)
    kind = db.Column(db.Text, nullable=False, default="note")
    title = db.Column(db.Text, nullable=False)
    uri = db.Column(db.Text)
    content = db.Column(db.Text)
    sha256 = db.Column(db.Text)
    collected_by = db.Column(db.BigInteger, db.ForeignKey("app_user.id"))
    collected_at = db.Column(db.DateTime(timezone=True))

    finding = db.relationship("Finding", back_populates="evidence")
    collector = db.relationship("AppUser")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Evidence {self.kind}:{self.title[:24]}>"
