"""User model."""
from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import String, BigInteger, Boolean, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class User(Base):
    """
    User model with soft delete support.

    Reference: spec-data-lifecycle.md § 8.1
    """
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    github_id: Mapped[Optional[int]] = mapped_column(BigInteger, unique=True, nullable=True)
    github_login: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Soft delete
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    deleted_email_archived: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
