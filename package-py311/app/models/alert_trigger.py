"""Alert trigger model."""
from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import Numeric, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AlertTrigger(Base):
    """
    Alert trigger event record.

    Tracks when an alert was triggered, the actual amount, and notification status.
    """
    __tablename__ = "alert_triggers"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    alert_id: Mapped[UUID] = mapped_column(
        ForeignKey("alerts.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Trigger details
    triggered_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
        index=True,
        comment="When the alert was triggered"
    )
    actual_amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        comment="Actual cost amount that triggered the alert (USD)"
    )
    threshold_amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        comment="Threshold amount at time of trigger (USD)"
    )

    # Notification status
    notified: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Whether notifications were sent successfully"
    )
