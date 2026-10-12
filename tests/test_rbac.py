"""Role-based access control."""

from __future__ import annotations

import pytest
from flask_login import login_user

from app.models.user import AppUser
from app.security.rbac import has_permission


def _login(client, username):
    """Helper — log a user in via a test request context."""
    with client.session_transaction() as sess:
        sess["_user_id"] = str(AppUser.query.filter_by(username=username).first().id)
        sess["_fresh"] = True


@pytest.mark.rbac
def test_anonymous_redirected_to_login(client):
    resp = client.get("/admin/")
    assert resp.status_code in (302, 401)
    if resp.status_code == 302:
        assert "/auth/login" in resp.headers["Location"]


@pytest.mark.rbac
def test_auditor_forbidden_from_admin(client, app):
    with app.app_context():
        _login(client, "testauditor")
    resp = client.get("/admin/")
    assert resp.status_code == 403


@pytest.mark.rbac
def test_viewer_forbidden_from_audit_trail(client, app):
    with app.app_context():
        _login(client, "testviewer")
    resp = client.get("/auditor/audit-trail")
    assert resp.status_code == 403


@pytest.mark.rbac
def test_admin_can_reach_admin_dashboard(client, app):
    with app.app_context():
        _login(client, "testadmin")
    resp = client.get("/admin/")
    # The test DB has minimal data; a 200 with an empty dashboard is expected.
    assert resp.status_code == 200


def test_permission_matrix(app):
    with app.app_context():
        admin = AppUser.query.filter_by(username="testadmin").first()
        auditor = AppUser.query.filter_by(username="testauditor").first()

        assert has_permission("edit.finding", admin)
        assert has_permission("run.scan", admin)
        assert not has_permission("edit.finding", auditor)
        assert has_permission("view.audit", auditor)
        assert has_permission("export.data", auditor)
