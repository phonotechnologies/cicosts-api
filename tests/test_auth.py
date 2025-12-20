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
from unittest.mock import patch, MagicMock

from tests.conftest import (
    UserFactory,
    create_test_token,
    TEST_JWT_SECRET,
)


class TestLogin:
    """Tests for GET /api/v1/auth/login endpoint."""

    def test_login_redirects_to_github(self, client, mock_api_secrets):
        """Test that login redirects to GitHub OAuth."""
        response = client.get("/api/v1/auth/login", follow_redirects=False)

        # Should redirect to GitHub
        assert response.status_code in [302, 307, 200]
        if response.status_code in [302, 307]:
            location = response.headers.get("Location", "")
            assert "github.com" in location or "authorize" in location

    def test_login_includes_client_id(self, client, mock_api_secrets):
        """Test that login URL includes client ID."""
        response = client.get("/api/v1/auth/login", follow_redirects=False)

        # If redirect, check location header
        if response.status_code in [302, 307]:
            location = response.headers.get("Location", "")
            # Should include client_id parameter
            assert "client_id" in location or response.status_code == 200


class TestCallback:
    """Tests for GET /api/v1/auth/callback endpoint."""

    def test_callback_without_code_fails(self, client, mock_api_secrets):
        """Test that callback without code returns error."""
        response = client.get("/api/v1/auth/callback")

        # Should fail without code
        assert response.status_code in [400, 422]

    def test_callback_with_error_returns_error(self, client, mock_api_secrets):
        """Test that callback handles OAuth errors."""
        response = client.get(
            "/api/v1/auth/callback",
            params={"error": "access_denied", "error_description": "User denied access"}
        )

        # Should handle error gracefully
        assert response.status_code in [400, 401, 302, 307]

    def test_callback_with_code_exchanges_token(self, client, mock_api_secrets):
        """Test that callback exchanges code for token."""
        with patch("app.routers.auth.exchange_code_for_token") as mock_exchange:
            mock_exchange.return_value = {
                "access_token": "gho_test_token",
                "token_type": "bearer",
            }

            with patch("app.routers.auth.get_github_user") as mock_user:
                mock_user.return_value = {
                    "id": 12345,
                    "login": "testuser",
                    "email": "test@example.com",
                    "avatar_url": "https://avatars.githubusercontent.com/u/12345",
                }

                response = client.get(
                    "/api/v1/auth/callback",
                    params={"code": "test_auth_code"}
                )

        # Should succeed or redirect
        assert response.status_code in [200, 302, 307]


class TestGetCurrentUser:
    """Tests for GET /api/v1/auth/me endpoint."""

    def test_get_current_user_success(self, authenticated_client):
        """Test getting current authenticated user."""
        client, user = authenticated_client

        response = client.get("/api/v1/auth/me")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(user.id)
        assert data["email"] == user.email
        assert data["github_login"] == user.github_login

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
        assert data.get("success") is True or "message" in data

    def test_logout_unauthenticated(self, client):
        """Test that unauthenticated logout returns 401."""
        response = client.post("/api/v1/auth/logout")

        assert response.status_code == 401


class TestRefreshToken:
    """Tests for POST /api/v1/auth/refresh endpoint."""

    def test_refresh_token_success(self, authenticated_client):
        """Test refreshing token successfully."""
        client, user = authenticated_client

        response = client.post("/api/v1/auth/refresh")

        # Should return new token
        assert response.status_code == 200
        data = response.json()
        assert "token" in data or "access_token" in data

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
