"""
Tests for Auth API router.

Tests cover:
- GET /api/v1/auth/login (initiate OAuth flow)
- GET /api/v1/auth/callback (OAuth callback)
- GET /api/v1/auth/me (get current user)
- POST /api/v1/auth/logout
- POST /api/v1/auth/refresh (refresh token)
"""
import pytest
from datetime import datetime, timedelta
from uuid import uuid4
from unittest.mock import patch, MagicMock, AsyncMock

from tests.conftest import (
    UserFactory,
    OrganizationFactory,
    OrgMembershipFactory,
    create_test_token,
    TEST_JWT_SECRET,
)


class TestLogin:
    """Tests for GET /api/v1/auth/login endpoint."""

    def test_login_redirects_to_github(self, client):
        """Test that login redirects to GitHub OAuth."""
        # Mock the secrets and settings
        mock_github_secrets = {"client_id": "test-client-id", "client_secret": "test-secret"}
        mock_api_secrets = {"jwt_secret": TEST_JWT_SECRET}

        with patch("app.routers.auth.get_github_secrets", return_value=mock_github_secrets):
            with patch("app.routers.auth.settings") as mock_settings:
                mock_settings.GITHUB_CLIENT_ID = "test-client-id"
                mock_settings.FRONTEND_URL = "http://localhost:3000"
                mock_settings.API_URL = "http://localhost:8000"

                response = client.get("/api/v1/auth/login", follow_redirects=False)

        # Should redirect to GitHub
        assert response.status_code in [302, 307]
        location = response.headers.get("Location", "")
        assert "github.com" in location
        assert "client_id" in location

    def test_login_includes_state(self, client):
        """Test that login URL includes state parameter."""
        mock_github_secrets = {"client_id": "test-client-id", "client_secret": "test-secret"}

        with patch("app.routers.auth.get_github_secrets", return_value=mock_github_secrets):
            with patch("app.routers.auth.settings") as mock_settings:
                mock_settings.GITHUB_CLIENT_ID = "test-client-id"
                mock_settings.FRONTEND_URL = "http://localhost:3000"
                mock_settings.API_URL = "http://localhost:8000"

                response = client.get("/api/v1/auth/login", follow_redirects=False)

        location = response.headers.get("Location", "")
        assert "state=" in location


class TestCallback:
    """Tests for GET /api/v1/auth/callback endpoint."""

    def test_callback_without_code_fails(self, client):
        """Test that callback without code returns error."""
        response = client.get("/api/v1/auth/callback?state=test-state")

        # Should fail without code (422 for validation error)
        assert response.status_code == 422

    def test_callback_requires_state(self, client):
        """Test that callback requires state parameter."""
        response = client.get("/api/v1/auth/callback?code=test-code")

        # Should fail without state (422 for validation error)
        assert response.status_code == 422


class TestGetCurrentUser:
    """Tests for GET /api/v1/auth/me endpoint."""

    def test_get_current_user_success(self, authenticated_client_with_org):
        """Test getting current authenticated user."""
        client, user, org = authenticated_client_with_org

        response = client.get("/api/v1/auth/me")

        assert response.status_code == 200
        data = response.json()
        # Response has nested user object
        assert "user" in data
        assert data["user"]["id"] == str(user.id)
        assert data["user"]["email"] == user.email
        assert data["user"]["github_login"] == user.github_login
        # Also has organizations
        assert "organizations" in data

    def test_get_current_user_unauthenticated(self, client):
        """Test that unauthenticated request returns 401."""
        response = client.get("/api/v1/auth/me")

        assert response.status_code == 401

    def test_get_current_user_invalid_token(self, client, db, mock_api_secrets):
        """Test that invalid token returns 401."""
        from app.database import get_db

        def override_get_db():
            try:
                yield db
            finally:
                pass

        from app.main import app
        app.dependency_overrides[get_db] = override_get_db

        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer invalid_token"}
        )

        assert response.status_code == 401

        app.dependency_overrides.clear()

    def test_get_current_user_expired_token(self, db, mock_api_secrets):
        """Test that expired token returns 401."""
        from fastapi.testclient import TestClient
        from app.main import app
        from app.database import get_db

        user = UserFactory.create(db)
        db.commit()

        # Create expired token
        token = create_test_token(
            user_id=user.id,
            expires_delta=timedelta(hours=-1)  # Expired 1 hour ago
        )

        def override_get_db():
            try:
                yield db
            finally:
                pass

        app.dependency_overrides[get_db] = override_get_db

        client = TestClient(app)
        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 401

        app.dependency_overrides.clear()


class TestLogout:
    """Tests for POST /api/v1/auth/logout endpoint."""

    def test_logout_success(self, authenticated_client):
        """Test logout successfully."""
        client, user = authenticated_client

        response = client.post("/api/v1/auth/logout")

        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "Logout" in data["message"] or "logout" in data["message"].lower()

    def test_logout_works_without_auth(self, client):
        """Test that logout works even without auth (stateless JWT)."""
        response = client.post("/api/v1/auth/logout")

        # Logout is stateless - works without auth
        assert response.status_code == 200


class TestRefreshToken:
    """Tests for POST /api/v1/auth/refresh endpoint."""

    def test_refresh_token_success(self, authenticated_client, mock_api_secrets):
        """Test refreshing token successfully."""
        client, user = authenticated_client

        with patch("app.routers.auth.get_api_secrets", return_value={"jwt_secret": TEST_JWT_SECRET}):
            response = client.post("/api/v1/auth/refresh")

        # Should return new token
        assert response.status_code == 200
        data = response.json()
        assert "token" in data

    def test_refresh_token_unauthenticated(self, client):
        """Test that unauthenticated refresh returns 401."""
        response = client.post("/api/v1/auth/refresh")

        assert response.status_code == 401


class TestTokenValidation:
    """Tests for JWT token validation."""

    def test_valid_token_accepted(self, db, mock_api_secrets):
        """Test that valid token is accepted."""
        from fastapi.testclient import TestClient
        from app.main import app
        from app.database import get_db

        user = UserFactory.create(db)
        db.commit()

        token = create_test_token(user_id=user.id)

        def override_get_db():
            try:
                yield db
            finally:
                pass

        app.dependency_overrides[get_db] = override_get_db

        client = TestClient(app)
        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200

        app.dependency_overrides.clear()

    def test_malformed_token_rejected(self, db, mock_api_secrets):
        """Test that malformed token is rejected."""
        from fastapi.testclient import TestClient
        from app.main import app
        from app.database import get_db

        def override_get_db():
            try:
                yield db
            finally:
                pass

        app.dependency_overrides[get_db] = override_get_db

        client = TestClient(app)
        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer not.a.valid.jwt.token"}
        )

        assert response.status_code == 401

        app.dependency_overrides.clear()

    def test_missing_authorization_header(self, client):
        """Test that missing auth header returns 401."""
        response = client.get("/api/v1/auth/me")

        assert response.status_code == 401

    def test_wrong_auth_scheme(self, client):
        """Test that wrong auth scheme returns 401."""
        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Basic dXNlcjpwYXNz"}
        )

        assert response.status_code in [401, 403]
