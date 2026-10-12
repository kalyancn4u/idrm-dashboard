"""
Admin mode — full operational control over the IDRM estate.
"""

from __future__ import annotations

from datetime import datetime, timezone

from flask import (
    Blueprint,
    abort,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user
from sqlalchemy import text

from app.config import BaseConfig
from app.extensions import db
from app.models.account import Account
from app.models.finding import Evidence, Finding
from app.models.grant import AccessGrant
from app.models.identity import Identity
from app.models.review import ReviewCampaign
from app.security.decorators import admin_required, roles_required, write_required
from app.services import reporting
from app.services.audit_service import log_event
from app.services.risk_engine import run_full_scan

admin_bp = Blueprint("admin", __name__, template_folder="../templates")


# ===========================================================================
# Dashboard
# ===========================================================================
@admin_bp.route("/")
@roles_required("admin", "analyst")
def dashboard():
    return render_template(
        "admin/dashboard.html",
        kpi=reporting.kpi_summary(),
        severity=reporting.findings_by_severity(),
        categories=reporting.findings_by_category(),
        by_system=reporting.findings_by_system(),
        recent=reporting.recent_findings(limit=8),
        top_risky=reporting.top_risky_identities(limit=6),
        overdue=reporting.overdue_findings(limit=6),
        campaign=reporting.active_campaign(),
        scan=reporting.last_scan(),
    )


# ===========================================================================
# Identities
# ===========================================================================
@admin_bp.route("/identities")
@roles_required("admin", "analyst")
def identities():
    q = (request.args.get("q") or "").strip()
    status = request.args.get("status") or ""
    itype = request.args.get("type") or ""
    sort = request.args.get("sort") or "risk"
    page = max(1, int(request.args.get("page", 1)))
    per_page = 25

    where, params = ["1=1"], {}

    if q:
        where.append(
            "(i.display_name ILIKE :q OR i.email ILIKE :q OR i.external_ref ILIKE :q "
            "OR i.department ILIKE :q)"
        )
        params["q"] = f"%{q}%"
    if status:
        where.append("i.employment_status = :status")
        params["status"] = status
    if itype:
        where.append("i.identity_type = :itype")
        params["itype"] = itype

    order = {
        "risk": "i.risk_score DESC, i.display_name",
        "name": "i.display_name ASC",
        "recent": "i.created_at DESC",
        "findings": "open_findings DESC, i.risk_score DESC",
    }.get(sort, "i.risk_score DESC, i.display_name")

    where_sql = " AND ".join(where)

    total = db.session.execute(
        text(f"SELECT count(*) FROM identity i WHERE {where_sql}"), params
    ).scalar_one()

    rows = db.session.execute(
        text(
            f"""
            SELECT i.*,
                   m.display_name AS manager_name,
                   (SELECT count(*) FROM account a WHERE a.identity_id = i.id) AS account_count,
                   (SELECT count(*) FROM finding f
                     WHERE f.identity_id = i.id AND f.status IN ('open','in_review')) AS open_findings
              FROM identity i
              LEFT JOIN identity m ON m.id = i.manager_id
             WHERE {where_sql}
             ORDER BY {order}
             LIMIT {per_page} OFFSET {(page - 1) * per_page}
            """
        ),
        params,
    ).mappings().all()

    return render_template(
        "admin/identities.html",
        rows=[dict(r) for r in rows],
        total=total,
        page=page,
        per_page=per_page,
        pages=max(1, (total + per_page - 1) // per_page),
        q=q,
        status=status,
        itype=itype,
        sort=sort,
    )


@admin_bp.route("/identities/<int:identity_id>")
@roles_required("admin", "analyst")
def identity_detail(identity_id: int):
    identity = db.session.get(Identity, identity_id)
    if identity is None:
        abort(404)

    accounts = db.session.execute(
        text(
            """
            SELECT a.*, sa.code AS system_code, sa.name AS system_name,
                   (SELECT count(*) FROM access_grant g
                     WHERE g.account_id = a.id AND g.state = 'active') AS grant_count
              FROM account a
              JOIN system_app sa ON sa.id = a.system_id
             WHERE a.identity_id = :iid
             ORDER BY sa.code, a.username
            """
        ),
        {"iid": identity_id},
    ).mappings().all()

    grants = db.session.execute(
        text(
            """
            SELECT g.id, g.state, g.granted_at, g.expires_at, g.last_used_at,
                   g.granted_by, g.justification,
                   e.code AS entitlement_code, e.name AS entitlement_name,
                   e.is_privileged, e.risk_level,
                   sa.code AS system_code, a.username
              FROM access_grant g
              JOIN account     a  ON a.id  = g.account_id
              JOIN entitlement e  ON e.id  = g.entitlement_id
              JOIN system_app  sa ON sa.id = a.system_id
             WHERE a.identity_id = :iid
             ORDER BY e.is_privileged DESC, sa.code, e.code
            """
        ),
        {"iid": identity_id},
    ).mappings().all()

    findings = db.session.execute(
        text(
            """
            SELECT f.id, f.code, f.title, f.severity, f.status, f.detected_at,
                   f.due_at, COALESCE(sa.code,'—') AS system_code,
                   COALESCE(rr.code,'—') AS rule_code
              FROM finding f
              LEFT JOIN system_app sa ON sa.id = f.system_id
              LEFT JOIN risk_rule  rr ON rr.id = f.risk_rule_id
             WHERE f.identity_id = :iid
             ORDER BY CASE f.severity
                        WHEN 'critical' THEN 1 WHEN 'high' THEN 2
                        WHEN 'medium' THEN 3 ELSE 4 END,
                      f.detected_at DESC
            """
        ),
        {"iid": identity_id},
    ).mappings().all()

    timeline = db.session.execute(
        text(
            """
            SELECT a.id, a.event_time, a.actor_username, a.event_type,
                   a.entity_type, a.entity_id, a.action, a.severity, a.message
              FROM audit_event a
             WHERE (a.entity_type = 'identity' AND a.entity_id = :iid)
                OR (a.entity_type = 'account'
                    AND a.entity_id IN (SELECT id FROM account WHERE identity_id = :iid))
                OR (a.entity_type = 'access_grant'
                    AND a.entity_id IN (SELECT g.id FROM access_grant g
                                        JOIN account ac ON ac.id = g.account_id
                                        WHERE ac.identity_id = :iid))
             ORDER BY a.event_time DESC
             LIMIT 40
            """
        ),
        {"iid": identity_id},
    ).mappings().all()

    return render_template(
        "admin/identity_detail.html",
        identity=identity,
        accounts=[dict(r) for r in accounts],
        grants=[dict(r) for r in grants],
        findings=[dict(r) for r in findings],
        timeline=[dict(r) for r in timeline],
    )


@admin_bp.route("/identities/<int:identity_id>/toggle-privileged", methods=["POST"])
@admin_required
def toggle_privileged(identity_id: int):
    identity = db.session.get(Identity, identity_id)
    if identity is None:
        abort(404)

    before = identity.is_privileged
    identity.is_privileged = not before
    db.session.commit()

    log_event(
        "UPDATE",
        "Toggled privileged flag",
        entity_type="identity",
        entity_id=identity_id,
        before={"is_privileged": before},
        after={"is_privileged": identity.is_privileged},
        message=f"{identity.display_name} privileged flag → {identity.is_privileged}",
    )
    flash(f"Privileged flag updated for {identity.display_name}.", "success")
    return redirect(url_for("admin.identity_detail", identity_id=identity_id))


# ===========================================================================
# Grants
# ===========================================================================
@admin_bp.route("/grants")
@roles_required("admin", "analyst")
def grants():
    state = request.args.get("state", "active")
    privileged = request.args.get("privileged") == "1"
    system = request.args.get("system") or ""
    q = (request.args.get("q") or "").strip()
    page = max(1, int(request.args.get("page", 1)))
    per_page = 30

    where, params = ["1=1"], {}
    if state:
        where.append("g.state = :state")
        params["state"] = state
    if privileged:
        where.append("e.is_privileged = TRUE")
    if system:
        where.append("sa.code = :system")
        params["system"] = system
    if q:
        where.append("(i.display_name ILIKE :q OR e.code ILIKE :q OR a.username ILIKE :q)")
        params["q"] = f"%{q}%"

    where_sql = " AND ".join(where)

    total = db.session.execute(
        text(
            f"""
            SELECT count(*)
              FROM access_grant g
              JOIN account     a  ON a.id  = g.account_id
              JOIN identity    i  ON i.id  = a.identity_id
              JOIN entitlement e  ON e.id  = g.entitlement_id
              JOIN system_app  sa ON sa.id = a.system_id
             WHERE {where_sql}
            """
        ),
        params,
    ).scalar_one()

    rows = db.session.execute(
        text(
            f"""
            SELECT g.id, g.state, g.granted_at, g.expires_at, g.last_used_at,
                   g.granted_by, g.justification,
                   i.display_name AS identity_name, i.id AS identity_id,
                   a.username, a.account_type,
                   e.code AS entitlement_code, e.name AS entitlement_name,
                   e.is_privileged, e.risk_level,
                   sa.code AS system_code
              FROM access_grant g
              JOIN account     a  ON a.id  = g.account_id
              JOIN identity    i  ON i.id  = a.identity_id
              JOIN entitlement e  ON e.id  = g.entitlement_id
              JOIN system_app  sa ON sa.id = a.system_id
             WHERE {where_sql}
             ORDER BY e.is_privileged DESC, i.display_name, sa.code
             LIMIT {per_page} OFFSET {(page - 1) * per_page}
            """
        ),
        params,
    ).mappings().all()

    systems = db.session.execute(
        text("SELECT code, name FROM system_app WHERE is_active ORDER BY code")
    ).mappings().all()

    return render_template(
        "admin/grants.html",
        rows=[dict(r) for r in rows],
        total=total,
        page=page,
        per_page=per_page,
        pages=max(1, (total + per_page - 1) // per_page),
        state=state,
        privileged=privileged,
        system=system,
        q=q,
        systems=[dict(s) for s in systems],
    )


@admin_bp.route("/grants/<int:grant_id>/revoke", methods=["POST"])
@write_required
def revoke_grant(grant_id: int):
    grant = db.session.get(AccessGrant, grant_id)
    if grant is None:
        abort(404)
    if grant.state != "active":
        flash("Grant is not active.", "warning")
        return redirect(request.referrer or url_for("admin.grants"))

    grant.state = "revoked"
    db.session.commit()

    log_event(
        "UPDATE",
        "Revoked access grant",
        entity_type="access_grant",
        entity_id=grant_id,
        severity="notice",
        message=(
            f"Revoked {grant.entitlement.code} from "
            f"{grant.account.identity.display_name}"
        ),
    )
    flash("Grant revoked.", "success")
    return redirect(request.referrer or url_for("admin.grants"))


@admin_bp.route("/grants/<int:grant_id>/extend", methods=["POST"])
@write_required
def extend_grant(grant_id: int):
    grant = db.session.get(AccessGrant, grant_id)
    if grant is None:
        abort(404)

    days = int(request.form.get("days", 30))
    from datetime import timedelta

    base = grant.expires_at or datetime.now(timezone.utc)
    if base.tzinfo is None:
        base = base.replace(tzinfo=timezone.utc)
    grant.expires_at = base + timedelta(days=days)
    db.session.commit()

    log_event(
        "UPDATE",
        f"Extended grant by {days} days",
        entity_type="access_grant",
        entity_id=grant_id,
        after={"expires_at": str(grant.expires_at)},
    )
    flash(f"Grant extended by {days} days.", "success")
    return redirect(request.referrer or url_for("admin.grants"))


# ===========================================================================
# Findings
# ===========================================================================
@admin_bp.route("/findings")
@roles_required("admin", "analyst")
def findings():
    status = request.args.get("status", "open")
    severity = request.args.get("severity") or ""
    system = request.args.get("system") or ""
    assigned = request.args.get("assigned") or ""
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
    if assigned == "me":
        where.append("f.assigned_to = :me")
        params["me"] = current_user.id
    elif assigned == "unassigned":
        where.append("f.assigned_to IS NULL")
    if q:
        where.append("(f.title ILIKE :q OR f.code ILIKE :q OR i.display_name ILIKE :q)")
        params["q"] = f"%{q}%"

    where_sql = " AND ".join(where)

    base_from = """
        FROM finding f
        LEFT JOIN identity   i  ON i.id  = f.identity_id
        LEFT JOIN system_app sa ON sa.id = f.system_id
        LEFT JOIN risk_rule  rr ON rr.id = f.risk_rule_id
        LEFT JOIN app_user   u  ON u.id  = f.assigned_to
    """

    total = db.session.execute(
        text(f"SELECT count(*) {base_from} WHERE {where_sql}"), params
    ).scalar_one()

    rows = db.session.execute(
        text(
            f"""
            SELECT f.id, f.code, f.title, f.severity, f.status, f.risk_score,
                   f.detected_at, f.due_at,
                   i.display_name AS identity_name, i.id AS identity_id,
                   COALESCE(sa.code,'—') AS system_code,
                   COALESCE(rr.code,'—') AS rule_code,
                   COALESCE(u.full_name,'Unassigned') AS assignee,
                   (f.status IN ('open','in_review') AND f.due_at < now()) AS overdue
            {base_from}
             WHERE {where_sql}
             ORDER BY CASE f.severity
                        WHEN 'critical' THEN 1 WHEN 'high' THEN 2
                        WHEN 'medium' THEN 3 ELSE 4 END,
                      f.due_at ASC NULLS LAST,
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
        "admin/findings.html",
        rows=[dict(r) for r in rows],
        total=total,
        page=page,
        per_page=per_page,
        pages=max(1, (total + per_page - 1) // per_page),
        status=status,
        severity=severity,
        system=system,
        assigned=assigned,
        q=q,
        systems=list(systems),
    )


@admin_bp.route("/findings/<int:finding_id>")
@roles_required("admin", "analyst")
def finding_detail(finding_id: int):
    finding = db.session.get(Finding, finding_id)
    if finding is None:
        abort(404)

    assignees = db.session.execute(
        text(
            "SELECT id, full_name, username, role FROM app_user "
            "WHERE is_active AND role IN ('admin','analyst') ORDER BY full_name"
        )
    ).mappings().all()

    related = db.session.execute(
        text(
            """
            SELECT f.id, f.code, f.title, f.severity, f.status
              FROM finding f
             WHERE f.id <> :fid
               AND ((f.identity_id = :iid AND :iid IS NOT NULL)
                    OR (f.account_id = :aid AND :aid IS NOT NULL))
             ORDER BY f.detected_at DESC
             LIMIT 6
            """
        ),
        {"fid": finding.id, "iid": finding.identity_id, "aid": finding.account_id},
    ).mappings().all()

    return render_template(
        "admin/finding_detail.html",
        finding=finding,
        assignees=[dict(a) for a in assignees],
        related=[dict(r) for r in related],
    )


@admin_bp.route("/findings/<int:finding_id>/status", methods=["POST"])
@write_required
def update_finding_status(finding_id: int):
    finding = db.session.get(Finding, finding_id)
    if finding is None:
        abort(404)

    new_status = request.form.get("status") or finding.status
    note = (request.form.get("note") or "").strip()

    valid = {"open", "in_review", "remediated", "accepted_risk", "false_positive", "closed"}
    if new_status not in valid:
        abort(400)

    before = {"status": finding.status}
    finding.status = new_status

    if new_status in {"remediated", "closed"}:
        finding.remediated_at = datetime.now(timezone.utc)
        finding.remediated_by = current_user.id
        finding.remediation_note = note or finding.remediation_note

    if note:
        db.session.add(
            Evidence(
                finding_id=finding.id,
                kind="note",
                title=f"Status change → {new_status}",
                content=note,
                collected_by=current_user.id,
                collected_at=datetime.now(timezone.utc),
            )
        )

    db.session.commit()

    log_event(
        "UPDATE",
        f"Finding status → {new_status}",
        entity_type="finding",
        entity_id=finding.id,
        severity="notice" if new_status in {"accepted_risk", "false_positive"} else "info",
        before=before,
        after={"status": new_status, "note": note or None},
        message=f"{finding.code} moved to {new_status}",
    )

    flash(f"{finding.code} updated to {new_status.replace('_', ' ')}.", "success")
    return redirect(url_for("admin.finding_detail", finding_id=finding.id))


@admin_bp.route("/findings/<int:finding_id>/assign", methods=["POST"])
@write_required
def assign_finding(finding_id: int):
    finding = db.session.get(Finding, finding_id)
    if finding is None:
        abort(404)

    assignee_id = request.form.get("assignee_id") or None
    finding.assigned_to = int(assignee_id) if assignee_id else None
    db.session.commit()

    log_event(
        "UPDATE",
        "Finding reassigned",
        entity_type="finding",
        entity_id=finding.id,
        after={"assigned_to": finding.assigned_to},
    )
    flash("Assignee updated.", "success")
    return redirect(url_for("admin.finding_detail", finding_id=finding.id))


@admin_bp.route("/findings/<int:finding_id>/evidence", methods=["POST"])
@write_required
def add_evidence(finding_id: int):
    finding = db.session.get(Finding, finding_id)
    if finding is None:
        abort(404)

    title = (request.form.get("title") or "").strip()
    if not title:
        flash("Evidence title is required.", "error")
        return redirect(url_for("admin.finding_detail", finding_id=finding.id))

    ev = Evidence(
        finding_id=finding.id,
        kind=request.form.get("kind") or "note",
        title=title,
        uri=(request.form.get("uri") or "").strip() or None,
        content=(request.form.get("content") or "").strip() or None,
        collected_by=current_user.id,
        collected_at=datetime.now(timezone.utc),
    )
    db.session.add(ev)
    db.session.commit()

    log_event(
        "INSERT",
        "Evidence attached",
        entity_type="evidence",
        entity_id=ev.id,
        message=f"Evidence '{title}' attached to {finding.code}",
    )
    flash("Evidence added.", "success")
    return redirect(url_for("admin.finding_detail", finding_id=finding.id))


# ===========================================================================
# Reviews
# ===========================================================================
@admin_bp.route("/reviews")
@roles_required("admin", "analyst")
def reviews():
    campaigns = reporting.campaign_list()

    active = db.session.execute(
        text(
            """
            SELECT ri.id, ri.decision, ri.decided_at, ri.decision_note,
                   i.display_name AS identity_name, i.id AS identity_id,
                   e.code AS entitlement_code, e.is_privileged,
                   sa.code AS system_code, a.username,
                   u.full_name AS reviewer_name
              FROM review_item ri
              JOIN review_campaign c ON c.id = ri.campaign_id
              JOIN access_grant g   ON g.id = ri.access_grant_id
              JOIN account      a   ON a.id = g.account_id
              JOIN identity     i   ON i.id = a.identity_id
              JOIN entitlement  e   ON e.id = g.entitlement_id
              JOIN system_app   sa  ON sa.id = a.system_id
              LEFT JOIN app_user u  ON u.id = ri.reviewer_id
             WHERE c.status = 'active'
             ORDER BY CASE ri.decision WHEN 'pending' THEN 1 ELSE 2 END,
                      e.is_privileged DESC, i.display_name
             LIMIT 100
            """
        )
    ).mappings().all()

    return render_template(
        "admin/reviews.html",
        campaigns=campaigns,
        items=[dict(r) for r in active],
    )


@admin_bp.route("/reviews/item/<int:item_id>/decide", methods=["POST"])
@write_required
def decide_review_item(item_id: int):
    decision = request.form.get("decision")
    if decision not in {"approve", "revoke", "modify", "abstain", "pending"}:
        abort(400)

    db.session.execute(
        text(
            """
            UPDATE review_item
               SET decision = :d,
                   decision_note = :n,
                   decided_at = CASE WHEN :d = 'pending' THEN NULL ELSE now() END,
                   reviewer_id = :uid
             WHERE id = :id
            """
        ),
        {
            "d": decision,
            "n": (request.form.get("note") or "").strip() or None,
            "uid": current_user.id,
            "id": item_id,
        },
    )
    db.session.commit()

    log_event(
        "UPDATE",
        f"Certification decision: {decision}",
        entity_type="review_item",
        entity_id=item_id,
        severity="notice" if decision == "revoke" else "info",
    )
    flash(f"Decision recorded: {decision}.", "success")
    return redirect(url_for("admin.reviews"))


# ===========================================================================
# Risk scan
# ===========================================================================
@admin_bp.route("/scan", methods=["POST"])
@write_required
def trigger_scan():
    result = run_full_scan(trigger_source="manual", triggered_by=current_user.id)
    flash(
        f"Scan #{result['scan_id']} complete — "
        f"{result['findings_created']} new finding(s), "
        f"{result['findings_closed']} closed.",
        "success",
    )
    if request.headers.get("Accept") == "application/json":
        return jsonify(result)
    return redirect(request.referrer or url_for("admin.dashboard"))


@admin_bp.route("/scan/history")
@roles_required("admin", "analyst")
def scan_history():
    return render_template("admin/scan_history.html", runs=reporting.scan_history(limit=50))
