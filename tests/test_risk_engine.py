"""Risk engine unit tests — against SQLite they exercise the registry only."""

from __future__ import annotations

import pytest
from sqlalchemy import text

from app.services import risk_engine


def test_registry_covers_seeded_rules():
    """Every rule code we ship has a callable implementation."""
    expected = {
        "RR-COMP-001", "RR-ORPH-001", "RR-ORPH-002",
        "RR-DORM-001", "RR-DORM-002",
        "RR-PRIV-001", "RR-PRIV-002", "RR-PRIV-003", "RR-PRIV-004",
        "RR-SOD-001",
        "RR-HYG-001", "RR-HYG-002", "RR-HYG-003",
    }
    assert expected.issubset(set(risk_engine.REGISTRY.keys()))


def test_severity_points_monotonic(app):
    with app.app_context():
        p = risk_engine.db.session.execute(
            text("SELECT fn_severity_points('critical'), fn_severity_points('low')")
        ).one()
        # Function may not exist on SQLite — skip if so.
        if p is None:
            pytest.skip("fn_severity_points unavailable")
        assert p[0] > p[1]


@pytest.mark.pg
def test_scan_creates_findings_on_postgres(app):
    """Full scan requires Postgres (triggers, PL/pgSQL)."""
    with app.app_context():
        result = risk_engine.run_full_scan(trigger_source="scheduled")
        assert result["scan_id"] > 0
        assert result["rules_evaluated"] > 0
