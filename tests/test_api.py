"""JSON API contract tests."""

from __future__ import annotations

import pytest


def _login(client, app, username):
    from app.models.user import AppUser

    with app.app_context():
        uid = AppUser.query.filter_by(username=username).first().id
    with client.session_transaction() as sess:
        sess["_user_id"] = str(uid)
        sess["_fresh"] = True


def test_health_is_public(client):
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.get_json()["status"] in {"ok", "degraded"}


def test_kpis_requires_auth(client):
    resp = client.get("/api/v1/kpis")
    assert resp.status_code in (401, 302)


def test_kpis_shape(client, app):
    _login(client, app, "testadmin")
    resp = client.get("/api/v1/kpis")
    assert resp.status_code == 200
    payload = resp.get_json()
    assert "kpi" in payload
    assert "severity" in payload
    assert isinstance(payload["severity"], list)


def test_findings_pagination_envelope(client, app):
    _login(client, app, "testadmin")
    resp = client.get("/api/v1/findings?page=1&per_page=5")
    assert resp.status_code == 200
    payload = resp.get_json()
    for key in ("page", "per_page", "count", "items"):
        assert key in payload


def test_audit_events_forbidden_for_viewer(client, app):
    _login(client, app, "testviewer")
    resp = client.get("/api/v1/audit-events")
    assert resp.status_code == 403
