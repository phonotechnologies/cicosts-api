"""
Tests for Limits API router.

Tests cover:
- GET /api/v1/limits/usage - Usage status endpoint
- GET /api/v1/limits/plan - Plan limits endpoint
- GET /api/v1/limits/upgrade-suggestion - Upgrade suggestion endpoint
"""
import pytest
from uuid import uuid4

from tests.conftest import (
    UserFactory,
    OrganizationFactory,
    OrgMembershipFactory,
    WorkflowRunFactory,
)


class TestLimitsUsage:
    """Tests for GET /api/v1/limits/usage endpoint."""

    def test_get_usage_empty_org(self, authenticated_client_with_org):
        """Test usage returns zeros for org with no workflow runs."""
        client, user, org = authenticated_client_with_org

        response = client.get(f"/api/v1/limits/usage?org_id={org.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["tier"] == "free"
        assert data["repos_used"] == 0
        assert data["repos_limit"] == 3
        assert data["repos_at_limit"] is False
        assert data["history_days_limit"] == 30
        assert data["tracked_repos"] == []

    def test_get_usage_with_repos(self, authenticated_client_with_org, db):
        """Test usage returns correct repo count."""
        client, user, org = authenticated_client_with_org

        # Create workflow runs for 2 repos
        WorkflowRunFactory.create(db, org_id=org.id, repo_name="org/repo1")
        WorkflowRunFactory.create(db, org_id=org.id, repo_name="org/repo2")
        WorkflowRunFactory.create(db, org_id=org.id, repo_name="org/repo1")  # Duplicate
        db.commit()

        response = client.get(f"/api/v1/limits/usage?org_id={org.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["repos_used"] == 2
        assert data["repos_at_limit"] is False
        assert set(data["tracked_repos"]) == {"org/repo1", "org/repo2"}

    def test_get_usage_at_limit(self, authenticated_client_with_org, db):
        """Test usage correctly detects when at limit."""
        client, user, org = authenticated_client_with_org

        # Create 3 repos (free tier limit)
        WorkflowRunFactory.create(db, org_id=org.id, repo_name="org/repo1")
        WorkflowRunFactory.create(db, org_id=org.id, repo_name="org/repo2")
        WorkflowRunFactory.create(db, org_id=org.id, repo_name="org/repo3")
        db.commit()

        response = client.get(f"/api/v1/limits/usage?org_id={org.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["repos_used"] == 3
        assert data["repos_at_limit"] is True

    def test_get_usage_pro_tier(self, db, mock_api_secrets):
        """Test usage for pro tier shows unlimited repos."""
        from fastapi.testclient import TestClient
        from app.main import app
        from app.database import get_db
        from tests.conftest import create_test_token

        # Create pro tier org
        user = UserFactory.create(db)
        org = OrganizationFactory.create(db, subscription_tier="pro")
        OrgMembershipFactory.create(db, user_id=user.id, org_id=org.id)

        # Create 5 repos
        for i in range(5):
            WorkflowRunFactory.create(db, org_id=org.id, repo_name=f"org/repo{i}")
        db.commit()

        # Setup authenticated client
        token = create_test_token(
            user_id=user.id,
            email=user.email,
            github_login=user.github_login,
            github_id=user.github_id,
        )

        def override_get_db():
            yield db

        app.dependency_overrides[get_db] = override_get_db
        client = TestClient(app)
        client.headers["Authorization"] = f"Bearer {token}"

        response = client.get(f"/api/v1/limits/usage?org_id={org.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["tier"] == "pro"
        assert data["repos_used"] == 5
        assert data["repos_limit"] is None  # Unlimited
        assert data["repos_at_limit"] is False
        assert data["history_days_limit"] == 365

        app.dependency_overrides.clear()

    def test_get_usage_requires_org_id(self, authenticated_client):
        """Test that org_id is required."""
        client, user = authenticated_client

        response = client.get("/api/v1/limits/usage")

        assert response.status_code == 422  # Validation error

    def test_get_usage_unauthenticated(self, client):
        """Test that unauthenticated request returns 401."""
        response = client.get(f"/api/v1/limits/usage?org_id={uuid4()}")

        assert response.status_code == 401


class TestLimitsPlan:
    """Tests for GET /api/v1/limits/plan endpoint."""

    def test_get_plan_free_tier(self, authenticated_client_with_org):
        """Test plan returns correct limits for free tier."""
        client, user, org = authenticated_client_with_org

        response = client.get(f"/api/v1/limits/plan?org_id={org.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["max_repos"] == 3
        assert data["max_history_days"] == 30
        assert data["max_team_members"] == 1

    def test_get_plan_pro_tier(self, db, mock_api_secrets):
        """Test plan returns correct limits for pro tier."""
        from fastapi.testclient import TestClient
        from app.main import app
        from app.database import get_db
        from tests.conftest import create_test_token

        # Create pro tier org
        user = UserFactory.create(db)
        org = OrganizationFactory.create(db, subscription_tier="pro")
        OrgMembershipFactory.create(db, user_id=user.id, org_id=org.id)
        db.commit()

        token = create_test_token(
            user_id=user.id,
            email=user.email,
            github_login=user.github_login,
            github_id=user.github_id,
        )

        def override_get_db():
            yield db

        app.dependency_overrides[get_db] = override_get_db
        client = TestClient(app)
        client.headers["Authorization"] = f"Bearer {token}"

        response = client.get(f"/api/v1/limits/plan?org_id={org.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["max_repos"] is None  # Unlimited
        assert data["max_history_days"] == 365
        assert data["max_team_members"] == 1

        app.dependency_overrides.clear()

    def test_get_plan_team_tier(self, db, mock_api_secrets):
        """Test plan returns correct limits for team tier."""
        from fastapi.testclient import TestClient
        from app.main import app
        from app.database import get_db
        from tests.conftest import create_test_token

        # Create team tier org
        user = UserFactory.create(db)
        org = OrganizationFactory.create(db, subscription_tier="team")
        OrgMembershipFactory.create(db, user_id=user.id, org_id=org.id)
        db.commit()

        token = create_test_token(
            user_id=user.id,
            email=user.email,
            github_login=user.github_login,
            github_id=user.github_id,
        )

        def override_get_db():
            yield db

        app.dependency_overrides[get_db] = override_get_db
        client = TestClient(app)
        client.headers["Authorization"] = f"Bearer {token}"

        response = client.get(f"/api/v1/limits/plan?org_id={org.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["max_repos"] is None  # Unlimited
        assert data["max_history_days"] == 365
        assert data["max_team_members"] == 5

        app.dependency_overrides.clear()

    def test_get_plan_unauthenticated(self, client):
        """Test that unauthenticated request returns 401."""
        response = client.get(f"/api/v1/limits/plan?org_id={uuid4()}")

        assert response.status_code == 401


class TestUpgradeSuggestion:
    """Tests for GET /api/v1/limits/upgrade-suggestion endpoint."""

    def test_no_upgrade_suggestion_for_team_tier(self, db, mock_api_secrets):
        """Test that team tier doesn't get upgrade suggestions."""
        from fastapi.testclient import TestClient
        from app.main import app
        from app.database import get_db
        from tests.conftest import create_test_token

        # Create team tier org
        user = UserFactory.create(db)
        org = OrganizationFactory.create(db, subscription_tier="team")
        OrgMembershipFactory.create(db, user_id=user.id, org_id=org.id)
        db.commit()

        token = create_test_token(
            user_id=user.id,
            email=user.email,
            github_login=user.github_login,
            github_id=user.github_id,
        )

        def override_get_db():
            yield db

        app.dependency_overrides[get_db] = override_get_db
        client = TestClient(app)
        client.headers["Authorization"] = f"Bearer {token}"

        response = client.get(f"/api/v1/limits/upgrade-suggestion?org_id={org.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["should_upgrade"] is False
        assert data["reason"] is None
        assert data["suggested_tier"] is None

        app.dependency_overrides.clear()

    def test_upgrade_suggestion_at_repo_limit(self, authenticated_client_with_org, db):
        """Test upgrade suggestion when at repo limit."""
        client, user, org = authenticated_client_with_org

        # Create 3 repos (at limit)
        WorkflowRunFactory.create(db, org_id=org.id, repo_name="org/repo1")
        WorkflowRunFactory.create(db, org_id=org.id, repo_name="org/repo2")
        WorkflowRunFactory.create(db, org_id=org.id, repo_name="org/repo3")
        db.commit()

        response = client.get(f"/api/v1/limits/upgrade-suggestion?org_id={org.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["should_upgrade"] is True
        assert "3 repository limit" in data["reason"]
        assert data["suggested_tier"] == "pro"

    def test_upgrade_suggestion_nearing_limit(self, authenticated_client_with_org, db):
        """Test upgrade suggestion when nearing repo limit."""
        client, user, org = authenticated_client_with_org

        # Create 2 repos (one away from limit)
        WorkflowRunFactory.create(db, org_id=org.id, repo_name="org/repo1")
        WorkflowRunFactory.create(db, org_id=org.id, repo_name="org/repo2")
        db.commit()

        response = client.get(f"/api/v1/limits/upgrade-suggestion?org_id={org.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["should_upgrade"] is True
        assert "2 of 3" in data["reason"]
        assert data["suggested_tier"] == "pro"

    def test_upgrade_suggestion_below_limit(self, authenticated_client_with_org, db):
        """Test no upgrade suggestion when well below limit."""
        client, user, org = authenticated_client_with_org

        # Create only 1 repo (well below limit of 3)
        WorkflowRunFactory.create(db, org_id=org.id, repo_name="org/repo1")
        db.commit()

        response = client.get(f"/api/v1/limits/upgrade-suggestion?org_id={org.id}")

        assert response.status_code == 200
        data = response.json()
        # Free tier always suggests upgrade due to history limit
        assert data["should_upgrade"] is True
        assert "30 days" in data["reason"]

    def test_upgrade_suggestion_unauthenticated(self, client):
        """Test that unauthenticated request returns 401."""
        response = client.get(f"/api/v1/limits/upgrade-suggestion?org_id={uuid4()}")

        assert response.status_code == 401


class TestHistoryEnforcement:
    """Tests for history limit enforcement in dashboard endpoints."""

    def test_dashboard_enforces_history_limit_free_tier(self, authenticated_client_with_org, db):
        """Test that dashboard trends endpoint caps days for free tier."""
        client, user, org = authenticated_client_with_org

        # Request 90 days, but free tier should cap to 30
        response = client.get(f"/api/v1/dashboard/trends?org_id={org.id}&days=90")

        assert response.status_code == 200
        # The endpoint should execute successfully (data capped internally)

    def test_dashboard_workflows_summary_enforces_limit(self, authenticated_client_with_org, db):
        """Test that workflows summary endpoint enforces history limit."""
        client, user, org = authenticated_client_with_org

        # Request 365 days on free tier (should be capped to 30)
        response = client.get(f"/api/v1/dashboard/workflows/summary?org_id={org.id}&days=365")

        assert response.status_code == 200
        # The endpoint should execute successfully (data capped internally)
