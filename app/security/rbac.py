"""
IDRM — role → permission matrix.

Four console roles:

    admin    full control over governed objects and configuration
    analyst  investigate, annotate, assign and remediate findings
    auditor  read-only assurance; may export evidence
    viewer   read-only dashboards; no exports
"""

from __future__ import annotations

from flask_login import current_user

# ---------------------------------------------------------------------------
# Permission catalogue
# ---------------------------------------------------------------------------
PERMISSIONS: dict[str, set[str]] = {
    "admin": {
        # read
        "view.dashboard",
        "view.identity",
        "view.account",
        "view.grant",
        "view.finding",
        "view.evidence",
        "view.audit",
        "view.campaign",
        "view.report",
        # write
        "edit.identity",
        "edit.account",
        "edit.grant",
        "edit.finding",
        "edit.evidence",
        "edit.campaign",
        "run.scan",
        "export.data",
        "admin.system",
    },
    "analyst": {
        "view.dashboard",
        "view.identity",
        "view.account",
        "view.grant",
        "view.finding",
        "view.evidence",
        "view.audit",
        "view.campaign",
        "view.report",
        "edit.finding",
        "edit.evidence",
        "run.scan",
        "export.data",
    },
    "auditor": {
        "view.dashboard",
        "view.identity",
        "view.account",
        "view.grant",
        "view.finding",
        "view.evidence",
        "view.audit",
        "view.campaign",
        "view.report",
        "export.data",
    },
    "viewer": {
        "view.dashboard",
        "view.finding",
        "view.report",
    },
}


def has_permission(permission: str, user=None) -> bool:
    """True when the (authenticated) user holds ``permission``."""
    u = user or current_user
    if not getattr(u, "is_authenticated", False):
        return False
    return permission in PERMISSIONS.get(getattr(u, "role", ""), set())
