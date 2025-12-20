"""GitHub App installation model."""
from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import String, BigInteger, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class GitHubInstallation(Base):
    """
    GitHub App installation record.

    Tracks which organizations/users have installed the CICosts GitHub App.
    """
    __tablename__ = "github_installations"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    installation_id: Mapped[int] = mapped_column(BigInteger, unique=True)

    # Account info (org or user)
    account_id: Mapped[int] = mapped_column(BigInteger)
    account_type: Mapped[str] = mapped_column(String(50))  # "Organization" or "User"
    account_login: Mapped[str] = mapped_column(String(255))

    # Link to our organization (if exists)
    org_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("organizations.id", ondelete="SET NULL"),
        nullable=True
    )

    # Installation details
    target_type: Mapped[str] = mapped_column(String(50), default="Organization")  # or "User"
    repository_selection: Mapped[str] = mapped_column(String(50), default="all")  # "all" or "selected"

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    suspended_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    suspended_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Permissions snapshot (JSON stored as text)
    permissions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    events: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Timestamps
    installed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    uninstalled_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
