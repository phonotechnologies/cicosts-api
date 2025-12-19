"""Job model."""
from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import String, BigInteger, DateTime, Numeric, ForeignKey, ForeignKeyConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Job(Base):
    """
    GitHub Actions job within a workflow run.

    Reference: spec-cost-calculation.md § 2.1
    """
    __tablename__ = "jobs"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    github_job_id: Mapped[int] = mapped_column(BigInteger)
    org_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"))
    run_github_id: Mapped[int] = mapped_column(BigInteger)

    repo_name: Mapped[str] = mapped_column(String(255))
    job_name: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(50))
    conclusion: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Runner and cost
    runner_type: Mapped[str] = mapped_column(String(100), default="ubuntu-latest")
    billable_ms: Mapped[int] = mapped_column(BigInteger, default=0)
    cost_usd: Mapped[Decimal] = mapped_column(Numeric(10, 4), default=0)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        ForeignKeyConstraint(
            ["org_id", "run_github_id"],
            ["workflow_runs.org_id", "workflow_runs.github_run_id"],
            ondelete="CASCADE",
        ),
    )
