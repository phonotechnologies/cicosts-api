"""Alert model."""
from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import String, Numeric, Boolean, DateTime, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column
import enum

from app.database import Base


class AlertType(str, enum.Enum):
    """Alert type enumeration."""
    COST_THRESHOLD = "cost_threshold"
    BUDGET_LIMIT = "budget_limit"
    ANOMALY = "anomaly"


class AlertPeriod(str, enum.Enum):
    """Alert period enumeration."""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class Alert(Base):
    """
    Cost alert configuration.

    Alerts trigger when costs exceed thresholds within a specified period.
    """
    __tablename__ = "alerts"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    org_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Alert configuration
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    alert_type: Mapped[AlertType] = mapped_column(
        SQLEnum(AlertType, name="alert_type_enum", create_type=True),
        nullable=False,
        default=AlertType.COST_THRESHOLD
    )
    threshold_amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        comment="Amount in USD that triggers the alert"
    )
    period: Mapped[AlertPeriod] = mapped_column(
        SQLEnum(AlertPeriod, name="alert_period_enum", create_type=True),
        nullable=False,
        default=AlertPeriod.DAILY
    )

    # Status
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Notification settings
    notify_email: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notify_slack: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    slack_webhook_url: Mapped[Optional[str]] = mapped_column(
        String(512),
        nullable=True,
        comment="Slack webhook URL for notifications"
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )
    last_triggered_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
        comment="Last time this alert was triggered"
    )
