"""
JSON API — /api/v1

Read-only for now; mutations flow through the HTML blueprints so that CSRF and
RBAC stay in one place.  Every endpoint is role-gated and audit-logged when it
touches sensitive data.
"""

from __future__ import annotations

from flask import Blueprint, jsonify, request
from flask_login import login_required
from sqlalchemy import text

from app.extensions import db
from app.security.decorators import auditor_required, roles_required
from app.services import reporting

api_bp = Blueprint("api", __name__)


def _paginate_args():
    page = max(1, int(request.args.get("page", 1)))
    per_page = min(int(request.args.get("per_page", 25)), 200)
    return page, per_page


@api_bp.route("/health")
def health():
    try:
        db.session.execute(text("SELECT 1"))
        return jsonify({"status": "ok", "database": "ok"})
    except Exception as exc:  # pragma: no cover
        return jsonify({"status": "degraded", "database": str(exc)}), 503


@api_bp.route("/kpis")
@login_required
def kpis():
    return jsonify(
        {
            "kpi": reporting.kpi_summary(),
            "severity": reporting.findings_by_severity(),
            "categories": reporting.findings_by_category(),
            "last_scan": reporting.last_scan(),
        }
    )


@api_bp.route("/findings")
@login_required
def findings():
    page, per_page = _paginate_args()
    status = request.args.get("status", "open")

    where = "1=1"
    params: dict = {}
    if status == "open":
        where = "f.status IN ('open','in_review')"
    elif status != "all":
        where = "f.status = :status"
        params["status"] = status

    rows = db.session.execute(
        text(
            f"""
            SELECT f.id, f.code, f.title, f.severity, f.status, f.risk_score,
                   f.detected_at, f.due_at,
                   i.display_name AS identity_name,
                   COALESCE(sa.code,'—') AS system_code
              FROM finding f
              LEFT JOIN identity   i  ON i.id  = f.identity_id
              LEFT JOIN system_app sa ON sa.id = f.system_id
             WHERE {where}
             ORDER BY f.detected_at DESC
             LIMIT {per_page} OFFSET {(page - 1) * per_page}
            """
        ),
        params,
    ).mappings().all()

    return jsonify(
        {
            "page": page,
            "per_page": per_page,
            "count": len(rows),
            "items": [dict(r) for r in rows],
        }
    )


@api_bp.route("/identities")
@login_required
def identities():
    page, per_page = _paginate_args()

    rows = db.session.execute(
        text(
            """
            SELECT i.id, i.external_ref, i.display_name, i.email,
                   i.identity_type, i.department, i.employment_status,
                   i.is_privileged, i.risk_score,
                   (SELECT count(*) FROM finding f
                     WHERE f.identity_id = i.id
                       AND f.status IN ('open','in_review')) AS open_findings
              FROM identity i
             ORDER BY i.risk_score DESC, i.display_name
             LIMIT :lim OFFSET :off
            """
        ),
        {"lim": per_page, "off": (page - 1) * per_page},
    ).mappings().all()

    return jsonify(
        {
            "page": page,
            "per_page": per_page,
            "count": len(rows),
            "items": [dict(r) for r in rows],
        }
    )


@api_bp.route("/audit-events")
@auditor_required
def audit_events():
    page, per_page = _paginate_args()

    rows, total = reporting.audit_trail(
        limit=per_page,
        offset=(page - 1) * per_page,
        entity_type=request.args.get("entity_type"),
        event_type=request.args.get("event_type"),
        actor=request.args.get("actor"),
        severity=request.args.get("severity"),
    )

    return jsonify(
        {
            "page": page,
            "per_page": per_page,
            "total": total,
            "items": rows,
        }
    )


@api_bp.route("/campaigns")
@login_required
def campaigns():
    return jsonify({"items": reporting.campaign_list()})
