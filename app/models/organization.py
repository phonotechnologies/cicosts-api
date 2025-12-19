"""Organization model."""
from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import String, BigInteger, Boolean, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Organization(Base):
    """
    Organization (GitHub org) model.

    Reference: spec-data-lifecycle.md § 5
    """
    __tablename__ = "organizations"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    github_org_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    github_org_slug: Mapped[str] = mapped_column(String(255))
    github_org_name: Mapped[str] = mapped_column(String(255))
    billing_email: Mapped[str] = mapped_column(String(255))

    # Subscription
    subscription_tier: Mapped[str] = mapped_column(String(50), default="free")
    stripe_customer_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Trial (ref: spec-data-lifecycle.md § 6.3)
    signup_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    trial_eligible: Mapped[bool] = mapped_column(Boolean, default=True)
    trial_start_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    trial_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    trial_converted: Mapped[bool] = mapped_column(Boolean, default=False)

    # AWS integration
    aws_account_id: Mapped[Optional[str]] = mapped_column(String(12), nullable=True)
    aws_syncing_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    aws_last_sync_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
