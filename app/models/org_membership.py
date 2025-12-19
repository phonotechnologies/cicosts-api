"""Organization membership model."""
from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import String, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class OrgMembership(Base):
    """
    Multi-org membership model.

    Reference: spec-data-lifecycle.md § 5.1
    """
    __tablename__ = "org_memberships"

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    org_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), primary_key=True)
    role: Mapped[str] = mapped_column(String(50))  # owner, admin, member, viewer
    invited_by: Mapped[Optional[UUID]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
