"""
Tests for Alerts API router.

Tests cover:
- GET /api/v1/alerts (list alerts)
- POST /api/v1/alerts (create alert)
- GET /api/v1/alerts/{id} (get alert)
- PUT /api/v1/alerts/{id} (update alert)
- DELETE /api/v1/alerts/{id} (delete alert)
- GET /api/v1/alerts/{id}/triggers (get alert triggers)
- POST /api/v1/alerts/{id}/check (manually check alert)
"""
import pytest
from datetime import datetime
from decimal import Decimal
from uuid import uuid4

from tests.conftest import (
    UserFactory,
    OrganizationFactory,
    OrgMembershipFactory,
    AlertFactory,
    AlertTriggerFactory,
    WorkflowRunFactory,
)
from app.models.alert import AlertType, AlertPeriod


class TestListAlerts:
    """Tests for GET /api/v1/alerts endpoint."""

    def test_list_alerts_empty(self, authenticated_client_with_org):
        """Test listing alerts when none exist."""
        client, user, org = authenticated_client_with_org

        response = client.get(f"/api/v1/alerts?org_id={org.id}")

        assert response.status_code == 200
        data = response.json()
        assert "alerts" in data
        assert "total" in data
        assert data["total"] == 0
        assert len(data["alerts"]) == 0

    def test_list_alerts_with_data(self, authenticated_client_with_org, db):
        """Test listing alerts returns all alerts for org."""
        client, user, org = authenticated_client_with_org

        # Create alerts
        alert1 = AlertFactory.create(db, org_id=org.id, name="Alert 1")
        alert2 = AlertFactory.create(db, org_id=org.id, name="Alert 2")
        db.commit()

        response = client.get(f"/api/v1/alerts?org_id={org.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["alerts"]) == 2

    def test_list_alerts_requires_org_id(self, authenticated_client):
        """Test that org_id is required."""
        client, user = authenticated_client

        response = client.get("/api/v1/alerts")

        assert response.status_code == 422

    def test_list_alerts_unauthorized_org(self, authenticated_client, db, mock_api_secrets):
        """Test cannot list alerts for org user is not a member of."""
        client, user = authenticated_client

        other_org = OrganizationFactory.create(db)
        AlertFactory.create(db, org_id=other_org.id)
        db.commit()

        response = client.get(f"/api/v1/alerts?org_id={other_org.id}")

        assert response.status_code in [403, 404]

    def test_list_alerts_unauthenticated(self, client):
        """Test that unauthenticated request returns 401."""
        response = client.get(f"/api/v1/alerts?org_id={uuid4()}")

        assert response.status_code == 401


class TestCreateAlert:
    """Tests for POST /api/v1/alerts endpoint."""

    def test_create_alert_success(self, authenticated_client_with_org):
        """Test creating an alert successfully."""
        client, user, org = authenticated_client_with_org

        response = client.post(
            f"/api/v1/alerts?org_id={org.id}",
            json={
                "name": "Daily Cost Alert",
                "alert_type": "cost_threshold",
                "threshold_amount": 100.0,
                "period": "daily",
                "notify_email": True,
            }
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Daily Cost Alert"
        assert data["alert_type"] == "cost_threshold"
        assert float(data["threshold_amount"]) == 100.0
        assert data["period"] == "daily"
        assert data["notify_email"] is True
        assert data["enabled"] is True

    def test_create_alert_budget_limit(self, authenticated_client_with_org):
        """Test creating a budget limit alert."""
        client, user, org = authenticated_client_with_org

        response = client.post(
            f"/api/v1/alerts?org_id={org.id}",
            json={
                "name": "Monthly Budget",
                "alert_type": "budget_limit",
                "threshold_amount": 500.0,
                "period": "monthly",
                "notify_email": True,
                "notify_slack": False,
            }
        )

        assert response.status_code == 201
        data = response.json()
        assert data["alert_type"] == "budget_limit"
        assert data["period"] == "monthly"

    def test_create_alert_with_slack(self, authenticated_client_with_org):
        """Test creating an alert with Slack notification."""
        client, user, org = authenticated_client_with_org

        response = client.post(
            f"/api/v1/alerts?org_id={org.id}",
            json={
                "name": "Slack Alert",
                "alert_type": "cost_threshold",
                "threshold_amount": 50.0,
                "period": "daily",
                "notify_email": False,
                "notify_slack": True,
                "slack_webhook_url": "https://hooks.slack.com/services/T00/B00/XXX",
            }
        )

        assert response.status_code == 201
        data = response.json()
        assert data["notify_slack"] is True
        assert data["slack_webhook_url"] is not None

    def test_create_alert_missing_required_fields(self, authenticated_client_with_org):
        """Test that required fields are validated."""
        client, user, org = authenticated_client_with_org

        response = client.post(
            f"/api/v1/alerts?org_id={org.id}",
            json={
                # Missing name, threshold_amount
            }
        )

        assert response.status_code == 422

    def test_create_alert_invalid_threshold(self, authenticated_client_with_org):
        """Test that negative threshold is rejected."""
        client, user, org = authenticated_client_with_org

        response = client.post(
            f"/api/v1/alerts?org_id={org.id}",
            json={
                "name": "Invalid Alert",
                "alert_type": "cost_threshold",
                "threshold_amount": -100.0,
                "period": "daily",
                "notify_email": True,
            }
        )

        assert response.status_code == 422

    def test_create_alert_unauthenticated(self, client):
        """Test that unauthenticated request returns 401."""
        response = client.post(
            f"/api/v1/alerts?org_id={uuid4()}",
            json={
                "name": "Test Alert",
                "alert_type": "cost_threshold",
                "threshold_amount": 100.0,
                "period": "daily",
                "notify_email": True,
            }
        )

        assert response.status_code == 401


class TestGetAlert:
    """Tests for GET /api/v1/alerts/{id} endpoint."""

    def test_get_alert_success(self, authenticated_client_with_org, db):
        """Test getting an alert by ID."""
        client, user, org = authenticated_client_with_org

        alert = AlertFactory.create(db, org_id=org.id, name="My Alert")
        db.commit()

        response = client.get(f"/api/v1/alerts/{alert.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(alert.id)
        assert data["name"] == "My Alert"

    def test_get_alert_not_found(self, authenticated_client):
        """Test getting non-existent alert returns 404."""
        client, user = authenticated_client

        response = client.get(f"/api/v1/alerts/{uuid4()}")

        assert response.status_code == 404

    def test_get_alert_unauthorized(self, authenticated_client, db, mock_api_secrets):
        """Test cannot get alert from another org."""
        client, user = authenticated_client

        other_org = OrganizationFactory.create(db)
        alert = AlertFactory.create(db, org_id=other_org.id)
        db.commit()

        response = client.get(f"/api/v1/alerts/{alert.id}")

        assert response.status_code in [403, 404]

    def test_get_alert_unauthenticated(self, client):
        """Test that unauthenticated request returns 401."""
        response = client.get(f"/api/v1/alerts/{uuid4()}")

        assert response.status_code == 401


class TestUpdateAlert:
    """Tests for PUT /api/v1/alerts/{id} endpoint."""

    def test_update_alert_name(self, authenticated_client_with_org, db):
        """Test updating alert name."""
        client, user, org = authenticated_client_with_org

        alert = AlertFactory.create(db, org_id=org.id, name="Original Name")
        db.commit()

        response = client.put(
            f"/api/v1/alerts/{alert.id}",
            json={"name": "Updated Name"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Name"

    def test_update_alert_threshold(self, authenticated_client_with_org, db):
        """Test updating alert threshold."""
        client, user, org = authenticated_client_with_org

        alert = AlertFactory.create(db, org_id=org.id, threshold_amount=Decimal("100.00"))
        db.commit()

        response = client.put(
            f"/api/v1/alerts/{alert.id}",
            json={"threshold_amount": 200.0}
        )

        assert response.status_code == 200
        data = response.json()
        assert float(data["threshold_amount"]) == 200.0

    def test_update_alert_enable_disable(self, authenticated_client_with_org, db):
        """Test enabling/disabling alert."""
        client, user, org = authenticated_client_with_org

        alert = AlertFactory.create(db, org_id=org.id, enabled=True)
        db.commit()

        # Disable
        response = client.put(
            f"/api/v1/alerts/{alert.id}",
            json={"enabled": False}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["enabled"] is False

        # Re-enable
        response = client.put(
            f"/api/v1/alerts/{alert.id}",
            json={"enabled": True}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["enabled"] is True

    def test_update_alert_multiple_fields(self, authenticated_client_with_org, db):
        """Test updating multiple alert fields at once."""
        client, user, org = authenticated_client_with_org

        alert = AlertFactory.create(db, org_id=org.id)
        db.commit()

        response = client.put(
            f"/api/v1/alerts/{alert.id}",
            json={
                "name": "New Name",
                "threshold_amount": 150.0,
                "period": "weekly",
                "notify_email": False,
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "New Name"
        assert float(data["threshold_amount"]) == 150.0
        assert data["period"] == "weekly"
        assert data["notify_email"] is False

    def test_update_alert_not_found(self, authenticated_client):
        """Test updating non-existent alert returns 404."""
        client, user = authenticated_client

        response = client.put(
            f"/api/v1/alerts/{uuid4()}",
            json={"name": "Updated"}
        )

        assert response.status_code == 404

    def test_update_alert_unauthenticated(self, client):
        """Test that unauthenticated request returns 401."""
        response = client.put(
            f"/api/v1/alerts/{uuid4()}",
            json={"name": "Updated"}
        )

        assert response.status_code == 401


class TestDeleteAlert:
    """Tests for DELETE /api/v1/alerts/{id} endpoint."""

    def test_delete_alert_success(self, authenticated_client_with_org, db):
        """Test deleting an alert."""
        client, user, org = authenticated_client_with_org

        alert = AlertFactory.create(db, org_id=org.id)
        db.commit()
        alert_id = alert.id

        response = client.delete(f"/api/v1/alerts/{alert_id}")

        assert response.status_code == 204

        # Verify alert is gone
        response = client.get(f"/api/v1/alerts/{alert_id}")
        assert response.status_code == 404

    def test_delete_alert_not_found(self, authenticated_client):
        """Test deleting non-existent alert returns 404."""
        client, user = authenticated_client

        response = client.delete(f"/api/v1/alerts/{uuid4()}")

        assert response.status_code == 404

    def test_delete_alert_unauthenticated(self, client):
        """Test that unauthenticated request returns 401."""
        response = client.delete(f"/api/v1/alerts/{uuid4()}")

        assert response.status_code == 401


class TestGetAlertTriggers:
    """Tests for GET /api/v1/alerts/{id}/triggers endpoint."""

    def test_get_triggers_empty(self, authenticated_client_with_org, db):
        """Test getting triggers when none exist."""
        client, user, org = authenticated_client_with_org

        alert = AlertFactory.create(db, org_id=org.id)
        db.commit()

        response = client.get(f"/api/v1/alerts/{alert.id}/triggers")

        assert response.status_code == 200
        data = response.json()
        assert "triggers" in data
        assert "total" in data
        assert data["total"] == 0

    def test_get_triggers_with_data(self, authenticated_client_with_org, db):
        """Test getting triggers when they exist."""
        client, user, org = authenticated_client_with_org

        alert = AlertFactory.create(db, org_id=org.id)
        trigger1 = AlertTriggerFactory.create(db, alert_id=alert.id)
        trigger2 = AlertTriggerFactory.create(db, alert_id=alert.id)
        db.commit()

        response = client.get(f"/api/v1/alerts/{alert.id}/triggers")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["triggers"]) == 2

    def test_get_triggers_limit(self, authenticated_client_with_org, db):
        """Test triggers respects limit parameter."""
        client, user, org = authenticated_client_with_org

        alert = AlertFactory.create(db, org_id=org.id)
        for _ in range(10):
            AlertTriggerFactory.create(db, alert_id=alert.id)
        db.commit()

        response = client.get(f"/api/v1/alerts/{alert.id}/triggers?limit=5")

        assert response.status_code == 200
        data = response.json()
        assert len(data["triggers"]) <= 5

    def test_get_triggers_not_found(self, authenticated_client):
        """Test getting triggers for non-existent alert returns 404."""
        client, user = authenticated_client

        response = client.get(f"/api/v1/alerts/{uuid4()}/triggers")

        assert response.status_code == 404

    def test_get_triggers_unauthenticated(self, client):
        """Test that unauthenticated request returns 401."""
        response = client.get(f"/api/v1/alerts/{uuid4()}/triggers")

        assert response.status_code == 401


class TestCheckAlert:
    """Tests for POST /api/v1/alerts/{id}/check endpoint."""

    def test_check_alert_no_trigger(self, authenticated_client_with_org, db):
        """Test checking alert that doesn't trigger."""
        client, user, org = authenticated_client_with_org

        now = datetime.utcnow()
        alert = AlertFactory.create(
            db, org_id=org.id,
            threshold_amount=Decimal("100.00"),
            period=AlertPeriod.DAILY
        )
        # Create workflow run with low cost
        WorkflowRunFactory.create(
            db, org_id=org.id, cost_usd=Decimal("10.00"),
            created_at=now, completed_at=now
        )
        db.commit()

        response = client.post(f"/api/v1/alerts/{alert.id}/check")

        assert response.status_code == 200
        data = response.json()
        assert data["triggered"] is False

    def test_check_alert_triggers(self, authenticated_client_with_org, db):
        """Test checking alert that should trigger."""
        client, user, org = authenticated_client_with_org

        now = datetime.utcnow()
        alert = AlertFactory.create(
            db, org_id=org.id,
            threshold_amount=Decimal("50.00"),
            period=AlertPeriod.DAILY
        )
        # Create workflow runs that exceed threshold
        WorkflowRunFactory.create(
            db, org_id=org.id, cost_usd=Decimal("30.00"),
            created_at=now, completed_at=now
        )
        WorkflowRunFactory.create(
            db, org_id=org.id, cost_usd=Decimal("30.00"),
            created_at=now, completed_at=now
        )
        db.commit()

        response = client.post(f"/api/v1/alerts/{alert.id}/check")

        assert response.status_code == 200
        data = response.json()
        assert data["threshold_exceeded"] is True
        assert data["current_cost"] >= 60.0
        assert float(data["threshold"]) == 50.0

    def test_check_alert_disabled(self, authenticated_client_with_org, db):
        """Test checking disabled alert."""
        client, user, org = authenticated_client_with_org

        alert = AlertFactory.create(db, org_id=org.id, enabled=False)
        db.commit()

        response = client.post(f"/api/v1/alerts/{alert.id}/check")

        assert response.status_code == 200
        data = response.json()
        # Disabled alerts return triggered=False
        assert data["triggered"] is False

    def test_check_alert_not_found(self, authenticated_client):
        """Test checking non-existent alert returns 404."""
        client, user = authenticated_client

        response = client.post(f"/api/v1/alerts/{uuid4()}/check")

        assert response.status_code == 404

    def test_check_alert_unauthenticated(self, client):
        """Test that unauthenticated request returns 401."""
        response = client.post(f"/api/v1/alerts/{uuid4()}/check")

        assert response.status_code == 401
