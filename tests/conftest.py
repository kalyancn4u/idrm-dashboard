"""Shared pytest fixtures."""

from __future__ import annotations

import os

import pytest
from sqlalchemy import text

from app import create_app
from app.extensions import db as _db


@pytest.fixture(scope="session")
def app():
    os.environ.setdefault("FLASK_ENV", "testing")
    application = create_app("testing")

    with application.app_context():
        _db.create_all()
        _seed_minimal(_db)
        yield application
        _db.session.remove()
        _db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def db(app):
    return _db


@pytest.fixture()
def runner(app):
    return app.test_cli_runner()


def _seed_minimal(db):
    """Create the smallest dataset that exercises the models."""
    db.session.execute(
        text(
            """
            INSERT INTO app_user (username, email, full_name, password_hash, role, is_active)
            VALUES
              ('testadmin',   'a@t.local', 'Test Admin',   'PLACEHOLDER', 'admin',   TRUE),
              ('testauditor', 'u@t.local', 'Test Auditor', 'PLACEHOLDER', 'auditor', TRUE),
              ('testviewer',  'v@t.local', 'Test Viewer',  'PLACEHOLDER', 'viewer',  TRUE)
            """
        )
    )
    db.session.execute(
        text(
            """
            INSERT INTO system_app (code, name, criticality, data_classification)
            VALUES ('TST', 'Test System', 'high', 'internal')
            """
        )
    )
    db.session.execute(
        text(
            """
            INSERT INTO identity (external_ref, display_name, email, identity_type,
                                  department, employment_status, is_privileged)
            VALUES
              ('T001', 'Test Person',  'p@t.local', 'employee',   'QA', 'active',     FALSE),
              ('T002', 'Test Leaver',  'l@t.local', 'employee',   'QA', 'terminated', TRUE)
            """
        )
    )
    db.session.commit()
