"""Immutable audit trail + scan bookkeeping."""

from __future__ import annotations

from app.extensions import db


class AuditEvent(db.Model):
    __tablename__ = "audit_event"

    id = db.Column(db.BigInteger, primary_key=True)
    event_time = db.Column(db.DateTime(timezone=True))
    actor_user_id = db.Column(db.BigInteger, db.ForeignKey("app_user.id"))
    actor_username = db.Column(db.Text, nullable=False, default="system")
    actor_ip = db.Column(db.Text)          # INET in Postgres; TEXT works via cast
    event_type = db.Column(db.Text, nullable=False)
    entity_type = db.Column(db.Text)
    entity_id = db.Column(db.BigInteger)
    action = db.Column(db.Text, nullable=False)
    before_state = db.Column(db.JSON)
    after_state = db.Column(db.JSON)
    correlation_id = db.Column(db.Text)
    severity = db.Column(db.Text, nullable=False, default="info")
    message = db.Column(db.Text)

    actor = db.relationship("AppUser")

    # ---- rendered helpers --------------------------------------------------
    @property
    def is_high_severity(self) -> bool:
        return self.severity in {"warning", "critical"}

    @property
    def changed_fields(self) -> list[str]:
        """Field names that differ between before_state and after_state."""
        before = self.before_state or {}
        after = self.after_state or {}
        keys = set(before) | set(after)
        return sorted(k for k in keys if before.get(k) != after.get(k))

    @property
    def action_verb(self) -> str:
        return {
            "INSERT": "created",
            "UPDATE": "updated",
            "DELETE": "deleted",
            "LOGIN": "signed in",
            "LOGOUT": "signed out",
            "SCAN": "ran a risk scan",
            "EXPORT": "exported data",
        }.get(self.event_type, self.event_type.lower())

    def __repr__(self) -> str:  # pragma: no cover
        return f"<AuditEvent {self.event_type} {self.entity_type}#{self.entity_id}>"


class ScanRun(db.Model):
    __tablename__ = "scan_run"

    id = db.Column(db.BigInteger, primary_key=True)
    started_at = db.Column(db.DateTime(timezone=True))
    finished_at = db.Column(db.DateTime(timezone=True))
    triggered_by = db.Column(db.BigInteger, db.ForeignKey("app_user.id"))
    trigger_source = db.Column(db.Text, nullable=False, default="manual")
    rules_evaluated = db.Column(db.Integer, nullable=False, default=0)
    findings_created = db.Column(db.Integer, nullable=False, default=0)
    findings_closed = db.Column(db.Integer, nullable=False, default=0)
    status = db.Column(db.Text, nullable=False, default="running")
    error_text = db.Column(db.Text)

    triggerer = db.relationship("AppUser")

    @property
    def duration_s(self) -> float | None:
        if not self.started_at or not self.finished_at:
            return None
        return (self.finished_at - self.started_at).total_seconds()

    def __repr__(self) -> str:  # pragma: no cover
        return f"<ScanRun #{self.id} {self.status}>"
