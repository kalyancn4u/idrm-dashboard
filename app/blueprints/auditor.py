"""
Auditor mode — read-only assurance surface.

Design rule: **no route in this blueprint mutates governed data.**
The only writes are (a) audit events recording that a read/export happened and
(b) optional read-only annotations, which are themselves audited.
"""

from __future__ import annotations

from flask import (
    Blueprint,
    Response,
    abort,
    render_template,
    request,
)
from sqlalchemy import text

from app.extensions import db
from app.models.finding import Finding
from app.security.decorators import auditor_required, roles_required
from app.services import reporting
from app.services.audit_service import log_event

auditor_bp = Blueprint("auditor", __name__, template_folder="../templates")


# ===========================================================================
# Dashboard
# ===========================================================================
@auditor_bp.route("/")
@roles_required("auditor", "admin", "viewer")
def dashboard():
    return render_template(
        "auditor/dashboard.html",
        kpi=reporting.kpi_summary(),
        severity=reporting.findings_by_severity(),
        categories=reporting.findings_by_category(),
        by_system=reporting.findings_by_system(),
        overdue=reporting.overdue_findings(limit=10),
        scan=reporting.last_scan(),
        scans=reporting.scan_history(limit=5),
        campaign=reporting.active_campaign(),
    )


# ===========================================================================
# Findings (read-only)
# ===========================================================================
@auditor_bp.route("/findings")
@roles_required("auditor", "admin", "viewer")
def findings():
    status = request.args.get("status", "open")
    severity = request.args.get("severity") or ""
    system = request.args.get("system") or ""
    q = (request.args.get("q") or "").strip()
    page = max(1, int(request.args.get("page", 1)))
    per_page = 25

    where, params = ["1=1"], {}
    if status == "open":
        where.append("f.status IN ('open','in_review')")
    elif status and status != "all":
        where.append("f.status = :status")
        params["status"] = status
    if severity:
        where.append("f.severity = :severity")
        params["severity"] = severity
    if system:
        where.append("sa.code = :system")
        params["system"] = system
    if q:
        where.append("(f.title ILIKE :q OR f.code ILIKE :q OR i.display_name ILIKE :q)")
        params["q"] = f"%{q}%"

    where_sql = " AND ".join(where)
    base_from = """
        FROM finding f
        LEFT JOIN identity   i  ON i.id  = f.identity_id
        LEFT JOIN system_app sa ON sa.id = f.system_id
        LEFT JOIN risk_rule  rr ON rr.id = f.risk_rule_id
    """

    total = db.session.execute(
        text(f"SELECT count(*) {base_from} WHERE {where_sql}"), params
    ).scalar_one()

    rows = db.session.execute(
        text(
            f"""
            SELECT f.id, f.code, f.title, f.severity, f.status,
                   f.detected_at, f.due_at, f.remediated_at,
                   i.display_name AS identity_name,
                   COALESCE(sa.code,'—') AS system_code,
                   COALESCE(rr.code,'—') AS rule_code,
                   (f.status IN ('open','in_review') AND f.due_at < now()) AS overdue
            {base_from}
             WHERE {where_sql}
             ORDER BY CASE f.severity
                        WHEN 'critical' THEN 1 WHEN 'high' THEN 2
                        WHEN 'medium' THEN 3 ELSE 4 END,
                      f.detected_at DESC
             LIMIT {per_page} OFFSET {(page - 1) * per_page}
            """
        ),
        params,
    ).mappings().all()

    systems = db.session.execute(
        text("SELECT code FROM system_app WHERE is_active ORDER BY code")
    ).scalars().all()

    return render_template(
        "auditor/findings.html",
        rows=[dict(r) for r in rows],
        total=total,
        page=page,
        per_page=per_page,
        pages=max(1, (total + per_page - 1) // per_page),
        status=status,
        severity=severity,
        system=system,
        q=q,
        systems=list(systems),
    )


@auditor_bp.route("/findings/<int:finding_id>")
@roles_required("auditor", "admin", "viewer")
def finding_detail(finding_id: int):
    finding = db.session.get(Finding, finding_id)
    if finding is None:
        abort(404)

    # Record that this finding was examined — an important audit-trail property.
    log_event(
        "VIEW",
        "Finding examined",
        entity_type="finding",
        entity_id=finding.id,
        message=f"{finding.code} reviewed by {request.remote_addr or 'unknown'}",
    )

    history = db.session.execute(
        text(
            """
            SELECT id, event_time, actor_username, event_type, action,
                   severity, message, before_state, after_state
              FROM audit_event
             WHERE entity_type = 'finding' AND entity_id = :fid
             ORDER BY event_time DESC
            """
        ),
        {"fid": finding.id},
    ).mappings().all()

    return render_template(
        "auditor/finding_detail.html",
        finding=finding,
        history=[dict(h) for h in history],
    )


# ===========================================================================
# Audit trail
# ===========================================================================
@auditor_bp.route("/audit-trail")
@auditor_required
def audit_trail():
    entity_type = request.args.get("entity_type") or ""
    event_type = request.args.get("event_type") or ""
    actor = request.args.get("actor") or ""
    severity = request.args.get("severity") or ""
    since = request.args.get("since")
    page = max(1, int(request.args.get("page", 1)))
    per_page = 50

    since_days = None
    if since and since.isdigit():
        since_days = int(since)

    rows, total = reporting.audit_trail(
        limit=per_page,
        offset=(page - 1) * per_page,
        entity_type=entity_type or None,
        event_type=event_type or None,
        actor=actor or None,
        severity=severity or None,
        since_days=since_days,
    )

    return render_template(
        "auditor/audit_trail.html",
        rows=rows,
        total=total,
        page=page,
        per_page=per_page,
        pages=max(1, (total + per_page - 1) // per_page),
        entity_type=entity_type,
        event_type=event_type,
        actor=actor,
        severity=severity,
        since=since or "",
        entity_types=reporting.audit_entity_types(),
        event_types=reporting.audit_event_types(),
    )


# ===========================================================================
# Campaigns
# ===========================================================================
@auditor_bp.route("/campaigns")
@roles_required("auditor", "admin", "viewer")
def campaigns():
    return render_template(
        "auditor/campaigns.html",
        campaigns=reporting.campaign_list(),
    )


# ===========================================================================
# Evidence register
# ===========================================================================
@auditor_bp.route("/evidence")
@auditor_required
def evidence():
    return render_template(
        "auditor/exports.html",
        evidence=reporting.evidence_register(limit=300),
    )


# ===========================================================================
# Exports
# ===========================================================================
@auditor_bp.route("/exports")
@auditor_required
def exports():
    return render_template(
        "auditor/exports.html",
        evidence=reporting.evidence_register(limit=50),
    )


@auditor_bp.route("/export/<kind>.csv")
@auditor_required
def export_csv(kind: str):
    builders = {
        "findings": reporting.export_findings_csv,
        "identities": reporting.export_identities_csv,
        "grants": reporting.export_grants_csv,
        "audit": reporting.export_audit_csv,
    }
    fn = builders.get(kind)
    if fn is None:
        abort(404)

    payload = fn()
    log_event(
        "EXPORT",
        f"Exported {kind} to CSV",
        entity_type="export",
        severity="notice",
        message=f"{kind}.csv exported ({len(payload)} bytes)",
        flush=True,
    )

    filename = f"idrm_{kind}_{reporting.utcnow():%Y%m%d_%H%M%S}.csv"
    return Response(
        payload,
        mimetype="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
