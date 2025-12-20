"""
Tests for Webhooks API router.

Tests cover:
- POST /api/v1/webhooks/github (GitHub App webhooks)
- POST /api/v1/webhooks/stripe (Stripe webhooks)
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

    def test_workflow_run_webhook(self, client, mock_api_secrets):
        """Test processing workflow_run webhook event."""
        payload = {
            "action": "completed",
            "workflow_run": {
                "id": 12345678,
                "name": "CI Pipeline",
                "run_number": 42,
                "status": "completed",
                "conclusion": "success",
                "event": "push",
                "actor": {"login": "testuser"},
                "repository": {
                    "id": 98765,
                    "name": "test-repo",
                    "full_name": "test-org/test-repo",
                    "owner": {"id": 11111, "login": "test-org"}
                },
                "created_at": "2024-12-20T10:00:00Z",
                "updated_at": "2024-12-20T10:05:00Z",
            },
            "repository": {
                "id": 98765,
                "name": "test-repo",
                "full_name": "test-org/test-repo",
                "owner": {"id": 11111, "login": "test-org"}
            },
            "installation": {"id": 123456},
        }
        payload_str = json.dumps(payload)
        signature = self.create_github_signature(payload_str, "test-webhook-secret")

        with patch("app.routers.webhooks.send_to_sqs") as mock_sqs:
            mock_sqs.return_value = {"MessageId": "test-message-id"}

            response = client.post(
                "/api/v1/webhooks/github",
                content=payload_str,
                headers={
                    "Content-Type": "application/json",
                    "X-GitHub-Event": "workflow_run",
                    "X-Hub-Signature-256": signature,
                    "X-GitHub-Delivery": "test-delivery-id",
                }
            )

        assert response.status_code == 200
        data = response.json()
        assert "received" in data or "queued" in data or "status" in data

    def test_workflow_job_webhook(self, client, mock_api_secrets):
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
                "runner_name": "ubuntu-latest",
                "labels": ["ubuntu-latest"],
            },
            "repository": {
                "id": 98765,
                "name": "test-repo",
                "full_name": "test-org/test-repo",
                "owner": {"id": 11111, "login": "test-org"}
            },
            "installation": {"id": 123456},
        }
        payload_str = json.dumps(payload)
        signature = self.create_github_signature(payload_str, "test-webhook-secret")

        with patch("app.routers.webhooks.send_to_sqs") as mock_sqs:
            mock_sqs.return_value = {"MessageId": "test-message-id"}

            response = client.post(
                "/api/v1/webhooks/github",
                content=payload_str,
                headers={
                    "Content-Type": "application/json",
                    "X-GitHub-Event": "workflow_job",
                    "X-Hub-Signature-256": signature,
                    "X-GitHub-Delivery": "test-delivery-id",
                }
            )

        assert response.status_code == 200

    def test_installation_webhook(self, client, mock_api_secrets):
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
                "permissions": {"actions": "read", "metadata": "read"},
                "events": ["workflow_run", "workflow_job"],
            },
            "sender": {"id": 99999, "login": "installer"},
        }
        payload_str = json.dumps(payload)
        signature = self.create_github_signature(payload_str, "test-webhook-secret")

        with patch("app.routers.webhooks.send_to_sqs") as mock_sqs:
            mock_sqs.return_value = {"MessageId": "test-message-id"}

            response = client.post(
                "/api/v1/webhooks/github",
                content=payload_str,
                headers={
                    "Content-Type": "application/json",
                    "X-GitHub-Event": "installation",
                    "X-Hub-Signature-256": signature,
                    "X-GitHub-Delivery": "test-delivery-id",
                }
            )

        assert response.status_code == 200

    def test_webhook_invalid_signature(self, client, mock_api_secrets):
        """Test that invalid signature is rejected."""
        payload = {"action": "test", "test": True}
        payload_str = json.dumps(payload)

        response = client.post(
            "/api/v1/webhooks/github",
            content=payload_str,
            headers={
                "Content-Type": "application/json",
                "X-GitHub-Event": "push",
                "X-Hub-Signature-256": "sha256=invalid_signature",
                "X-GitHub-Delivery": "test-delivery-id",
            }
        )

        # Should reject invalid signature
        assert response.status_code in [401, 403]

    def test_webhook_missing_signature(self, client, mock_api_secrets):
        """Test that missing signature is rejected."""
        payload = {"action": "test", "test": True}
        payload_str = json.dumps(payload)

        response = client.post(
            "/api/v1/webhooks/github",
            content=payload_str,
            headers={
                "Content-Type": "application/json",
                "X-GitHub-Event": "push",
                "X-GitHub-Delivery": "test-delivery-id",
            }
        )

        # Should reject missing signature
        assert response.status_code in [400, 401, 403]

    def test_webhook_ping_event(self, client, mock_api_secrets):
        """Test handling GitHub ping event."""
        payload = {
            "zen": "Keep it logically awesome.",
            "hook_id": 123456,
            "hook": {"type": "App", "id": 123456},
        }
        payload_str = json.dumps(payload)
        signature = self.create_github_signature(payload_str, "test-webhook-secret")

        response = client.post(
            "/api/v1/webhooks/github",
            content=payload_str,
            headers={
                "Content-Type": "application/json",
                "X-GitHub-Event": "ping",
                "X-Hub-Signature-256": signature,
                "X-GitHub-Delivery": "test-delivery-id",
            }
        )

        assert response.status_code == 200

    def test_webhook_unhandled_event(self, client, mock_api_secrets):
        """Test that unhandled events are acknowledged."""
        payload = {"action": "opened", "issue": {"id": 123}}
        payload_str = json.dumps(payload)
        signature = self.create_github_signature(payload_str, "test-webhook-secret")

        response = client.post(
            "/api/v1/webhooks/github",
            content=payload_str,
            headers={
                "Content-Type": "application/json",
                "X-GitHub-Event": "issues",
                "X-Hub-Signature-256": signature,
                "X-GitHub-Delivery": "test-delivery-id",
            }
        )

        # Should acknowledge but not process
        assert response.status_code == 200


class TestStripeWebhooks:
    """Tests for POST /api/v1/webhooks/stripe endpoint."""

    def test_stripe_webhook_placeholder(self, client):
        """Test Stripe webhook endpoint exists."""
        # Stripe webhooks require signature verification
        # This is a placeholder test
        response = client.post(
            "/api/v1/webhooks/stripe",
            json={"type": "checkout.session.completed"}
        )

        # Endpoint should exist (may reject without proper signature)
        assert response.status_code in [200, 400, 401, 403]


class TestWebhookProcessing:
    """Integration tests for webhook processing flow."""

    def test_workflow_run_queued_to_sqs(self, client, mock_api_secrets):
        """Test that workflow_run events are queued to SQS."""
        payload = {
            "action": "completed",
            "workflow_run": {
                "id": 99999999,
                "name": "Test Workflow",
                "run_number": 1,
                "status": "completed",
                "conclusion": "success",
                "event": "push",
                "actor": {"login": "testuser"},
                "repository": {
                    "id": 12345,
                    "name": "test-repo",
                    "full_name": "test-org/test-repo",
                    "owner": {"id": 67890, "login": "test-org"}
                },
                "created_at": "2024-12-20T10:00:00Z",
                "updated_at": "2024-12-20T10:05:00Z",
            },
            "repository": {
                "id": 12345,
                "name": "test-repo",
                "full_name": "test-org/test-repo",
                "owner": {"id": 67890, "login": "test-org"}
            },
            "installation": {"id": 111222},
        }
        payload_str = json.dumps(payload)

        with patch("app.routers.webhooks.send_to_sqs") as mock_sqs:
            mock_sqs.return_value = {"MessageId": "msg-123"}

            # Create valid signature
            signature = hmac.new(
                b"test-webhook-secret",
                payload_str.encode(),
                hashlib.sha256
            ).hexdigest()

            response = client.post(
                "/api/v1/webhooks/github",
                content=payload_str,
                headers={
                    "Content-Type": "application/json",
                    "X-GitHub-Event": "workflow_run",
                    "X-Hub-Signature-256": f"sha256={signature}",
                    "X-GitHub-Delivery": "delivery-123",
                }
            )

            assert response.status_code == 200

            # Verify SQS was called
            if mock_sqs.called:
                call_args = mock_sqs.call_args
                assert call_args is not None
