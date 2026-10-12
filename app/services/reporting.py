"""
IDRM — reporting service.

All aggregate queries live here so that blueprints stay thin and the numbers
presented to Admins and Auditors are guaranteed to come from the same source.
"""

from __future__ import annotations

import csv
import io
from datetime import datetime, timezone

from sqlalchemy import text

from app.extensions import db

# ===========================================================================
# KPI blocks
# ===========================================================================
def kpi_summary() -> dict:
    row = db.session.execute(
        text(
            """
            SELECT
              (SELECT count(*) FROM identity WHERE employment_status = 'active')      AS identities_active,
              (SELECT count(*) FROM identity WHERE employment_status = 'terminated')  AS identities_terminated,
              (SELECT count(*) FROM account  WHERE status = 'active')                 AS accounts_active,
              (SELECT count(*) FROM access_grant WHERE state = 'active')              AS grants_active,
              (SELECT count(*) FROM finding WHERE status IN ('open','in_review'))     AS findings_open,
              (SELECT count(*) FROM finding
                WHERE status IN ('open','in_review') AND severity = 'critical')       AS findings_critical,
              (SELECT count(*) FROM finding
                WHERE status IN ('open','in_review') AND due_at < now())              AS findings_overdue,
              (SELECT count(*) FROM finding
                WHERE status = 'remediated'
                  AND remediated_at > now() - INTERVAL '30 days')                     AS remediated_30d,
              (SELECT count(*) FROM identity WHERE risk_score >= 60)                  AS high_risk_identities
            """
        )
    ).mappings().one()
    return dict(row)


def findings_by_severity() -> list[dict]:
    rows = db.session.execute(
        text(
            """
            SELECT severity, count(*) AS n
              FROM finding
             WHERE status IN ('open','in_review')
             GROUP BY severity
             ORDER BY CASE severity
                        WHEN 'critical' THEN 1
                        WHEN 'high'     THEN 2
                        WHEN 'medium'   THEN 3
                        ELSE 4 END
            """
        )
    ).mappings().all()
    return [dict(r) for r in rows]


def findings_by_category() -> list[dict]:
    rows = db.session.execute(
        text(
            """
            SELECT rr.category, count(*) AS n
              FROM finding f
              JOIN risk_rule rr ON rr.id = f.risk_rule_id
             WHERE f.status IN ('open','in_review')
             GROUP BY rr.category
             ORDER BY n DESC
            """
        )
    ).mappings().all()
    return [dict(r) for r in rows]


def findings_by_system() -> list[dict]:
    rows = db.session.execute(
        text(
            """
            SELECT COALESCE(sa.code, '—') AS system_code,
                   COALESCE(sa.name, 'Unassigned') AS system_name,
                   count(*) AS n,
                   count(*) FILTER (WHERE f.severity = 'critical') AS critical_n
              FROM finding f
              LEFT JOIN system_app sa ON sa.id = f.system_id
             WHERE f.status IN ('open','in_review')
             GROUP BY sa.code, sa.name
             ORDER BY critical_n DESC, n DESC
            """
        )
    ).mappings().all()
    return [dict(r) for r in rows]


def recent_findings(limit: int = 8) -> list[dict]:
    rows = db.session.execute(
        text(
            """
            SELECT f.id, f.code, f.title, f.severity, f.status,
                   f.detected_at, f.due_at,
                   i.display_name AS identity_name,
                   i.id AS identity_id,
                   COALESCE(sa.code, '—') AS system_code
              FROM finding f
              LEFT JOIN identity   i  ON i.id  = f.identity_id
              LEFT JOIN system_app sa ON sa.id = f.system_id
             ORDER BY f.detected_at DESC NULLS LAST
             LIMIT :lim
            """
        ),
        {"lim": limit},
    ).mappings().all()
    return [dict(r) for r in rows]


def top_risky_identities(limit: int = 6) -> list[dict]:
    rows = db.session.execute(
        text(
            """
            SELECT i.id, i.display_name, i.department, i.identity_type,
                   i.risk_score, i.is_privileged,
                   count(f.id) FILTER (WHERE f.status IN ('open','in_review')) AS open_findings
              FROM identity i
              LEFT JOIN finding f ON f.identity_id = i.id
             WHERE i.employment_status = 'active'
             GROUP BY i.id
             ORDER BY i.risk_score DESC, open_findings DESC
             LIMIT :lim
            """
        ),
        {"lim": limit},
    ).mappings().all()
    return [dict(r) for r in rows]


def overdue_findings(limit: int = 10) -> list[dict]:
    rows = db.session.execute(
        text(
            """
            SELECT f.id, f.code, f.title, f.severity, f.status, f.due_at,
                   i.display_name AS identity_name
              FROM finding f
              LEFT JOIN identity i ON i.id = f.identity_id
             WHERE f.status IN ('open','in_review')
               AND f.due_at < now()
             ORDER BY f.due_at ASC
             LIMIT :lim
            """
        ),
        {"lim": limit},
    ).mappings().all()
    return [dict(r) for r in rows]


def active_campaign() -> dict | None:
    row = db.session.execute(
        text(
            """
            SELECT c.id, c.code, c.name, c.status, c.starts_at, c.due_at,
                   sa.code AS scope_code,
                   count(ri.id) AS total,
                   count(ri.id) FILTER (WHERE ri.decision <> 'pending') AS decided,
                   count(ri.id) FILTER (WHERE ri.decision = 'revoke')   AS revoked,
                   count(ri.id) FILTER (WHERE ri.decision = 'approve')  AS approved
              FROM review_campaign c
              LEFT JOIN review_item ri ON ri.campaign_id = c.id
              LEFT JOIN system_app  sa ON sa.id = c.scope_system_id
             WHERE c.status = 'active'
             GROUP BY c.id, sa.code
             ORDER BY c.due_at ASC NULLS LAST
             LIMIT 1
            """
        )
    ).mappings().first()
    if not row:
        return None
    d = dict(row)
    d["progress_pct"] = int(round(100 * d["decided"] / d["total"])) if d["total"] else 0
    return d


def last_scan() -> dict | None:
    row = db.session.execute(
        text(
            """
            SELECT id, started_at, finished_at, trigger_source, status,
                   rules_evaluated, findings_created, findings_closed,
                   EXTRACT(EPOCH FROM (finished_at - started_at))::NUMERIC(6,2) AS duration_s
              FROM scan_run
             ORDER BY started_at DESC
             LIMIT 1
            """
        )
    ).mappings().first()
    return dict(row) if row else None


def scan_history(limit: int = 10) -> list[dict]:
    rows = db.session.execute(
        text(
            """
            SELECT id, started_at, finished_at, trigger_source, status,
                   rules_evaluated, findings_created, findings_closed,
                   EXTRACT(EPOCH FROM (finished_at - started_at))::NUMERIC(6,2) AS duration_s
              FROM scan_run
             ORDER BY started_at DESC
             LIMIT :lim
            """
        ),
        {"lim": limit},
    ).mappings().all()
    return [dict(r) for r in rows]


# ===========================================================================
# Auditor-specific
# ===========================================================================
def audit_trail(
    limit: int = 100,
    offset: int = 0,
    entity_type: str | None = None,
    event_type: str | None = None,
    actor: str | None = None,
    severity: str | None = None,
    since_days: int | None = None,
) -> tuple[list[dict], int]:
    clauses, params = ["1=1"], {"lim": limit, "off": offset}

    if entity_type:
        clauses.append("entity_type = :entity_type")
        params["entity_type"] = entity_type
    if event_type:
        clauses.append("event_type = :event_type")
        params["event_type"] = event_type
    if actor:
        clauses.append("actor_username ILIKE :actor")
        params["actor"] = f"%{actor}%"
    if severity:
        clauses.append("severity = :severity")
        params["severity"] = severity
    if since_days:
        clauses.append("event_time > now() - make_interval(days => :days)")
        params["days"] = since_days

    where = " AND ".join(clauses)

    total = db.session.execute(
        text(f"SELECT count(*) FROM audit_event WHERE {where}"), params
    ).scalar_one()

    rows = db.session.execute(
        text(
            f"""
            SELECT id, event_time, actor_username, actor_ip, event_type,
                   entity_type, entity_id, action, severity, message,
                   before_state, after_state, correlation_id
              FROM audit_event
             WHERE {where}
             ORDER BY event_time DESC, id DESC
             LIMIT :lim OFFSET :off
            """
        ),
        params,
    ).mappings().all()

    return [dict(r) for r in rows], total


def audit_event_types() -> list[str]:
    rows = db.session.execute(
        text("SELECT DISTINCT event_type FROM audit_event ORDER BY event_type")
    ).scalars().all()
    return list(rows)


def audit_entity_types() -> list[str]:
    rows = db.session.execute(
        text(
            "SELECT DISTINCT entity_type FROM audit_event "
            "WHERE entity_type IS NOT NULL ORDER BY entity_type"
        )
    ).scalars().all()
    return list(rows)


def evidence_register(limit: int = 200) -> list[dict]:
    rows = db.session.execute(
        text(
            """
            SELECT e.id, e.kind, e.title, e.uri, e.collected_at, e.sha256,
                   f.code AS finding_code, f.title AS finding_title,
                   f.severity AS finding_severity,
                   u.full_name AS collector_name
              FROM evidence e
              JOIN finding  f ON f.id = e.finding_id
              LEFT JOIN app_user u ON u.id = e.collected_by
             ORDER BY e.collected_at DESC
             LIMIT :lim
            """
        ),
        {"lim": limit},
    ).mappings().all()
    return [dict(r) for r in rows]


def campaign_list() -> list[dict]:
    rows = db.session.execute(
        text(
            """
            SELECT c.id, c.code, c.name, c.status, c.starts_at, c.due_at,
                   sa.code AS scope_code,
                   count(ri.id) AS total,
                   count(ri.id) FILTER (WHERE ri.decision <> 'pending') AS decided,
                   count(ri.id) FILTER (WHERE ri.decision = 'revoke')   AS revoked
              FROM review_campaign c
              LEFT JOIN review_item ri ON ri.campaign_id = c.id
              LEFT JOIN system_app  sa ON sa.id = c.scope_system_id
             GROUP BY c.id, sa.code
             ORDER BY c.starts_at DESC NULLS LAST
            """
        )
    ).mappings().all()
    out = []
    for r in rows:
        d = dict(r)
        d["progress_pct"] = int(round(100 * d["decided"] / d["total"])) if d["total"] else 0
        out.append(d)
    return out


# ===========================================================================
# CSV exports
# ===========================================================================
def _to_csv(headers: list[str], rows: list[dict]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(headers)
    for r in rows:
        w.writerow([r.get(h, "") for h in headers])
    return buf.getvalue()


def export_findings_csv() -> str:
    rows = db.session.execute(
        text(
            """
            SELECT f.code, f.title, f.severity, f.status, f.risk_score,
                   f.detected_at, f.due_at, f.remediated_at,
                   i.display_name AS identity_name,
                   i.external_ref AS identity_ref,
                   COALESCE(sa.code,'') AS system_code,
                   COALESCE(rr.code,'') AS rule_code,
                   COALESCE(u.full_name,'') AS assigned_to
              FROM finding f
              LEFT JOIN identity   i  ON i.id  = f.identity_id
              LEFT JOIN system_app sa ON sa.id = f.system_id
              LEFT JOIN risk_rule  rr ON rr.id = f.risk_rule_id
              LEFT JOIN app_user   u  ON u.id  = f.assigned_to
             ORDER BY f.detected_at DESC
            """
        )
    ).mappings().all()

    headers = [
        "code", "title", "severity", "status", "risk_score",
        "detected_at", "due_at", "remediated_at",
        "identity_name", "identity_ref", "system_code", "rule_code", "assigned_to",
    ]
    return _to_csv(headers, [dict(r) for r in rows])


def export_identities_csv() -> str:
    rows = db.session.execute(
        text(
            """
            SELECT i.external_ref, i.display_name, i.email, i.identity_type,
                   i.department, i.job_title, i.employment_status,
                   i.is_privileged, i.risk_score,
                   count(DISTINCT a.id) AS accounts,
                   count(DISTINCT g.id) FILTER (WHERE g.state='active') AS active_grants,
                   count(DISTINCT f.id) FILTER (WHERE f.status IN ('open','in_review')) AS open_findings
              FROM identity i
              LEFT JOIN account      a ON a.identity_id = i.id
              LEFT JOIN access_grant g ON g.account_id  = a.id
              LEFT JOIN finding      f ON f.identity_id = i.id
             GROUP BY i.id
             ORDER BY i.risk_score DESC
            """
        )
    ).mappings().all()

    headers = [
        "external_ref", "display_name", "email", "identity_type", "department",
        "job_title", "employment_status", "is_privileged", "risk_score",
        "accounts", "active_grants", "open_findings",
    ]
    return _to_csv(headers, [dict(r) for r in rows])


def export_grants_csv() -> str:
    rows = db.session.execute(
        text(
            """
            SELECT i.display_name AS identity_name, i.external_ref,
                   sa.code AS system_code, a.username, a.account_type,
                   e.code AS entitlement_code, e.is_privileged,
                   g.state, g.granted_at, g.expires_at, g.last_used_at,
                   g.granted_by, g.justification
              FROM access_grant g
              JOIN account     a  ON a.id  = g.account_id
              JOIN identity    i  ON i.id  = a.identity_id
              JOIN entitlement e  ON e.id  = g.entitlement_id
              JOIN system_app  sa ON sa.id = a.system_id
             WHERE g.state = 'active'
             ORDER BY e.is_privileged DESC, i.display_name
            """
        )
    ).mappings().all()

    headers = [
        "identity_name", "external_ref", "system_code", "username", "account_type",
        "entitlement_code", "is_privileged", "state", "granted_at", "expires_at",
        "last_used_at", "granted_by", "justification",
    ]
    return _to_csv(headers, [dict(r) for r in rows])


def export_audit_csv(limit: int = 100_000) -> str:
    rows = db.session.execute(
        text(
            """
            SELECT id, event_time, actor_username, actor_ip, event_type,
                   entity_type, entity_id, action, severity, message
              FROM audit_event
             ORDER BY event_time DESC
             LIMIT :lim
            """
        ),
        {"lim": limit},
    ).mappings().all()

    headers = [
        "id", "event_time", "actor_username", "actor_ip", "event_type",
        "entity_type", "entity_id", "action", "severity", "message",
    ]
    return _to_csv(headers, [dict(r) for r in rows])


# ===========================================================================
# Helpers
# ===========================================================================
def utcnow() -> datetime:
    return datetime.now(timezone.utc)
