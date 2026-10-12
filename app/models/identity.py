"""Governed identity — a human or non-human principal."""

from __future__ import annotations

from app.extensions import db


class Identity(db.Model):
    __tablename__ = "identity"

    id = db.Column(db.BigInteger, primary_key=True)
    external_ref = db.Column(db.Text, unique=True)
    display_name = db.Column(db.Text, nullable=False)
    email = db.Column(db.Text)
    identity_type = db.Column(db.Text, nullable=False, default="employee")
    department = db.Column(db.Text)
    job_title = db.Column(db.Text)
    manager_id = db.Column(db.BigInteger, db.ForeignKey("identity.id"))
    employment_status = db.Column(db.Text, nullable=False, default="active")
    join_date = db.Column(db.Date)
    termination_date = db.Column(db.Date)
    is_privileged = db.Column(db.Boolean, nullable=False, default=False)
    risk_score = db.Column(db.Numeric(5, 2), nullable=False, default=0)
    last_reviewed_at = db.Column(db.DateTime(timezone=True))
    created_at = db.Column(db.DateTime(timezone=True))
    updated_at = db.Column(db.DateTime(timezone=True))

    # ---- relationships -----------------------------------------------------
    manager = db.relationship("Identity", remote_side=[id], backref="reports")
    accounts = db.relationship(
        "Account", back_populates="identity", cascade="all, delete-orphan", lazy="selectin"
    )
    findings = db.relationship("Finding", back_populates="identity", lazy="selectin")

    # ---- helpers -----------------------------------------------------------
    @property
    def is_terminated(self) -> bool:
        return self.employment_status == "terminated"

    @property
    def is_human(self) -> bool:
        return self.identity_type in {"employee", "contractor", "vendor"}

    @property
    def risk_band(self) -> str:
        s = float(self.risk_score or 0)
        if s >= 60:
            return "critical"
        if s >= 35:
            return "high"
        if s >= 15:
            return "medium"
        return "low"

    @property
    def initials(self) -> str:
        parts = [p for p in (self.display_name or "?").split() if p]
        if len(parts) == 1:
            return parts[0][:2].upper()
        return (parts[0][0] + parts[-1][0]).upper()

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Identity {self.display_name}>"
