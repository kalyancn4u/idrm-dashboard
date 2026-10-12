"""
IDRM — ORM models.

Importing this package registers every mapper with SQLAlchemy. The tables are
created by ``sql/01_schema.sql``, not by ``db.create_all()`` — the SQL file is
the single source of truth so that DBAs and auditors can review it directly.
"""

from app.models.account import Account
from app.models.audit import AuditEvent, ScanRun
from app.models.entitlement import Entitlement
from app.models.finding import Evidence, Finding, RiskRule, SodRule
from app.models.grant import AccessGrant
from app.models.identity import Identity
from app.models.review import ReviewCampaign, ReviewItem
from app.models.system_app import SystemApp
from app.models.user import AppUser

__all__ = [
    "AccessGrant",
    "Account",
    "AppUser",
    "AuditEvent",
    "Entitlement",
    "Evidence",
    "Finding",
    "Identity",
    "ReviewCampaign",
    "ReviewItem",
    "RiskRule",
    "ScanRun",
    "SodRule",
    "SystemApp",
]
