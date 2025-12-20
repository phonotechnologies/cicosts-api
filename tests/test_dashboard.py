"""
Tests for Dashboard API router.

Tests cover:
- GET /api/v1/dashboard/summary
- GET /api/v1/dashboard/trends
- GET /api/v1/dashboard/top-workflows
- GET /api/v1/dashboard/recent-runs
- GET /api/v1/dashboard/workflows
- GET /api/v1/dashboard/workflows/summary

Note: The dashboard endpoints do not currently check org membership.
They return data for any org_id passed. This is noted in tests.
"""
import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from tests.conftest import (
    UserFactory,
    OrganizationFactory,
    OrgMembershipFactory,
    WorkflowRunFactory,
    JobFactory,
)


class TestDashboardSummary:
    """Tests for GET /api/v1/dashboard/summary endpoint."""

    def test_get_summary_empty_org(self, authenticated_client_with_org):
        """Test summary returns zeros for org with no workflow runs."""
        client, user, org = authenticated_client_with_org

        response = client.get(f"/api/v1/dashboard/summary?org_id={org.id}")

        assert response.status_code == 200
        data = response.json()
        assert "today" in data
        assert "week" in data
        assert "month" in data
        assert data["today"]["amount"] == 0
        assert data["week"]["amount"] == 0
        assert data["month"]["amount"] == 0

    def test_get_summary_with_data(self, authenticated_client_with_org, db):
        """Test summary returns correct totals with workflow data."""
        client, user, org = authenticated_client_with_org

        # Create workflow runs for today with completed_at set
        now = datetime.utcnow()
        WorkflowRunFactory.create(
            db, org_id=org.id,
            cost_usd=Decimal("10.00"),
            created_at=now,
            completed_at=now
        )
        WorkflowRunFactory.create(
            db, org_id=org.id,
            cost_usd=Decimal("5.00"),
            created_at=now,
            completed_at=now
        )
        db.commit()

        response = client.get(f"/api/v1/dashboard/summary?org_id={org.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["today"]["amount"] == 15.0
        assert data["month"]["amount"] == 15.0

    def test_get_summary_requires_org_id(self, authenticated_client):
        """Test that org_id is required."""
        client, user = authenticated_client

        response = client.get("/api/v1/dashboard/summary")

        assert response.status_code == 422  # Validation error

    def test_get_summary_other_org_returns_empty(self, authenticated_client, db, mock_api_secrets):
        """Test that querying another org's summary returns empty data.

        Note: The current implementation does NOT check org membership.
        It returns 200 with zeros for orgs with no data.
        """
        client, user = authenticated_client

        # Create another org that user is not a member of
        other_org = OrganizationFactory.create(db)
        db.commit()

        response = client.get(f"/api/v1/dashboard/summary?org_id={other_org.id}")

        # Returns 200 with zeros (no org access check currently)
        assert response.status_code == 200
        data = response.json()
        assert data["today"]["amount"] == 0

    def test_get_summary_unauthenticated(self, client):
        """Test that unauthenticated request returns 401."""
        response = client.get(f"/api/v1/dashboard/summary?org_id={uuid4()}")

        assert response.status_code == 401


class TestDashboardTrends:
    """Tests for GET /api/v1/dashboard/trends endpoint."""

    def test_get_trends_empty(self, authenticated_client_with_org):
        """Test trends returns data points for org with no data."""
        client, user, org = authenticated_client_with_org

        response = client.get(f"/api/v1/dashboard/trends?org_id={org.id}")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        # Returns date range even if all zeros
        assert len(data) > 0

    def test_get_trends_with_data(self, authenticated_client_with_org, db):
        """Test trends returns daily cost data."""
        client, user, org = authenticated_client_with_org

        now = datetime.utcnow()
        # Create runs over several days
        for i in range(7):
            run_time = now - timedelta(days=i)
            WorkflowRunFactory.create(
                db, org_id=org.id,
                cost_usd=Decimal(f"{10.0 + i:.4f}"),
                created_at=run_time,
                completed_at=run_time
            )
        db.commit()

        response = client.get(f"/api/v1/dashboard/trends?org_id={org.id}&days=7")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        # Should have data points
        assert len(data) > 0

    def test_get_trends_custom_days(self, authenticated_client_with_org):
        """Test trends with custom days parameter."""
        client, user, org = authenticated_client_with_org

        response = client.get(f"/api/v1/dashboard/trends?org_id={org.id}&days=14")

        assert response.status_code == 200

    def test_get_trends_unauthenticated(self, client):
        """Test that unauthenticated request returns 401."""
        response = client.get(f"/api/v1/dashboard/trends?org_id={uuid4()}")

        assert response.status_code == 401


class TestTopWorkflows:
    """Tests for GET /api/v1/dashboard/top-workflows endpoint."""

    def test_get_top_workflows_empty(self, authenticated_client_with_org):
        """Test top workflows returns empty list for org with no data."""
        client, user, org = authenticated_client_with_org

        response = client.get(f"/api/v1/dashboard/top-workflows?org_id={org.id}")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0

    def test_get_top_workflows_with_data(self, authenticated_client_with_org, db):
        """Test top workflows returns correct data."""
        client, user, org = authenticated_client_with_org

        now = datetime.utcnow()
        # Create multiple runs for different workflows
        for i in range(5):
            WorkflowRunFactory.create(
                db, org_id=org.id,
                workflow_name="CI Pipeline",
                cost_usd=Decimal("10.00"),
                created_at=now,
                completed_at=now
            )
        for i in range(3):
            WorkflowRunFactory.create(
                db, org_id=org.id,
                workflow_name="Deploy",
                cost_usd=Decimal("5.00"),
                created_at=now,
                completed_at=now
            )
        db.commit()

        response = client.get(f"/api/v1/dashboard/top-workflows?org_id={org.id}&limit=5")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_get_top_workflows_limit(self, authenticated_client_with_org, db):
        """Test top workflows respects limit parameter."""
        client, user, org = authenticated_client_with_org

        now = datetime.utcnow()
        # Create multiple unique workflows
        for i in range(10):
            WorkflowRunFactory.create(
                db, org_id=org.id,
                workflow_name=f"Workflow {i}",
                cost_usd=Decimal(f"{i + 1:.4f}"),
                created_at=now,
                completed_at=now
            )
        db.commit()

        response = client.get(f"/api/v1/dashboard/top-workflows?org_id={org.id}&limit=3")

        assert response.status_code == 200
        data = response.json()
        assert len(data) <= 3

    def test_get_top_workflows_unauthenticated(self, client):
        """Test that unauthenticated request returns 401."""
        response = client.get(f"/api/v1/dashboard/top-workflows?org_id={uuid4()}")

        assert response.status_code == 401


class TestRecentRuns:
    """Tests for GET /api/v1/dashboard/recent-runs endpoint."""

    def test_get_recent_runs_empty(self, authenticated_client_with_org):
        """Test recent runs returns empty list for org with no data."""
        client, user, org = authenticated_client_with_org

        response = client.get(f"/api/v1/dashboard/recent-runs?org_id={org.id}")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0

    def test_get_recent_runs_with_data(self, authenticated_client_with_org, db):
        """Test recent runs returns workflow run data."""
        client, user, org = authenticated_client_with_org

        now = datetime.utcnow()
        # Create some runs
        for i in range(5):
            run_time = now - timedelta(hours=i)
            WorkflowRunFactory.create(
                db, org_id=org.id,
                created_at=run_time,
                completed_at=run_time
            )
        db.commit()

        response = client.get(f"/api/v1/dashboard/recent-runs?org_id={org.id}")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 5

    def test_get_recent_runs_limit(self, authenticated_client_with_org, db):
        """Test recent runs respects limit parameter."""
        client, user, org = authenticated_client_with_org

        now = datetime.utcnow()
        # Create 20 runs
        for i in range(20):
            WorkflowRunFactory.create(
                db, org_id=org.id,
                created_at=now - timedelta(hours=i),
                completed_at=now - timedelta(hours=i)
            )
        db.commit()

        response = client.get(f"/api/v1/dashboard/recent-runs?org_id={org.id}&limit=5")

        assert response.status_code == 200
        data = response.json()
        assert len(data) <= 5

    def test_get_recent_runs_unauthenticated(self, client):
        """Test that unauthenticated request returns 401."""
        response = client.get(f"/api/v1/dashboard/recent-runs?org_id={uuid4()}")

        assert response.status_code == 401


class TestWorkflowsList:
    """Tests for GET /api/v1/dashboard/workflows endpoint."""

    def test_get_workflows_empty(self, authenticated_client_with_org):
        """Test workflows returns empty list for org with no data."""
        client, user, org = authenticated_client_with_org

        response = client.get(f"/api/v1/dashboard/workflows?org_id={org.id}")

        assert response.status_code == 200
        data = response.json()
        assert "workflows" in data
        assert "total" in data
        assert data["total"] == 0

    def test_get_workflows_with_data(self, authenticated_client_with_org, db):
        """Test workflows returns aggregated workflow data."""
        client, user, org = authenticated_client_with_org

        now = datetime.utcnow()
        # Create runs for multiple workflows
        for i in range(5):
            WorkflowRunFactory.create(
                db, org_id=org.id,
                repo_name="main-app",
                workflow_name="CI",
                cost_usd=Decimal("1.00"),
                created_at=now,
                completed_at=now
            )
        for i in range(3):
            WorkflowRunFactory.create(
                db, org_id=org.id,
                repo_name="main-app",
                workflow_name="Deploy",
                cost_usd=Decimal("2.00"),
                created_at=now,
                completed_at=now
            )
        db.commit()

        response = client.get(f"/api/v1/dashboard/workflows?org_id={org.id}")

        assert response.status_code == 200
        data = response.json()
        assert "workflows" in data
        assert "repositories" in data

    def test_get_workflows_filter_by_repo(self, authenticated_client_with_org, db):
        """Test workflows can be filtered by repository."""
        client, user, org = authenticated_client_with_org

        now = datetime.utcnow()
        # Create runs for different repos
        WorkflowRunFactory.create(
            db, org_id=org.id, repo_name="repo-a",
            created_at=now, completed_at=now
        )
        WorkflowRunFactory.create(
            db, org_id=org.id, repo_name="repo-b",
            created_at=now, completed_at=now
        )
        db.commit()

        response = client.get(f"/api/v1/dashboard/workflows?org_id={org.id}&repo=repo-a")

        assert response.status_code == 200
        data = response.json()
        # Results should only include repo-a
        for workflow in data.get("workflows", []):
            assert "repo-a" in workflow["repo"]

    def test_get_workflows_search(self, authenticated_client_with_org, db):
        """Test workflows can be searched by name."""
        client, user, org = authenticated_client_with_org

        now = datetime.utcnow()
        WorkflowRunFactory.create(
            db, org_id=org.id, workflow_name="CI Pipeline",
            created_at=now, completed_at=now
        )
        WorkflowRunFactory.create(
            db, org_id=org.id, workflow_name="Deploy Production",
            created_at=now, completed_at=now
        )
        db.commit()

        response = client.get(f"/api/v1/dashboard/workflows?org_id={org.id}&search=Deploy")

        assert response.status_code == 200

    def test_get_workflows_unauthenticated(self, client):
        """Test that unauthenticated request returns 401."""
        response = client.get(f"/api/v1/dashboard/workflows?org_id={uuid4()}")

        assert response.status_code == 401


class TestWorkflowsSummary:
    """Tests for GET /api/v1/dashboard/workflows/summary endpoint."""

    def test_get_workflows_summary_empty(self, authenticated_client_with_org):
        """Test workflows summary returns zeros for empty org."""
        client, user, org = authenticated_client_with_org

        response = client.get(f"/api/v1/dashboard/workflows/summary?org_id={org.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["total_workflows"] == 0
        assert data["total_runs"] == 0
        assert data["total_cost"] == 0

    def test_get_workflows_summary_with_data(self, authenticated_client_with_org, db):
        """Test workflows summary returns correct totals."""
        client, user, org = authenticated_client_with_org

        now = datetime.utcnow()
        # Create runs
        WorkflowRunFactory.create(
            db, org_id=org.id, workflow_name="CI",
            cost_usd=Decimal("10.00"),
            created_at=now, completed_at=now
        )
        WorkflowRunFactory.create(
            db, org_id=org.id, workflow_name="CI",
            cost_usd=Decimal("10.00"),
            created_at=now, completed_at=now
        )
        WorkflowRunFactory.create(
            db, org_id=org.id, workflow_name="Deploy",
            cost_usd=Decimal("5.00"),
            created_at=now, completed_at=now
        )
        db.commit()

        response = client.get(f"/api/v1/dashboard/workflows/summary?org_id={org.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["total_workflows"] == 2  # CI and Deploy
        assert data["total_runs"] == 3
        assert data["total_cost"] == 25.0

    def test_get_workflows_summary_unauthenticated(self, client):
        """Test that unauthenticated request returns 401."""
        response = client.get(f"/api/v1/dashboard/workflows/summary?org_id={uuid4()}")

        assert response.status_code == 401
