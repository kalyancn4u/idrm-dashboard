"""Model-level behaviour."""

from __future__ import annotations

from app.models.identity import Identity
from app.models.user import AppUser


def test_user_role_helpers(app):
    with app.app_context():
        admin = AppUser.query.filter_by(username="testadmin").first()
        auditor = AppUser.query.filter_by(username="testauditor").first()
        viewer = AppUser.query.filter_by(username="testviewer").first()

        assert admin.is_admin and admin.can_write
        assert auditor.is_auditor and not auditor.can_write
        assert viewer.is_viewer and not viewer.can_write


def test_user_initials(app):
    with app.app_context():
        admin = AppUser.query.filter_by(username="testadmin").first()
        assert admin.initials == "TA"


def test_placeholder_password_never_matches(app):
    with app.app_context():
        admin = AppUser.query.filter_by(username="testadmin").first()
        assert admin.check_password("anything") is False


def test_identity_risk_band(app):
    with app.app_context():
        person = Identity.query.filter_by(external_ref="T001").first()
        person.risk_score = 72
        assert person.risk_band == "critical"
        person.risk_score = 40
        assert person.risk_band == "high"
        person.risk_score = 20
        assert person.risk_band == "medium"
        person.risk_score = 5
        assert person.risk_band == "low"


def test_identity_terminated_flag(app):
    with app.app_context():
        leaver = Identity.query.filter_by(external_ref="T002").first()
        assert leaver.is_terminated
