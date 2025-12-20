"""Tests for the alerts system."""
import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from sqlalchemy.orm import Session

from app.models.alert import Alert, AlertType, AlertPeriod
from app.models.alert_trigger import AlertTrigger
from app.models.organization import Organization
from app.models.workflow_run import WorkflowRun
from app.services.alert_service import AlertService


class TestAlertService:
    """Test AlertService functionality."""

    def test_get_period_start_daily(self):
        """Test calculating daily period start."""
        service = AlertService(None)
        end_time = datetime(2024, 12, 20, 15, 30, 45)
        start = service._get_period_start(AlertPeriod.DAILY, end_time)

        assert start == datetime(2024, 12, 20, 0, 0, 0)

    def test_get_period_start_weekly(self):
        """Test calculating weekly period start (Monday)."""
        service = AlertService(None)
        # December 20, 2024 is a Friday
        end_time = datetime(2024, 12, 20, 15, 30, 45)
        start = service._get_period_start(AlertPeriod.WEEKLY, end_time)

        # Should be Monday, December 16, 2024
        assert start == datetime(2024, 12, 16, 0, 0, 0)

    def test_get_period_start_monthly(self):
        """Test calculating monthly period start."""
        service = AlertService(None)
        end_time = datetime(2024, 12, 20, 15, 30, 45)
        start = service._get_period_start(AlertPeriod.MONTHLY, end_time)

        assert start == datetime(2024, 12, 1, 0, 0, 0)


class TestAlertModels:
    """Test Alert and AlertTrigger models."""

    def test_alert_creation(self):
        """Test creating an Alert instance."""
        org_id = uuid4()
        alert = Alert(
            id=uuid4(),
            org_id=org_id,
            name="Test Alert",
            alert_type=AlertType.COST_THRESHOLD,
            threshold_amount=Decimal("100.00"),
            period=AlertPeriod.DAILY,
            enabled=True,
            notify_email=True,
            notify_slack=False,
        )

        assert alert.name == "Test Alert"
        assert alert.alert_type == AlertType.COST_THRESHOLD
        assert alert.threshold_amount == Decimal("100.00")
        assert alert.period == AlertPeriod.DAILY
        assert alert.enabled is True
        assert alert.notify_email is True
        assert alert.notify_slack is False

    def test_alert_trigger_creation(self):
        """Test creating an AlertTrigger instance."""
        alert_id = uuid4()
        trigger = AlertTrigger(
            id=uuid4(),
            alert_id=alert_id,
            triggered_at=datetime.utcnow(),
            actual_amount=Decimal("125.50"),
            threshold_amount=Decimal("100.00"),
            notified=True,
        )

        assert trigger.actual_amount == Decimal("125.50")
        assert trigger.threshold_amount == Decimal("100.00")
        assert trigger.notified is True


class TestAlertTypes:
    """Test alert type and period enums."""

    def test_alert_types(self):
        """Test AlertType enum values."""
        assert AlertType.COST_THRESHOLD == "cost_threshold"
        assert AlertType.BUDGET_LIMIT == "budget_limit"
        assert AlertType.ANOMALY == "anomaly"

    def test_alert_periods(self):
        """Test AlertPeriod enum values."""
        assert AlertPeriod.DAILY == "daily"
        assert AlertPeriod.WEEKLY == "weekly"
        assert AlertPeriod.MONTHLY == "monthly"


# Integration tests would require a test database
# Here's an example structure:

# @pytest.fixture
# def db_session():
#     """Create a test database session."""
#     # Setup test database
#     engine = create_engine("sqlite:///:memory:")
#     Base.metadata.create_all(engine)
#     Session = sessionmaker(bind=engine)
#     session = Session()
#     yield session
#     session.close()
#
# def test_alert_service_check_alerts(db_session):
#     """Test checking alerts with database."""
#     # Create test organization
#     org_id = uuid4()
#     org = Organization(id=org_id, ...)
#     db_session.add(org)
#
#     # Create workflow runs to generate costs
#     run = WorkflowRun(
#         org_id=org_id,
#         cost_usd=Decimal("50.00"),
#         ...
#     )
#     db_session.add(run)
#
#     # Create alert
#     alert = Alert(
#         org_id=org_id,
#         threshold_amount=Decimal("100.00"),
#         period=AlertPeriod.DAILY,
#         enabled=True,
#         ...
#     )
#     db_session.add(alert)
#     db_session.commit()
#
#     # Test alert service
#     service = AlertService(db_session)
#     triggers = service.check_alerts(org_id)
#
#     # Should not trigger (cost is below threshold)
#     assert len(triggers) == 0
