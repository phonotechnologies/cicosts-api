"""
Tests for Webhooks API router.

Tests cover:
- POST /api/v1/webhooks/github (GitHub App webhooks)
- POST /api/v1/webhooks/stripe (Stripe webhooks)
- Signature verification
- Event type handling
"""
import pytest
import hmac
import hashlib
import json
from datetime import datetime
from unittest.mock import patch, MagicMock


class TestGitHubWebhooks:
    """Tests for POST /api/v1/webhooks/github endpoint."""

    def create_github_signature(self, payload: str, secret: str) -> str:
        """Create GitHub webhook signature."""
        signature = hmac.new(
            secret.encode(),
            payload.encode(),
            hashlib.sha256
        ).hexdigest()
        return f"sha256={signature}"

    def test_workflow_run_webhook(self, client):
        """Test processing workflow_run webhook event."""
        payload = {
            "action": "completed",
            "workflow_run": {
                "id": 12345678,
                "name": "CI Pipeline",
                "run_number": 42,
                "status": "completed",
                "conclusion": "success",
            },
            "repository": {
                "id": 98765,
                "name": "test-repo",
                "full_name": "test-org/test-repo",
            },
            "organization": {
                "id": 11111,
                "login": "test-org",
            },
            "installation": {"id": 123456},
        }
        payload_str = json.dumps(payload)

        # Mock to disable signature verification and skip SQS
        mock_secrets = {"webhook_secret": ""}

        with patch("app.routers.webhooks.get_github_secrets", return_value=mock_secrets):
            with patch("app.routers.webhooks.settings") as mock_settings:
                mock_settings.ENVIRONMENT = "development"
                response = client.post(
                    "/api/v1/webhooks/github",
                    content=payload_str,
                    headers={
                        "Content-Type": "application/json",
                        "X-GitHub-Event": "workflow_run",
                        "X-GitHub-Delivery": "test-delivery-id",
                    }
                )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "queued"

    def test_workflow_job_webhook(self, client):
        """Test processing workflow_job webhook event."""
        payload = {
            "action": "completed",
            "workflow_job": {
                "id": 87654321,
                "run_id": 12345678,
                "name": "build",
                "status": "completed",
                "conclusion": "success",
                "started_at": "2024-12-20T10:00:00Z",
                "completed_at": "2024-12-20T10:05:00Z",
                "labels": ["ubuntu-latest"],
            },
            "repository": {
                "id": 98765,
                "name": "test-repo",
            },
            "organization": {
                "id": 11111,
                "login": "test-org",
            },
            "installation": {"id": 123456},
        }
        payload_str = json.dumps(payload)

        mock_secrets = {"webhook_secret": ""}

        with patch("app.routers.webhooks.get_github_secrets", return_value=mock_secrets):
            with patch("app.routers.webhooks.settings") as mock_settings:
                mock_settings.ENVIRONMENT = "development"
                response = client.post(
                    "/api/v1/webhooks/github",
                    content=payload_str,
                    headers={
                        "Content-Type": "application/json",
                        "X-GitHub-Event": "workflow_job",
                        "X-GitHub-Delivery": "test-delivery-id",
                    }
                )

        assert response.status_code == 200

    def test_installation_webhook(self, client):
        """Test processing installation webhook event."""
        payload = {
            "action": "created",
            "installation": {
                "id": 123456,
                "account": {
                    "id": 11111,
                    "login": "test-org",
                    "type": "Organization",
                },
                "target_type": "Organization",
                "repository_selection": "all",
            },
            "sender": {"id": 99999, "login": "installer"},
        }
        payload_str = json.dumps(payload)

        mock_secrets = {"webhook_secret": ""}

        with patch("app.routers.webhooks.get_github_secrets", return_value=mock_secrets):
            with patch("app.routers.webhooks.settings") as mock_settings:
                mock_settings.ENVIRONMENT = "development"
                response = client.post(
                    "/api/v1/webhooks/github",
                    content=payload_str,
                    headers={
                        "Content-Type": "application/json",
                        "X-GitHub-Event": "installation",
                        "X-GitHub-Delivery": "test-delivery-id",
                    }
                )

        assert response.status_code == 200

    def test_webhook_with_valid_signature(self, client):
        """Test webhook with valid signature passes."""
        webhook_secret = "test-secret-key"
        payload = {"action": "completed", "workflow_run": {"id": 123}}
        payload_str = json.dumps(payload)
        signature = self.create_github_signature(payload_str, webhook_secret)

        mock_secrets = {"webhook_secret": webhook_secret}

        with patch("app.routers.webhooks.get_github_secrets", return_value=mock_secrets):
            with patch("app.routers.webhooks.settings") as mock_settings:
                mock_settings.ENVIRONMENT = "development"
                response = client.post(
                    "/api/v1/webhooks/github",
                    content=payload_str,
                    headers={
                        "Content-Type": "application/json",
                        "X-GitHub-Event": "workflow_run",
                        "X-GitHub-Delivery": "test-delivery-id",
                        "X-Hub-Signature-256": signature,
                    }
                )

        assert response.status_code == 200

    def test_webhook_invalid_signature(self, client):
        """Test that invalid signature is rejected."""
        webhook_secret = "test-secret-key"
        payload = {"action": "test", "workflow_run": {"id": 123}}
        payload_str = json.dumps(payload)

        mock_secrets = {"webhook_secret": webhook_secret}

        with patch("app.routers.webhooks.get_github_secrets", return_value=mock_secrets):
            with patch("app.routers.webhooks.settings") as mock_settings:
                mock_settings.ENVIRONMENT = "development"
                response = client.post(
                    "/api/v1/webhooks/github",
                    content=payload_str,
                    headers={
                        "Content-Type": "application/json",
                        "X-GitHub-Event": "workflow_run",
                        "X-Hub-Signature-256": "sha256=invalid_signature",
                        "X-GitHub-Delivery": "test-delivery-id",
                    }
                )

        # Should reject invalid signature
        assert response.status_code == 401

    def test_webhook_missing_signature_no_secret(self, client):
        """Test that missing signature is OK when no secret configured."""
        payload = {"action": "completed", "workflow_run": {"id": 123}}
        payload_str = json.dumps(payload)

        # No webhook secret configured - signature not required
        mock_secrets = {"webhook_secret": ""}

        with patch("app.routers.webhooks.get_github_secrets", return_value=mock_secrets):
            with patch("app.routers.webhooks.settings") as mock_settings:
                mock_settings.ENVIRONMENT = "development"
                response = client.post(
                    "/api/v1/webhooks/github",
                    content=payload_str,
                    headers={
                        "Content-Type": "application/json",
                        "X-GitHub-Event": "workflow_run",
                        "X-GitHub-Delivery": "test-delivery-id",
                    }
                )

        # Should accept when no secret is configured
        assert response.status_code == 200

    def test_webhook_ping_event(self, client):
        """Test handling GitHub ping event (ignored)."""
        payload = {
            "zen": "Keep it logically awesome.",
            "hook_id": 123456,
        }
        payload_str = json.dumps(payload)

        mock_secrets = {"webhook_secret": ""}

        with patch("app.routers.webhooks.get_github_secrets", return_value=mock_secrets):
            with patch("app.routers.webhooks.settings") as mock_settings:
                mock_settings.ENVIRONMENT = "development"
                response = client.post(
                    "/api/v1/webhooks/github",
                    content=payload_str,
                    headers={
                        "Content-Type": "application/json",
                        "X-GitHub-Event": "ping",
                        "X-GitHub-Delivery": "test-delivery-id",
                    }
                )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ignored"

    def test_webhook_unhandled_event(self, client):
        """Test that unhandled events are ignored."""
        payload = {"action": "opened", "issue": {"id": 123}}
        payload_str = json.dumps(payload)

        mock_secrets = {"webhook_secret": ""}

        with patch("app.routers.webhooks.get_github_secrets", return_value=mock_secrets):
            with patch("app.routers.webhooks.settings") as mock_settings:
                mock_settings.ENVIRONMENT = "development"
                response = client.post(
                    "/api/v1/webhooks/github",
                    content=payload_str,
                    headers={
                        "Content-Type": "application/json",
                        "X-GitHub-Event": "issues",
                        "X-GitHub-Delivery": "test-delivery-id",
                    }
                )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ignored"


class TestStripeWebhooks:
    """Tests for POST /api/v1/webhooks/stripe endpoint."""

    def test_stripe_webhook_received(self, client):
        """Test Stripe webhook endpoint exists and receives events."""
        from unittest.mock import patch

        # Mock stripe verification to return a valid event
        with patch("app.services.stripe_service.verify_webhook_signature") as mock_verify:
            mock_verify.return_value = {
                "type": "checkout.session.completed",
                "data": {"object": {}}
            }

            response = client.post(
                "/api/v1/webhooks/stripe",
                json={"type": "checkout.session.completed"},
                headers={"Stripe-Signature": "test_signature"}
            )

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "received"

    def test_stripe_webhook_missing_signature(self, client):
        """Test Stripe webhook rejects requests without signature."""
        response = client.post(
            "/api/v1/webhooks/stripe",
            json={"type": "checkout.session.completed"}
        )

        assert response.status_code == 401
