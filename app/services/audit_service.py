"""
IDRM — audit service.

Two write paths:

1. **Server-side triggers** (``fn_audit_row``) capture row-level INSERT/UPDATE/
   DELETE on governed tables automatically. Nothing to do in Python.

2. **Application events** (LOGIN, LOGOUT, SCAN, EXPORT, VIEW_SENSITIVE) have no
   row to trigger on, so the app writes them explicitly via ``log_event``.

``log_event`` buffers into ``flask.g.audit_buffer`` and the buffer is flushed in
the after-request hook, so a failed transaction never leaves orphan audit rows.
"""

from __future__ import annotations

import logging

from flask import g, has_request_context, request
from flask_login import current_user
from sqlalchemy import text

from app.extensions import db

log = logging.getLogger(__name__)


def _actor() -> tuple[int | None, str, str | None]:
    uid, username = None, "system"
    if has_request_context() and getattr(current_user, "is_authenticated", False):
        uid = getattr(current_user, "id", None)
        username = getattr(current_user, "username", "unknown")
    ip = request.remote_addr if has_request_context() else None
    return uid, username, ip


def log_event(
    event_type: str,
    action: str,
    *,
    entity_type: str | None = None,
    entity_id: int | None = None,
    severity: str = "info",
    message: str | None = None,
    before: dict | None = None,
    after: dict | None = None,
    flush: bool = False,
) -> None:
    """
    Record an application-level audit event.

    ``flush=True`` writes immediately (use for security-critical events such as
    LOGIN failures).  Otherwise the row is buffered and written after the
    request completes successfully.
    """
    payload = {
        "event_type": event_type,
        "action": action,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "severity": severity,
        "message": message or f"{action} {entity_type or ''}".strip(),
        "before_state": before,
        "after_state": after,
    }

    if flush or not has_request_context():
        _write(payload)
        return

    if not hasattr(g, "audit_buffer"):
        g.audit_buffer = []
    g.audit_buffer.append(payload)


def flush_buffer(events: list[dict]) -> int:
    """Write a batch of buffered events. Called from the after-request hook."""
    written = 0
    for ev in events:
        if _write(ev):
            written += 1
    return written


def _write(ev: dict) -> bool:
    uid, username, ip = _actor()
    try:
        db.session.execute(
            text(
                """
                INSERT INTO audit_event
                    (actor_user_id, actor_username, actor_ip, event_type,
                     entity_type, entity_id, action, before_state, after_state,
                     severity, message)
                VALUES
                    (:uid, :uname, CAST(:ip AS inet), :etype,
                     :ent, :eid, :action, CAST(:before AS jsonb), CAST(:after AS jsonb),
                     :sev, :msg)
                """
            ),
            {
                "uid": uid,
                "uname": username,
                "ip": ip,
                "etype": ev["event_type"],
                "ent": ev.get("entity_type"),
                "eid": ev.get("entity_id"),
                "action": ev["action"],
                "before": _json(ev.get("before_state")),
                "after": _json(ev.get("after_state")),
                "sev": ev.get("severity", "info"),
                "msg": ev.get("message"),
            },
        )
        db.session.commit()
        return True
    except Exception as exc:  # pragma: no cover
        db.session.rollback()
        log.error("Failed to write audit event %s: %s", ev.get("event_type"), exc)
        return False


def _json(value):
    import json

    return json.dumps(value, default=str) if value is not None else None


def set_actor_context(username: str) -> None:
    """
    Push the acting username into the Postgres session so that *trigger*-generated
    audit rows are attributed to the right person.

    Call once per request, right after authentication.
    """
    try:
        db.session.execute(
            text("SELECT set_config('idrm.actor', :a, true)"), {"a": username}
        )
    except Exception as exc:  # pragma: no cover
        log.debug("Could not set idrm.actor: %s", exc)
