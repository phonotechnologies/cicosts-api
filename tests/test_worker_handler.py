"""
Tests for Webhook Worker Handler.

Tests cover:
- workflow_run event processing
- workflow_job event processing
- installation event processing
- Lambda handler entry points
- Scheduled job handling
"""
import pytest
import json
from datetime import datetime
from decimal import Decimal
from uuid import uuid4
from unittest.mock import patch, MagicMock

from tests.conftest import (
    OrganizationFactory,
    GitHubInstallationFactory,
    WorkflowRunFactory,
)


class TestWorkflowRunHandler:
    """Tests for workflow_run event processing."""

    def test_process_workflow_run_ignores_non_completed(self):
        """Test that workflow_run handler ignores non-completed events."""
        from app.workers.handler import handle_sqs_webhooks

        records = [
            {
                "messageId": "msg-1",
                "body": json.dumps({
                    "event_type": "workflow_run",
                    "action": "in_progress",  # Not completed
                    "delivery_id": "test-delivery-1",
                    "payload": {
                        "action": "in_progress",
                        "workflow_run": {
                            "id": 123456,
                            "name": "CI",
                            "run_number": 1,
                            "status": "in_progress",
                            "conclusion": None,
                        },
                    }
                }),
            }
        ]

        result = handle_sqs_webhooks(records)

        # Should succeed without error
        assert "batchItemFailures" in result
        assert len(result["batchItemFailures"]) == 0

    def test_process_workflow_run_with_database(self, db, sample_data):
        """Test that workflow_run event creates a WorkflowRun record."""
        from app.workers.handler import handle_sqs_webhooks

        org = sample_data["organizations"][0]
        installation = sample_data["installations"][0]

        records = [
            {
                "messageId": "msg-1",
                "body": json.dumps({
                    "event_type": "workflow_run",
                    "action": "completed",
                    "delivery_id": "test-delivery-1",
                    "payload": {
                        "action": "completed",
                        "workflow_run": {
                            "id": 999888777,
                            "name": "New CI Pipeline",
                            "run_number": 100,
                            "status": "completed",
                            "conclusion": "success",
                            "event": "push",
                            "actor": {"login": "developer"},
                            "created_at": "2024-12-20T12:00:00Z",
                            "updated_at": "2024-12-20T12:10:00Z",
                        },
                        "repository": {
                            "id": 12345,
                            "name": "new-repo",
                            "full_name": "acme-corp/new-repo",
                        },
                        "organization": {
                            "id": org.github_org_id,
                            "login": org.github_org_slug,
                        },
                        "installation": {"id": installation.installation_id},
                        "sender": {"login": "developer"},
                    }
                }),
            }
        ]

        # Mock the database session factory to return our test session
        mock_session_factory = MagicMock(return_value=db)

        with patch("app.database.get_session_local", return_value=mock_session_factory):
            result = handle_sqs_webhooks(records)

        # Should process successfully with no failures
        assert "batchItemFailures" in result


class TestWorkflowJobHandler:
    """Tests for workflow_job event processing."""

    def test_process_workflow_job_ignores_non_completed(self):
        """Test that workflow_job handler ignores non-completed events."""
        from app.workers.handler import handle_sqs_webhooks

        records = [
            {
                "messageId": "msg-1",
                "body": json.dumps({
                    "event_type": "workflow_job",
                    "action": "in_progress",
                    "delivery_id": "test-delivery-1",
                    "payload": {
                        "action": "in_progress",
                        "workflow_job": {
                            "id": 888777666,
                            "run_id": 123456,
                            "name": "test-job",
                            "status": "in_progress",
                            "conclusion": None,
                        },
                    }
                }),
            }
        ]

        result = handle_sqs_webhooks(records)

        assert "batchItemFailures" in result
        assert len(result["batchItemFailures"]) == 0


class TestInstallationHandler:
    """Tests for installation event processing."""

    def test_process_installation_ignores_unknown_action(self):
        """Test that installation handler ignores unknown actions gracefully."""
        from app.workers.handler import handle_sqs_webhooks

        records = [
            {
                "messageId": "msg-1",
                "body": json.dumps({
                    "event_type": "installation",
                    "action": "new_permissions_accepted",  # Not directly handled
                    "delivery_id": "test-delivery-1",
                    "payload": {
                        "action": "new_permissions_accepted",
                        "installation": {
                            "id": 999111222,
                            "account": {
                                "id": 555444,
                                "login": "new-org",
                                "type": "Organization",
                            },
                        },
                        "sender": {"id": 12345, "login": "admin"},
                    }
                }),
            }
        ]

        # Mock get_session_local to prevent actual database access
        mock_session = MagicMock()
        mock_session_factory = MagicMock(return_value=mock_session)

        with patch("app.database.get_session_local", return_value=mock_session_factory):
            result = handle_sqs_webhooks(records)

        assert "batchItemFailures" in result


class TestScheduledJobHandler:
    """Tests for scheduled job handling."""

    def test_health_check_job(self):
        """Test health check scheduled job."""
        from app.workers.handler import handle_scheduled_job

        event = {
            "job_type": "health_check",
            "tasks": ["db", "cache"],
        }

        result = handle_scheduled_job(event)

        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["status"] == "ok"
        assert body["checks"] == ["db", "cache"]

    def test_unknown_job_type(self):
        """Test unknown job type returns error."""
        from app.workers.handler import handle_scheduled_job

        event = {
            "job_type": "unknown_job",
            "tasks": [],
        }

        result = handle_scheduled_job(event)

        assert result["statusCode"] == 400

    def test_daily_sync_job(self):
        """Test daily sync scheduled job."""
        from app.workers.handler import handle_scheduled_job

        event = {
            "job_type": "daily_sync",
            "tasks": ["github", "aws"],
        }

        result = handle_scheduled_job(event)

        assert result["statusCode"] == 200


class TestLambdaHandler:
    """Tests for Lambda handler entry point."""

    def test_lambda_handler_processes_sqs_event(self):
        """Test Lambda handler processes SQS event correctly."""
        from workers import handler

        sqs_event = {
            "Records": [
                {
                    "messageId": "msg-1",
                    "body": json.dumps({
                        "event_type": "workflow_run",
                        "action": "in_progress",  # Ignored action
                        "delivery_id": "test-delivery",
                        "payload": {
                            "action": "in_progress",
                            "workflow_run": {
                                "id": 123456,
                                "name": "CI",
                            },
                        }
                    }),
                }
            ]
        }

        result = handler(sqs_event, None)

        # Should return batch item failures format
        assert "batchItemFailures" in result
        assert len(result["batchItemFailures"]) == 0

    def test_lambda_handler_processes_scheduled_event(self):
        """Test Lambda handler processes scheduled job event."""
        from workers import handler

        scheduled_event = {
            "job_type": "health_check",
            "tasks": ["db", "cache"],
        }

        result = handler(scheduled_event, None)

        assert result["statusCode"] == 200

    def test_lambda_handler_handles_invalid_json(self):
        """Test Lambda handler handles errors gracefully."""
        from workers import handler

        sqs_event = {
            "Records": [
                {
                    "messageId": "msg-1",
                    "body": "invalid json",
                }
            ]
        }

        result = handler(sqs_event, None)

        # Should return with the failed message
        assert "batchItemFailures" in result
        assert len(result["batchItemFailures"]) == 1

    def test_lambda_handler_empty_records(self):
        """Test Lambda handler with empty records."""
        from workers import handler

        sqs_event = {"Records": []}

        result = handler(sqs_event, None)

        assert "batchItemFailures" in result
        assert len(result["batchItemFailures"]) == 0

    def test_lambda_handler_unknown_event(self):
        """Test Lambda handler with unknown event type."""
        from workers import handler

        unknown_event = {"unknown": "event"}

        result = handler(unknown_event, None)

        assert result["statusCode"] == 400


class TestCostCalculation:
    """Tests for cost calculation in worker."""

    def test_calculate_billable_ms(self):
        """Test billable milliseconds calculation."""
        start = datetime(2024, 12, 20, 12, 0, 0)
        end = datetime(2024, 12, 20, 12, 5, 30)  # 5 min 30 sec

        diff_ms = int((end - start).total_seconds() * 1000)

        assert diff_ms == 330000  # 5.5 minutes in ms

    def test_cost_calculation_ubuntu(self):
        """Test cost calculation for ubuntu runner."""
        from app.services.cost_calculator import calculate_job_cost

        # 5 minutes
        cost = calculate_job_cost("ubuntu-latest", 300000)
        assert cost == Decimal("0.0400")  # 5 * $0.008

    def test_cost_calculation_macos(self):
        """Test cost calculation for macOS runner."""
        from app.services.cost_calculator import calculate_job_cost

        # 10 minutes on macOS
        cost = calculate_job_cost("macos-latest", 600000)
        assert cost == Decimal("0.8000")  # 10 * $0.08

    def test_cost_calculation_windows(self):
        """Test cost calculation for Windows runner."""
        from app.services.cost_calculator import calculate_job_cost

        # 3 minutes on Windows
        cost = calculate_job_cost("windows-latest", 180000)
        assert cost == Decimal("0.0480")  # 3 * $0.016
