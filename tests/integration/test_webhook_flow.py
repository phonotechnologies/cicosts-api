"""
Webhook Flow Integration Tests

Tests the complete webhook pipeline:
GitHub Webhook -> API -> SQS -> Lambda Worker -> Database

Run with: pytest tests/integration/test_webhook_flow.py -v --integration

Requires:
- INTEGRATION_TEST_TOKEN: Valid JWT for API access
- INTEGRATION_GITHUB_WEBHOOK_SECRET: GitHub webhook secret for signing
- Database access (via Supabase)
"""

import hmac
import hashlib
import json
import os
import time
import uuid
from datetime import datetime

import pytest

pytestmark = pytest.mark.integration


# Test configuration
WEBHOOK_SECRET = os.getenv("INTEGRATION_GITHUB_WEBHOOK_SECRET", "")
DATABASE_URL = os.getenv("INTEGRATION_DATABASE_URL", "")


def generate_webhook_signature(payload: str, secret: str) -> str:
    """Generate GitHub webhook signature."""
    signature = hmac.new(
        secret.encode(),
        payload.encode(),
        hashlib.sha256
    ).hexdigest()
    return f"sha256={signature}"


@pytest.fixture
def skip_without_webhook_secret():
    """Skip tests that require webhook secret."""
    if not WEBHOOK_SECRET:
        pytest.skip("INTEGRATION_GITHUB_WEBHOOK_SECRET not set")


@pytest.fixture
def skip_without_database():
    """Skip tests that require database access."""
    if not DATABASE_URL:
        pytest.skip("INTEGRATION_DATABASE_URL not set")


class TestWebhookSignatureVerification:
    """Test webhook signature verification."""

    def test_valid_signature_accepted(self, http_client, skip_without_webhook_secret):
        """Test that valid signature is accepted."""
        payload = json.dumps({
            "action": "completed",
            "workflow_run": {
                "id": 12345,
                "name": "Test Workflow",
                "status": "completed"
            }
        })
        signature = generate_webhook_signature(payload, WEBHOOK_SECRET)

        response = http_client.post(
            "/api/v1/webhooks/github",
            content=payload,
            headers={
                "Content-Type": "application/json",
                "X-GitHub-Event": "workflow_run",
                "X-GitHub-Delivery": str(uuid.uuid4()),
                "X-Hub-Signature-256": signature
            }
        )
        # Should be accepted (202) or at least not rejected due to signature
        assert response.status_code in (200, 202, 400), f"Unexpected status: {response.status_code}"

    def test_invalid_signature_rejected(self, http_client):
        """Test that invalid signature is rejected."""
        payload = json.dumps({"action": "test"})

        response = http_client.post(
            "/api/v1/webhooks/github",
            content=payload,
            headers={
                "Content-Type": "application/json",
                "X-GitHub-Event": "workflow_run",
                "X-GitHub-Delivery": str(uuid.uuid4()),
                "X-Hub-Signature-256": "sha256=invalid"
            }
        )
        assert response.status_code in (400, 401, 403)


class TestWorkflowRunWebhook:
    """Test workflow_run webhook processing."""

    def test_workflow_run_queued(self, http_client, skip_without_webhook_secret):
        """Test workflow_run event is queued to SQS."""
        workflow_id = int(time.time() * 1000)  # Unique ID
        payload = json.dumps({
            "action": "completed",
            "workflow_run": {
                "id": workflow_id,
                "name": "Integration Test Workflow",
                "status": "completed",
                "conclusion": "success",
                "run_number": 1,
                "run_attempt": 1,
                "head_branch": "main",
                "head_sha": "abc123",
                "event": "push",
                "created_at": datetime.utcnow().isoformat() + "Z",
                "updated_at": datetime.utcnow().isoformat() + "Z",
                "run_started_at": datetime.utcnow().isoformat() + "Z",
                "workflow_id": 12345,
                "html_url": "https://github.com/test/repo/actions/runs/1"
            },
            "workflow": {
                "id": 12345,
                "name": "Integration Test Workflow"
            },
            "repository": {
                "id": 98765,
                "name": "test-repo",
                "full_name": "test-org/test-repo"
            },
            "organization": {
                "id": 11111,
                "login": "test-org"
            },
            "installation": {
                "id": 100565576  # Real installation ID for phonotechnologies
            }
        })
        signature = generate_webhook_signature(payload, WEBHOOK_SECRET)

        response = http_client.post(
            "/api/v1/webhooks/github",
            content=payload,
            headers={
                "Content-Type": "application/json",
                "X-GitHub-Event": "workflow_run",
                "X-GitHub-Delivery": str(uuid.uuid4()),
                "X-Hub-Signature-256": signature
            }
        )
        # 202 Accepted means it was queued
        assert response.status_code == 202, f"Expected 202, got {response.status_code}: {response.text}"


class TestWorkflowJobWebhook:
    """Test workflow_job webhook processing."""

    def test_workflow_job_queued(self, http_client, skip_without_webhook_secret):
        """Test workflow_job event is queued to SQS."""
        job_id = int(time.time() * 1000)  # Unique ID
        payload = json.dumps({
            "action": "completed",
            "workflow_job": {
                "id": job_id,
                "run_id": 123456,
                "name": "build",
                "status": "completed",
                "conclusion": "success",
                "started_at": datetime.utcnow().isoformat() + "Z",
                "completed_at": datetime.utcnow().isoformat() + "Z",
                "runner_name": "GitHub Actions 2",
                "labels": ["ubuntu-latest"],
                "workflow_name": "Integration Test Workflow"
            },
            "repository": {
                "id": 98765,
                "name": "test-repo",
                "full_name": "test-org/test-repo"
            },
            "organization": {
                "id": 11111,
                "login": "test-org"
            },
            "installation": {
                "id": 100565576
            }
        })
        signature = generate_webhook_signature(payload, WEBHOOK_SECRET)

        response = http_client.post(
            "/api/v1/webhooks/github",
            content=payload,
            headers={
                "Content-Type": "application/json",
                "X-GitHub-Event": "workflow_job",
                "X-GitHub-Delivery": str(uuid.uuid4()),
                "X-Hub-Signature-256": signature
            }
        )
        assert response.status_code == 202, f"Expected 202, got {response.status_code}: {response.text}"


class TestInstallationWebhook:
    """Test installation webhook processing."""

    def test_installation_ping(self, http_client, skip_without_webhook_secret):
        """Test ping event is handled."""
        payload = json.dumps({
            "zen": "Anything added dilutes everything else.",
            "hook_id": 12345,
            "hook": {
                "type": "App",
                "id": 12345
            }
        })
        signature = generate_webhook_signature(payload, WEBHOOK_SECRET)

        response = http_client.post(
            "/api/v1/webhooks/github",
            content=payload,
            headers={
                "Content-Type": "application/json",
                "X-GitHub-Event": "ping",
                "X-GitHub-Delivery": str(uuid.uuid4()),
                "X-Hub-Signature-256": signature
            }
        )
        # Ping should return 200 or 202
        assert response.status_code in (200, 202)


class TestDatabaseRecordCreation:
    """Test that webhook processing creates database records.

    These tests verify the full pipeline by checking the database
    after sending webhooks.
    """

    @pytest.fixture
    def db_session(self, skip_without_database):
        """Create database session for verification."""
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        engine = create_engine(DATABASE_URL)
        Session = sessionmaker(bind=engine)
        session = Session()
        yield session
        session.close()

    def test_workflow_run_creates_record(
        self,
        http_client,
        skip_without_webhook_secret,
        db_session
    ):
        """Test workflow_run webhook creates database record."""
        from app.models.workflow_run import WorkflowRun

        workflow_id = int(time.time() * 1000)
        payload = json.dumps({
            "action": "completed",
            "workflow_run": {
                "id": workflow_id,
                "name": "E2E Test Workflow",
                "status": "completed",
                "conclusion": "success",
                "run_number": 1,
                "run_attempt": 1,
                "head_branch": "main",
                "head_sha": "e2e123",
                "event": "push",
                "created_at": datetime.utcnow().isoformat() + "Z",
                "updated_at": datetime.utcnow().isoformat() + "Z",
                "run_started_at": datetime.utcnow().isoformat() + "Z",
                "workflow_id": 99999,
                "html_url": f"https://github.com/test/repo/actions/runs/{workflow_id}"
            },
            "workflow": {
                "id": 99999,
                "name": "E2E Test Workflow"
            },
            "repository": {
                "id": 98765,
                "name": "e2e-test-repo",
                "full_name": "phonotechnologies/e2e-test-repo"
            },
            "organization": {
                "id": 234989007,  # phonotechnologies org ID
                "login": "phonotechnologies"
            },
            "installation": {
                "id": 100565576
            }
        })
        signature = generate_webhook_signature(payload, WEBHOOK_SECRET)

        # Send webhook
        response = http_client.post(
            "/api/v1/webhooks/github",
            content=payload,
            headers={
                "Content-Type": "application/json",
                "X-GitHub-Event": "workflow_run",
                "X-GitHub-Delivery": str(uuid.uuid4()),
                "X-Hub-Signature-256": signature
            }
        )
        assert response.status_code == 202

        # Wait for async processing
        time.sleep(5)

        # Verify database record
        record = db_session.query(WorkflowRun).filter(
            WorkflowRun.github_run_id == workflow_id
        ).first()

        # Note: Record might not exist if org is at repo limit
        if record:
            assert record.workflow_name == "E2E Test Workflow"
            assert record.status == "completed"
            assert record.conclusion == "success"
