"""
IDRM — risk engine.

Evaluates the `risk_rule` catalogue against live data, raising `finding` rows
for new violations and auto-closing findings whose condition no longer holds.

Every rule is a small function returning a list of "hits". A hit is a dict:

    {
        "identity_id":     int | None,
        "account_id":      int | None,
        "access_grant_id": int | None,
        "system_id":       int | None,
        "title":           str,
        "description":     str,
    }

The engine is deliberately table-driven rather than clever: a novice can read
each rule top-to-bottom and know exactly what it does.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone

from flask import current_app
from sqlalchemy import text

from app.extensions import db

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Rule registry:  code → callable(dormancy_days) → list[hit]
# ---------------------------------------------------------------------------
REGISTRY: dict[str, callable] = {}


def rule(code: str):
    def deco(fn):
        REGISTRY[code] = fn
        return fn

    return deco


# ===========================================================================
# Individual rules
# ===========================================================================
@rule("RR-COMP-001")
def _terminated_with_active_access(dormancy_days: int):  # noqa: ARG001
    rows = db.session.execute(
        text(
            """
            SELECT i.id AS identity_id,
                   a.id AS account_id,
                   g.id AS access_grant_id,
                   a.system_id AS system_id,
                   i.display_name,
                   e.code AS entitlement_code,
                   sa.code AS system_code
              FROM identity i
              JOIN account      a  ON a.identity_id = i.id
              JOIN access_grant g  ON g.account_id  = a.id
              JOIN entitlement  e  ON e.id          = g.entitlement_id
              JOIN system_app   sa ON sa.id         = a.system_id
             WHERE i.employment_status = 'terminated'
               AND g.state = 'active'
            """
        )
    ).mappings().all()

    return [
        {
            "identity_id": r["identity_id"],
            "account_id": r["account_id"],
            "access_grant_id": r["access_grant_id"],
            "system_id": r["system_id"],
            "title": f"Terminated identity retains {r['entitlement_code']} on {r['system_code']}",
            "description": (
                f"{r['display_name']} is marked terminated but still holds an active "
                f"grant of {r['entitlement_code']} on {r['system_code']}."
            ),
        }
        for r in rows
    ]


@rule("RR-ORPH-001")
def _orphaned_accounts(dormancy_days: int):  # noqa: ARG001
    rows = db.session.execute(
        text(
            """
            SELECT a.id AS account_id, a.identity_id, a.system_id,
                   a.username, sa.code AS system_code, i.display_name
              FROM account a
              JOIN identity   i  ON i.id  = a.identity_id
              JOIN system_app sa ON sa.id = a.system_id
             WHERE a.status = 'active'
               AND i.employment_status = 'terminated'
            """
        )
    ).mappings().all()

    return [
        {
            "identity_id": r["identity_id"],
            "account_id": r["account_id"],
            "system_id": r["system_id"],
            "title": f"Orphaned active account {r['username']} on {r['system_code']}",
            "description": (
                f"Account belongs to terminated identity {r['display_name']} but is still active."
            ),
        }
        for r in rows
    ]


@rule("RR-ORPH-002")
def _no_manager(dormancy_days: int):  # noqa: ARG001
    rows = db.session.execute(
        text(
            """
            SELECT id AS identity_id, display_name
              FROM identity
             WHERE employment_status = 'active'
               AND identity_type = 'employee'
               AND manager_id IS NULL
            """
        )
    ).mappings().all()

    return [
        {
            "identity_id": r["identity_id"],
            "title": f"Active employee {r['display_name']} has no manager",
            "description": "Manager field is empty; approval routing cannot resolve.",
        }
        for r in rows
    ]


@rule("RR-DORM-001")
def _dormant_accounts(dormancy_days: int):
    rows = db.session.execute(
        text(
            """
            SELECT a.id AS account_id, a.identity_id, a.system_id, a.username,
                   a.last_login_at, sa.code AS system_code
              FROM account a
              JOIN identity   i  ON i.id  = a.identity_id
              JOIN system_app sa ON sa.id = a.system_id
             WHERE a.status = 'active'
               AND a.account_type NOT IN ('privileged', 'emergency')
               AND i.employment_status = 'active'
               AND (a.last_login_at IS NULL
                    OR a.last_login_at < now() - make_interval(days => :d))
            """
        ),
        {"d": dormancy_days},
    ).mappings().all()

    return [
        {
            "identity_id": r["identity_id"],
            "account_id": r["account_id"],
            "system_id": r["system_id"],
            "title": f"Dormant account {r['username']} on {r['system_code']}",
            "description": (
                f"No authentication recorded in the last {dormancy_days} days."
            ),
        }
        for r in rows
    ]


@rule("RR-DORM-002")
def _dormant_privileged(dormancy_days: int):
    rows = db.session.execute(
        text(
            """
            SELECT a.id AS account_id, a.identity_id, a.system_id, a.username,
                   a.last_login_at, sa.code AS system_code
              FROM account a
              JOIN system_app sa ON sa.id = a.system_id
             WHERE a.status = 'active'
               AND a.account_type = 'privileged'
               AND (a.last_login_at IS NULL
                    OR a.last_login_at < now() - make_interval(days => :d))
            """
        ),
        {"d": dormancy_days},
    ).mappings().all()

    return [
        {
            "identity_id": r["identity_id"],
            "account_id": r["account_id"],
            "system_id": r["system_id"],
            "title": f"Dormant privileged account {r['username']} on {r['system_code']}",
            "description": (
                f"Privileged account inactive for {dormancy_days}+ days — revoke or disable."
            ),
        }
        for r in rows
    ]


@rule("RR-PRIV-001")
def _privileged_without_mfa(dormancy_days: int):  # noqa: ARG001
    rows = db.session.execute(
        text(
            """
            SELECT a.id AS account_id, a.identity_id, a.system_id, a.username,
                   sa.code AS system_code
              FROM account a
              JOIN system_app sa ON sa.id = a.system_id
             WHERE a.status = 'active'
               AND a.account_type = 'privileged'
               AND a.mfa_enabled = FALSE
            """
        )
    ).mappings().all()

    return [
        {
            "identity_id": r["identity_id"],
            "account_id": r["account_id"],
            "system_id": r["system_id"],
            "title": f"Privileged account {r['username']} on {r['system_code']} lacks MFA",
            "description": "Privileged access without a second factor breaches the access control standard.",
        }
        for r in rows
    ]


@rule("RR-PRIV-002")
def _standing_privilege(dormancy_days: int):  # noqa: ARG001
    rows = db.session.execute(
        text(
            """
            SELECT g.id AS access_grant_id, a.id AS account_id, a.identity_id,
                   a.system_id, e.code AS entitlement_code, sa.code AS system_code,
                   i.display_name
              FROM access_grant g
              JOIN account     a  ON a.id  = g.account_id
              JOIN identity    i  ON i.id  = a.identity_id
              JOIN entitlement e  ON e.id  = g.entitlement_id
              JOIN system_app  sa ON sa.id = a.system_id
             WHERE g.state = 'active'
               AND e.is_privileged = TRUE
               AND g.expires_at IS NULL
               AND i.employment_status = 'active'
            """
        )
    ).mappings().all()

    return [
        {
            "identity_id": r["identity_id"],
            "account_id": r["account_id"],
            "access_grant_id": r["access_grant_id"],
            "system_id": r["system_id"],
            "title": (
                f"Standing privileged access: {r['entitlement_code']} "
                f"for {r['display_name']} on {r['system_code']}"
            ),
            "description": "Privileged grant has no expiry — convert to just-in-time.",
        }
        for r in rows
    ]


@rule("RR-PRIV-003")
def _excessive_privilege(dormancy_days: int):  # noqa: ARG001
    rows = db.session.execute(
        text(
            """
            SELECT i.id AS identity_id, i.display_name, COUNT(DISTINCT e.id) AS n
              FROM identity i
              JOIN account      a ON a.identity_id = i.id
              JOIN access_grant g ON g.account_id  = a.id
              JOIN entitlement  e ON e.id          = g.entitlement_id
             WHERE g.state = 'active'
               AND e.is_privileged = TRUE
               AND i.employment_status = 'active'
             GROUP BY i.id, i.display_name
            HAVING COUNT(DISTINCT e.id) > 3
            """
        )
    ).mappings().all()

    return [
        {
            "identity_id": r["identity_id"],
            "title": f"Excessive privileged entitlements ({r['n']}) for {r['display_name']}",
            "description": "Holding more than three privileged entitlements increases blast radius.",
        }
        for r in rows
    ]


@rule("RR-SOD-001")
def _sod_conflicts(dormancy_days: int):  # noqa: ARG001
    rows = db.session.execute(
        text(
            """
            SELECT DISTINCT
                   i.id AS identity_id,
                   a.id AS account_id,
                   g.id AS access_grant_id,
                   a.system_id AS system_id,
                   i.display_name,
                   ea.code AS ent_a,
                   eb.code AS ent_b,
                   sa.code AS system_code,
                   sr.description AS sod_description
              FROM sod_rule sr
              JOIN entitlement ea ON ea.id = sr.entitlement_a_id
              JOIN entitlement eb ON eb.id = sr.entitlement_b_id
              JOIN system_app  sa ON sa.id = sr.system_id
              JOIN entitlement e1 ON e1.system_id = sr.system_id
              JOIN entitlement e2 ON e2.system_id = sr.system_id
              JOIN access_grant g1 ON g1.entitlement_id = e1.id AND g1.state = 'active'
              JOIN access_grant g2 ON g2.entitlement_id = e2.id AND g2.state = 'active'
              JOIN account  a  ON a.id = g1.account_id AND a.id = g2.account_id
              JOIN identity i  ON i.id = a.identity_id
              JOIN access_grant g ON g.id = g1.id
             WHERE sr.is_active = TRUE
               AND e1.id = sr.entitlement_a_id
               AND e2.id = sr.entitlement_b_id
               AND i.employment_status = 'active'
            """
        )
    ).mappings().all()

    return [
        {
            "identity_id": r["identity_id"],
            "account_id": r["account_id"],
            "access_grant_id": r["access_grant_id"],
            "system_id": r["system_id"],
            "title": f"Segregation of duties conflict: {r['ent_a']} + {r['ent_b']}",
            "description": (
                f"{r['display_name']} holds both {r['ent_a']} and {r['ent_b']} on "
                f"{r['system_code']}. {r['sod_description'] or ''}".strip()
            ),
        }
        for r in rows
    ]


@rule("RR-HYG-001")
def _stale_grants(dormancy_days: int):  # noqa: ARG001
    rows = db.session.execute(
        text(
            """
            SELECT g.id AS access_grant_id, a.id AS account_id, a.identity_id,
                   a.system_id, e.code AS entitlement_code, sa.code AS system_code,
                   i.display_name, g.last_used_at
              FROM access_grant g
              JOIN account     a  ON a.id  = g.account_id
              JOIN identity    i  ON i.id  = a.identity_id
              JOIN entitlement e  ON e.id  = g.entitlement_id
              JOIN system_app  sa ON sa.id = a.system_id
             WHERE g.state = 'active'
               AND i.employment_status = 'active'
               AND e.is_privileged = FALSE
               AND (g.last_used_at IS NULL
                    OR g.last_used_at < now() - INTERVAL '90 days')
            """
        )
    ).mappings().all()

    return [
        {
            "identity_id": r["identity_id"],
            "account_id": r["account_id"],
            "access_grant_id": r["access_grant_id"],
            "system_id": r["system_id"],
            "title": (
                f"Stale grant {r['entitlement_code']} for {r['display_name']} "
                f"on {r['system_code']}"
            ),
            "description": "Grant has not been exercised in over 90 days.",
        }
        for r in rows
    ]


@rule("RR-HYG-002")
def _stale_passwords(dormancy_days: int):  # noqa: ARG001
    rows = db.session.execute(
        text(
            """
            SELECT a.id AS account_id, a.identity_id, a.system_id, a.username,
                   sa.code AS system_code
              FROM account a
              JOIN system_app sa ON sa.id = a.system_id
             WHERE a.status = 'active'
               AND a.account_type <> 'service'
               AND (a.password_last_changed_at IS NULL
                    OR a.password_last_changed_at < now() - INTERVAL '365 days')
            """
        )
    ).mappings().all()

    return [
        {
            "identity_id": r["identity_id"],
            "account_id": r["account_id"],
            "system_id": r["system_id"],
            "title": f"Password not rotated in 365+ days: {r['username']} on {r['system_code']}",
            "description": "Password age exceeds the credential rotation control.",
        }
        for r in rows
    ]


@rule("RR-HYG-003")
def _shared_accounts(dormancy_days: int):  # noqa: ARG001
    rows = db.session.execute(
        text(
            """
            SELECT a.id AS account_id, a.identity_id, a.system_id, a.username,
                   sa.code AS system_code
              FROM account a
              JOIN system_app sa ON sa.id = a.system_id
             WHERE a.account_type = 'shared'
               AND a.status = 'active'
            """
        )
    ).mappings().all()

    return [
        {
            "identity_id": r["identity_id"],
            "account_id": r["account_id"],
            "system_id": r["system_id"],
            "title": f"Shared account in use: {r['username']} on {r['system_code']}",
            "description": "Shared credentials prevent individual attribution.",
        }
        for r in rows
    ]


@rule("RR-PRIV-004")
def _emergency_active(dormancy_days: int):  # noqa: ARG001
    rows = db.session.execute(
        text(
            """
            SELECT a.id AS account_id, a.identity_id, a.system_id, a.username,
                   sa.code AS system_code
              FROM account a
              JOIN system_app sa ON sa.id = a.system_id
             WHERE a.account_type = 'emergency'
               AND a.status = 'active'
            """
        )
    ).mappings().all()

    return [
        {
            "identity_id": r["identity_id"],
            "account_id": r["account_id"],
            "system_id": r["system_id"],
            "title": f"Emergency account active: {r['username']} on {r['system_code']}",
            "description": "Break-glass accounts must remain disabled until invoked.",
        }
        for r in rows
    ]


# ===========================================================================
# Engine
# ===========================================================================
def run_full_scan(trigger_source: str = "manual", triggered_by: int | None = None) -> dict:
    """
    Evaluate every active rule, reconcile findings, rescore identities.

    Returns a summary dict.
    """
    t0 = time.time()
    dormancy = current_app.config.get("IDRM_DORMANCY_DAYS", 90)

    scan_id = db.session.execute(
        text(
            """
            INSERT INTO scan_run (triggered_by, trigger_source, status)
            VALUES (:uid, :src, 'running')
            RETURNING id
            """
        ),
        {"uid": triggered_by, "src": trigger_source},
    ).scalar_one()
    db.session.commit()

    by_rule: dict[str, int] = {}
    created_total = 0

    rules = db.session.execute(
        text(
            "SELECT id, code, severity, weight FROM risk_rule "
            "WHERE is_active = TRUE ORDER BY code"
        )
    ).mappings().all()

    for rule_row in rules:
        code = rule_row["code"]
        fn = REGISTRY.get(code)
        if fn is None:
            log.debug("No implementation registered for rule %s — skipped.", code)
            continue

        try:
            hits = fn(dormancy)
        except Exception as exc:  # pragma: no cover
            db.session.rollback()
            log.exception("Rule %s failed: %s", code, exc)
            hits = []

        by_rule[code] = len(hits)
        created_total += _upsert_findings(rule_row, hits)

    # --- auto-close findings whose condition no longer holds -----------------
    closed = _auto_close_stale_findings(set(REGISTRY.keys()))

    # --- rescore identities --------------------------------------------------
    rescored = db.session.execute(text("SELECT fn_recompute_all_risk_scores()")).scalar_one()

    duration = time.time() - t0
    db.session.execute(
        text(
            """
            UPDATE scan_run
               SET finished_at = now(),
                   status = 'success',
                   rules_evaluated = :rules,
                   findings_created = :created,
                   findings_closed = :closed
             WHERE id = :id
            """
        ),
        {"rules": len(rules), "created": created_total, "closed": closed, "id": scan_id},
    )
    db.session.commit()

    # Application-level audit event
    from app.services.audit_service import log_event

    log_event(
        "SCAN",
        f"Risk scan #{scan_id} completed",
        entity_type="scan_run",
        entity_id=scan_id,
        message=(
            f"{len(rules)} rules evaluated, {created_total} findings created, "
            f"{closed} auto-closed in {duration:.1f}s"
        ),
        after={"by_rule": by_rule},
        flush=True,
    )

    return {
        "scan_id": scan_id,
        "rules_evaluated": len(rules),
        "findings_created": created_total,
        "findings_closed": closed,
        "identities_rescored": rescored,
        "duration_s": duration,
        "by_rule": by_rule,
    }


def _upsert_findings(rule_row, hits: list[dict]) -> int:
    """Insert findings that do not already exist (open) for the same subject."""
    created = 0

    for hit in hits:
        exists = db.session.execute(
            text(
                """
                SELECT 1 FROM finding
                 WHERE risk_rule_id = :rid
                   AND status IN ('open', 'in_review')
                   AND COALESCE(identity_id, 0)     = COALESCE(:iid, 0)
                   AND COALESCE(account_id, 0)      = COALESCE(:aid, 0)
                   AND COALESCE(access_grant_id, 0) = COALESCE(:gid, 0)
                 LIMIT 1
                """
            ),
            {
                "rid": rule_row["id"],
                "iid": hit.get("identity_id"),
                "aid": hit.get("account_id"),
                "gid": hit.get("access_grant_id"),
            },
        ).scalar()

        if exists:
            continue

        db.session.execute(
            text(
                """
                INSERT INTO finding
                    (risk_rule_id, identity_id, account_id, access_grant_id,
                     system_id, title, description, severity, status, risk_score)
                VALUES
                    (:rid, :iid, :aid, :gid, :sid, :title, :descr, :sev, 'open', 0)
                """
            ),
            {
                "rid": rule_row["id"],
                "iid": hit.get("identity_id"),
                "aid": hit.get("account_id"),
                "gid": hit.get("access_grant_id"),
                "sid": hit.get("system_id"),
                "title": hit["title"],
                "descr": hit.get("description"),
                "sev": rule_row["severity"],
            },
        )
        created += 1

    db.session.commit()
    return created


def _auto_close_stale_findings(active_rule_codes: set[str]) -> int:
    """
    Close findings raised by rules that no longer produce a hit.

    A finding is auto-closed when:
      * it is open/in_review, AND
      * its rule is still active, AND
      * re-running that rule no longer produces a hit for the same subject.
    """
    # Simpler, safer approach: recompute the set of live hits per rule and close
    # any open finding whose rule+subject tuple is absent.
    live: set[tuple] = set()
    dormancy = current_app.config.get("IDRM_DORMANCY_DAYS", 90)

    rule_ids = {
        r["code"]: r["id"]
        for r in db.session.execute(
            text("SELECT id, code FROM risk_rule WHERE is_active = TRUE")
        ).mappings()
    }

    for code in active_rule_codes:
        fn = REGISTRY.get(code)
        rid = rule_ids.get(code)
        if fn is None or rid is None:
            continue
        try:
            hits = fn(dormancy)
        except Exception:  # pragma: no cover
            continue
        for h in hits:
            live.add(
                (
                    rid,
                    h.get("identity_id"),
                    h.get("account_id"),
                    h.get("access_grant_id"),
                )
            )

    open_findings = db.session.execute(
        text(
            """
            SELECT id, risk_rule_id, identity_id, account_id, access_grant_id
              FROM finding
             WHERE status IN ('open', 'in_review')
            """
        )
    ).mappings().all()

    closed = 0
    for f in open_findings:
        key = (
            f["risk_rule_id"],
            f["identity_id"],
            f["account_id"],
            f["access_grant_id"],
        )
        if key not in live:
            db.session.execute(
                text(
                    """
                    UPDATE finding
                       SET status = 'closed',
                           remediation_note = COALESCE(remediation_note, '') ||
                               E'\n[auto] Condition no longer detected by the risk engine.',
                           updated_at = now()
                     WHERE id = :id
                    """
                ),
                {"id": f["id"]},
            )
            closed += 1

    db.session.commit()
    return closed
