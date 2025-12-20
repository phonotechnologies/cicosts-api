"""Workflow run model."""
from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import String, BigInteger, Integer, DateTime, Numeric, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class WorkflowRun(Base):
    """
    GitHub Actions workflow run.

    Reference: spec-cost-calculation.md § 4.3
    """
    __tablename__ = "workflow_runs"

    # Composite primary key for multi-org support
    org_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), primary_key=True)
    github_run_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)

    repo_name: Mapped[str] = mapped_column(String(255))
    repo_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    workflow_name: Mapped[str] = mapped_column(String(255))
    workflow_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    run_number: Mapped[int] = mapped_column(Integer)

    # Status
    status: Mapped[str] = mapped_column(String(50))
    conclusion: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    event: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    triggered_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime] = mapped_column(DateTime)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Cost
    billable_ms: Mapped[int] = mapped_column(BigInteger, default=0)
    cost_usd: Mapped[Decimal] = mapped_column(Numeric(10, 4), default=0)

    created_locally_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
