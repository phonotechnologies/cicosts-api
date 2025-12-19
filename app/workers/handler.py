"""
Lambda workers handler.

Processes EventBridge scheduled jobs and SQS webhook messages.
Reference: infrastructure/eventbridge.tf
"""
import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


def handle_scheduled_job(event: dict) -> dict:
    """
    Handle EventBridge scheduled job.

    Jobs:
    - daily_sync: Sync GitHub/AWS costs (2 AM UTC)
    - trial_eligibility_check: Check trial eligibility (2:30 AM UTC)
    - data_cleanup: Delete expired data (3 AM UTC)
    - hard_delete_expired_users: Hard delete after 30 days (4 AM UTC)
    - weekly_digest_email: Send weekly digests (Monday 8 AM UTC)
    - health_check: System health check (every 5 min)
    """
    job_type = event.get("job_type")
    tasks = event.get("tasks", [])

    logger.info(f"Processing scheduled job: {job_type}")

    handlers = {
        "daily_sync": _handle_daily_sync,
        "trial_eligibility_check": _handle_trial_check,
        "data_cleanup": _handle_data_cleanup,
        "hard_delete_expired_users": _handle_hard_delete,
        "weekly_digest_email": _handle_weekly_digest,
        "health_check": _handle_health_check,
    }

    handler_fn = handlers.get(job_type)
    if not handler_fn:
        logger.warning(f"Unknown job type: {job_type}")
        return {"statusCode": 400, "body": f"Unknown job: {job_type}"}

    try:
        result = handler_fn(tasks)
        return {"statusCode": 200, "body": json.dumps(result)}
    except Exception as e:
        logger.error(f"Job {job_type} failed: {e}")
        return {"statusCode": 500, "body": str(e)}


def handle_sqs_webhooks(records: list) -> dict:
    """
    Process webhook messages from SQS queue.

    Uses partial batch failure reporting.
    Reference: spec-error-handling.md § 2.2
    """
    batch_item_failures = []

    for record in records:
        try:
            body = json.loads(record["body"])
            event_type = body.get("event_type")
            payload = body.get("payload", {})

            logger.info(f"Processing webhook: {event_type}")

            if event_type == "workflow_run":
                _process_workflow_run(payload)
            elif event_type == "workflow_job":
                _process_workflow_job(payload)
            elif event_type == "installation":
                _process_installation(payload)
            else:
                logger.info(f"Ignoring event type: {event_type}")

        except Exception as e:
            logger.error(f"Failed to process message {record['messageId']}: {e}")
            batch_item_failures.append({
                "itemIdentifier": record["messageId"]
            })

    return {"batchItemFailures": batch_item_failures}


# Job handlers (stubs for now)

def _handle_daily_sync(tasks: list) -> dict:
    """Sync GitHub and AWS costs."""
    logger.info(f"Running daily sync tasks: {tasks}")
    # TODO: Implement
    return {"status": "completed", "tasks": tasks}


def _handle_trial_check(tasks: list) -> dict:
    """Check trial eligibility for engaged users."""
    logger.info("Checking trial eligibility")
    # TODO: Implement (spec-data-lifecycle.md § 6.3)
    return {"status": "completed", "checked": 0}


def _handle_data_cleanup(tasks: list) -> dict:
    """Delete expired data based on retention policy."""
    logger.info(f"Running data cleanup tasks: {tasks}")
    # TODO: Implement (spec-data-lifecycle.md § 2.2)
    return {"status": "completed", "deleted": 0}


def _handle_hard_delete(tasks: list) -> dict:
    """Hard delete users 30 days after soft delete."""
    logger.info("Processing hard deletes")
    # TODO: Implement (spec-data-lifecycle.md § 8.1)
    return {"status": "completed", "deleted": 0}


def _handle_weekly_digest(tasks: list) -> dict:
    """Send weekly cost digest emails."""
    logger.info("Sending weekly digests")
    # TODO: Implement
    return {"status": "completed", "sent": 0}


def _handle_health_check(tasks: list) -> dict:
    """Check system health."""
    logger.info(f"Running health checks: {tasks}")
    # TODO: Implement (spec-error-handling.md § 7.2)
    return {"status": "ok", "checks": tasks}


# Webhook processors (stubs for now)

def _process_workflow_run(payload: dict) -> None:
    """Process workflow_run webhook."""
    action = payload.get("action")
    run = payload.get("workflow_run", {})

    logger.info(f"Workflow run {run.get('id')}: {action}")

    if action == "completed":
        # TODO: Calculate costs and store
        pass


def _process_workflow_job(payload: dict) -> None:
    """Process workflow_job webhook."""
    action = payload.get("action")
    job = payload.get("workflow_job", {})

    logger.info(f"Workflow job {job.get('id')}: {action}")

    if action == "completed":
        # TODO: Calculate job cost
        pass


def _process_installation(payload: dict) -> None:
    """Process GitHub App installation webhook."""
    action = payload.get("action")
    installation = payload.get("installation", {})

    logger.info(f"Installation {installation.get('id')}: {action}")

    # TODO: Handle install/uninstall
