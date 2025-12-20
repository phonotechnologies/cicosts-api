"""
Tests for Settings API router.

Tests cover:
- GET /api/v1/settings/user
- PATCH /api/v1/settings/user
- GET /api/v1/settings/notifications
- PATCH /api/v1/settings/notifications
- GET /api/v1/settings/organizations
- POST /api/v1/settings/organizations/{id}/leave
- DELETE /api/v1/settings/account
"""
import pytest
from uuid import uuid4

from tests.conftest import (
    UserFactory,
    OrganizationFactory,
    OrgMembershipFactory,
)


class TestGetUserSettings:
    """Tests for GET /api/v1/settings/user endpoint."""

    def test_get_user_settings_success(self, authenticated_client):
        """Test retrieving user settings."""
        client, user = authenticated_client

        response = client.get("/api/v1/settings/user")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(user.id)
        assert data["email"] == user.email
        assert data["github_login"] == user.github_login
        assert "weekly_digest_enabled" in data
        assert "alert_emails_enabled" in data

    def test_get_user_settings_unauthenticated(self, client):
        """Test that unauthenticated request returns 401."""
        response = client.get("/api/v1/settings/user")

        assert response.status_code == 401


class TestUpdateUserSettings:
    """Tests for PATCH /api/v1/settings/user endpoint.

    Note: The PATCH /user endpoint is read-only per the implementation.
    It returns the current user without updating anything.
    For updates, use /notifications endpoint.
    """

    def test_patch_user_returns_current_user(self, authenticated_client):
        """Test that PATCH /user returns current user without updates."""
        client, user = authenticated_client

        response = client.patch("/api/v1/settings/user")

        assert response.status_code == 200
        data = response.json()
        # Returns current user data
        assert data["id"] == str(user.id)
        assert data["email"] == user.email

    def test_update_user_settings_unauthenticated(self, client):
        """Test that unauthenticated request returns 401."""
        response = client.patch("/api/v1/settings/user")

        assert response.status_code == 401


class TestGetNotificationSettings:
    """Tests for GET /api/v1/settings/notifications endpoint."""

    def test_get_notification_settings_success(self, authenticated_client):
        """Test retrieving notification settings."""
        client, user = authenticated_client

        response = client.get("/api/v1/settings/notifications")

        assert response.status_code == 200
        data = response.json()
        assert "weekly_digest_enabled" in data
        assert "alert_emails_enabled" in data
        assert "notification_email" in data

    def test_get_notification_settings_unauthenticated(self, client):
        """Test that unauthenticated request returns 401."""
        response = client.get("/api/v1/settings/notifications")

        assert response.status_code == 401


class TestUpdateNotificationSettings:
    """Tests for PATCH /api/v1/settings/notifications endpoint."""

    def test_enable_weekly_digest(self, authenticated_client):
        """Test enabling weekly digest."""
        client, user = authenticated_client

        response = client.patch(
            "/api/v1/settings/notifications",
            json={"weekly_digest_enabled": True}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["weekly_digest_enabled"] is True

    def test_disable_alert_emails(self, authenticated_client):
        """Test disabling alert emails."""
        client, user = authenticated_client

        response = client.patch(
            "/api/v1/settings/notifications",
            json={"alert_emails_enabled": False}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["alert_emails_enabled"] is False

    def test_update_notification_email(self, authenticated_client):
        """Test updating notification email."""
        client, user = authenticated_client

        response = client.patch(
            "/api/v1/settings/notifications",
            json={"notification_email": "alerts@example.com"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["notification_email"] == "alerts@example.com"

    def test_update_all_notification_settings(self, authenticated_client):
        """Test updating all notification settings at once."""
        client, user = authenticated_client

        response = client.patch(
            "/api/v1/settings/notifications",
            json={
                "notification_email": "alerts@example.com",
                "weekly_digest_enabled": True,
                "alert_emails_enabled": True,
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["notification_email"] == "alerts@example.com"
        assert data["weekly_digest_enabled"] is True
        assert data["alert_emails_enabled"] is True

    def test_update_notifications_unauthenticated(self, client):
        """Test that unauthenticated request returns 401."""
        response = client.patch(
            "/api/v1/settings/notifications",
            json={"weekly_digest_enabled": True}
        )

        assert response.status_code == 401


class TestGetOrganizations:
    """Tests for GET /api/v1/settings/organizations endpoint."""

    def test_get_organizations_empty(self, authenticated_client):
        """Test retrieving organizations when user has none."""
        client, user = authenticated_client

        response = client.get("/api/v1/settings/organizations")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0

    def test_get_organizations_with_memberships(self, authenticated_client_with_org):
        """Test retrieving organizations when user has memberships."""
        client, user, org = authenticated_client_with_org

        response = client.get("/api/v1/settings/organizations")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1

        # Find our org
        org_data = next((o for o in data if o["id"] == str(org.id)), None)
        assert org_data is not None
        assert org_data["github_org_slug"] == org.github_org_slug

    def test_get_organizations_unauthenticated(self, client):
        """Test that unauthenticated request returns 401."""
        response = client.get("/api/v1/settings/organizations")

        assert response.status_code == 401


class TestLeaveOrganization:
    """Tests for POST /api/v1/settings/organizations/{id}/leave endpoint."""

    def test_leave_organization_success(self, authenticated_client_with_org, db):
        """Test leaving an organization successfully."""
        client, user, org = authenticated_client_with_org

        # Create a second user as owner so current user can leave
        owner = UserFactory.create(db)
        OrgMembershipFactory.create(db, user_id=owner.id, org_id=org.id, role="owner")
        db.commit()

        response = client.post(f"/api/v1/settings/organizations/{org.id}/leave")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_leave_nonexistent_organization(self, authenticated_client):
        """Test leaving an organization that doesn't exist."""
        client, user = authenticated_client

        fake_id = uuid4()
        response = client.post(f"/api/v1/settings/organizations/{fake_id}/leave")

        assert response.status_code == 404

    def test_leave_organization_not_member(self, authenticated_client, db, mock_api_secrets):
        """Test leaving an organization user is not a member of."""
        client, user = authenticated_client

        # Create an org without adding user as member
        org = OrganizationFactory.create(db)
        db.commit()

        response = client.post(f"/api/v1/settings/organizations/{org.id}/leave")

        assert response.status_code == 404

    def test_leave_organization_unauthenticated(self, client):
        """Test that unauthenticated request returns 401."""
        response = client.post(f"/api/v1/settings/organizations/{uuid4()}/leave")

        assert response.status_code == 401


class TestDeleteAccount:
    """Tests for DELETE /api/v1/settings/account endpoint."""

    def test_delete_account_success(self, authenticated_client):
        """Test deleting account successfully."""
        client, user = authenticated_client

        response = client.delete("/api/v1/settings/account")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_delete_account_unauthenticated(self, client):
        """Test that unauthenticated request returns 401."""
        response = client.delete("/api/v1/settings/account")

        assert response.status_code == 401

    def test_cannot_access_after_delete(self, authenticated_client):
        """Test that user cannot access API after account deletion."""
        client, user = authenticated_client

        # Delete account
        response = client.delete("/api/v1/settings/account")
        assert response.status_code == 200

        # Try to access protected endpoint
        response = client.get("/api/v1/settings/user")
        # Should fail - either 401 or 404
        assert response.status_code in [401, 404]
