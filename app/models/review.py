"""Access certification campaigns."""

from __future__ import annotations

from app.extensions import db


class ReviewCampaign(db.Model):
    __tablename__ = "review_campaign"

    id = db.Column(db.BigInteger, primary_key=True)
    code = db.Column(db.Text, nullable=False, unique=True)
    name = db.Column(db.Text, nullable=False)
    description = db.Column(db.Text)
    scope_system_id = db.Column(db.BigInteger, db.ForeignKey("system_app.id"))
    status = db.Column(db.Text, nullable=False, default="draft")
    starts_at = db.Column(db.DateTime(timezone=True))
    due_at = db.Column(db.DateTime(timezone=True))
    completed_at = db.Column(db.DateTime(timezone=True))
    created_by = db.Column(db.BigInteger, db.ForeignKey("app_user.id"))
    created_at = db.Column(db.DateTime(timezone=True))
    updated_at = db.Column(db.DateTime(timezone=True))

    scope_system = db.relationship("SystemApp")
    creator = db.relationship("AppUser")
    items = db.relationship(
        "ReviewItem", back_populates="campaign", cascade="all, delete-orphan", lazy="selectin"
    )

    @property
    def total(self) -> int:
        return len(self.items)

    @property
    def decided(self) -> int:
        return sum(1 for i in self.items if i.decision != "pending")

    @property
    def progress_pct(self) -> int:
        return int(round(100 * self.decided / self.total)) if self.total else 0

    @property
    def revoked(self) -> int:
        return sum(1 for i in self.items if i.decision == "revoke")

    @property
    def approved(self) -> int:
        return sum(1 for i in self.items if i.decision == "approve")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<ReviewCampaign {self.code} {self.status}>"


class ReviewItem(db.Model):
    __tablename__ = "review_item"

    id = db.Column(db.BigInteger, primary_key=True)
    campaign_id = db.Column(db.BigInteger, db.ForeignKey("review_campaign.id"), nullable=False)
    access_grant_id = db.Column(db.BigInteger, db.ForeignKey("access_grant.id"), nullable=False)
    reviewer_id = db.Column(db.BigInteger, db.ForeignKey("app_user.id"))
    decision = db.Column(db.Text, nullable=False, default="pending")
    decision_note = db.Column(db.Text)
    decided_at = db.Column(db.DateTime(timezone=True))
    created_at = db.Column(db.DateTime(timezone=True))

    campaign = db.relationship("ReviewCampaign", back_populates="items")
    grant = db.relationship("AccessGrant", back_populates="review_items")
    reviewer = db.relationship("AppUser")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<ReviewItem c={self.campaign_id} g={self.access_grant_id} {self.decision}>"
