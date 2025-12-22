"""
E2E API Tests - Tests against live dev-api.cicosts.dev

Run with: pytest tests/integration/test_e2e_api.py -v --integration
"""

import pytest

pytestmark = pytest.mark.integration


class TestHealthEndpoints:
    """Test health check endpoints."""

    def test_root_endpoint(self, http_client):
        """Test root endpoint returns API info."""
        response = http_client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "CICosts API"
        assert "version" in data

    def test_health_endpoint(self, http_client):
        """Test health endpoint returns all checks."""
        response = http_client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "checks" in data
        checks = data["checks"]
        assert checks["api"] == "ok"
        assert checks["environment"] in ("dev", "prod", "staging")

    def test_health_database_connected(self, http_client):
        """Test that database is connected."""
        response = http_client.get("/health")
        data = response.json()
        assert data["checks"].get("database") == "ok", "Database should be connected"

    def test_health_redis_connected(self, http_client):
        """Test that Redis is connected."""
        response = http_client.get("/health")
        data = response.json()
        assert data["checks"].get("redis") == "ok", "Redis should be connected"


class TestRateLimiting:
    """Test rate limiting headers."""

    def test_rate_limit_headers_present(self, http_client):
        """Test that rate limit headers are returned."""
        response = http_client.get("/health")
        assert response.status_code == 200
        assert "x-ratelimit-limit" in response.headers
        assert "x-ratelimit-remaining" in response.headers
        assert "x-ratelimit-tier" in response.headers

    def test_rate_limit_values_reasonable(self, http_client):
        """Test that rate limit values are reasonable."""
        response = http_client.get("/health")
        limit = int(response.headers.get("x-ratelimit-limit", "0"))
        remaining = int(response.headers.get("x-ratelimit-remaining", "0"))

        assert limit >= 60, "Rate limit should be at least 60/min"
        assert remaining >= 0, "Remaining should be non-negative"
        assert remaining <= limit, "Remaining should not exceed limit"


class TestAuthEndpoints:
    """Test authentication endpoints."""

    def test_login_redirect(self, http_client):
        """Test login redirects to GitHub."""
        # Don't follow redirects to test the redirect itself
        response = http_client.get("/api/v1/auth/login", follow_redirects=False)
        assert response.status_code == 307
        assert "github.com" in response.headers.get("location", "")

    def test_me_requires_auth(self, http_client):
        """Test /me endpoint requires authentication."""
        response = http_client.get("/api/v1/auth/me")
        assert response.status_code == 401

    def test_refresh_requires_auth(self, http_client):
        """Test refresh endpoint requires authentication."""
        response = http_client.post("/api/v1/auth/refresh")
        assert response.status_code == 401


class TestAuthenticatedEndpoints:
    """Test endpoints that require authentication."""

    def test_dashboard_summary_requires_auth(self, http_client):
        """Test dashboard summary requires auth."""
        response = http_client.get("/api/v1/dashboard/summary")
        assert response.status_code == 401

    def test_alerts_requires_auth(self, http_client):
        """Test alerts endpoint requires auth."""
        response = http_client.get("/api/v1/alerts")
        assert response.status_code == 401

    def test_settings_requires_auth(self, http_client):
        """Test settings endpoint requires auth."""
        response = http_client.get("/api/v1/settings/user")
        assert response.status_code == 401

    def test_limits_requires_auth(self, http_client):
        """Test limits endpoint requires auth."""
        response = http_client.get("/api/v1/limits/usage")
        assert response.status_code == 401


class TestWebhookEndpoints:
    """Test webhook endpoints."""

    def test_github_webhook_requires_signature(self, http_client):
        """Test GitHub webhook requires valid signature."""
        response = http_client.post(
            "/api/v1/webhooks/github",
            json={"action": "test"},
            headers={"X-GitHub-Event": "ping"}
        )
        # Should fail signature verification
        assert response.status_code in (400, 401, 403)

    def test_stripe_webhook_requires_signature(self, http_client):
        """Test Stripe webhook requires valid signature."""
        response = http_client.post(
            "/api/v1/webhooks/stripe",
            json={"type": "test.event"}
        )
        # Should fail signature verification
        assert response.status_code in (400, 401, 403)


class TestCORSHeaders:
    """Test CORS configuration."""

    def test_cors_allows_app_origin(self, http_client):
        """Test CORS allows app.cicosts.dev origin."""
        response = http_client.options(
            "/health",
            headers={
                "Origin": "https://app.cicosts.dev",
                "Access-Control-Request-Method": "GET"
            }
        )
        # Either 200 OK with CORS headers or the actual response
        assert response.status_code in (200, 204)

    def test_cors_allows_dev_origin(self, http_client):
        """Test CORS allows dev.cicosts.dev origin."""
        response = http_client.options(
            "/health",
            headers={
                "Origin": "https://dev.cicosts.dev",
                "Access-Control-Request-Method": "GET"
            }
        )
        assert response.status_code in (200, 204)


class TestWithAuthentication:
    """Tests that require a valid auth token.

    These tests are skipped if INTEGRATION_TEST_TOKEN is not set.
    """

    @pytest.fixture(autouse=True)
    def skip_without_token(self, auth_token):
        """Skip these tests if no auth token is provided."""
        if not auth_token:
            pytest.skip("INTEGRATION_TEST_TOKEN not set")

    def test_me_returns_user_info(self, authenticated_client):
        """Test /me returns current user info."""
        response = authenticated_client.get("/api/v1/auth/me")
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert "github_username" in data
        assert "email" in data

    def test_dashboard_summary(self, authenticated_client):
        """Test dashboard summary returns data."""
        response = authenticated_client.get("/api/v1/dashboard/summary")
        # 200 if org exists, might be 400 if no org_id provided
        assert response.status_code in (200, 400, 422)

    def test_settings_user(self, authenticated_client):
        """Test settings returns user data."""
        response = authenticated_client.get("/api/v1/settings/user")
        assert response.status_code == 200
        data = response.json()
        assert "github_username" in data

    def test_settings_notifications(self, authenticated_client):
        """Test notification settings."""
        response = authenticated_client.get("/api/v1/settings/notifications")
        assert response.status_code == 200
        data = response.json()
        assert "alert_emails_enabled" in data

    def test_settings_organizations(self, authenticated_client):
        """Test organizations list."""
        response = authenticated_client.get("/api/v1/settings/organizations")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_limits_usage(self, authenticated_client):
        """Test limits usage endpoint."""
        response = authenticated_client.get("/api/v1/limits/usage")
        # Might need org_id parameter
        assert response.status_code in (200, 400, 422)

    def test_limits_plan(self, authenticated_client):
        """Test limits plan endpoint."""
        response = authenticated_client.get("/api/v1/limits/plan")
        assert response.status_code in (200, 400, 422)


class TestAPIResponseFormats:
    """Test API response formats and content types."""

    def test_json_content_type(self, http_client):
        """Test responses have JSON content type."""
        response = http_client.get("/health")
        assert "application/json" in response.headers.get("content-type", "")

    def test_error_format(self, http_client):
        """Test error responses have proper format."""
        response = http_client.get("/api/v1/auth/me")
        assert response.status_code == 401
        data = response.json()
        assert "detail" in data

    def test_404_handling(self, http_client):
        """Test 404 returns proper JSON error."""
        response = http_client.get("/api/v1/nonexistent")
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
