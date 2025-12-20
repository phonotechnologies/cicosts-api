"""
AWS Lambda handler for CICosts Workers.

Processes:
- EventBridge scheduled jobs (daily sync, trials, cleanup)
- SQS webhook messages
"""
import json
import logging
from typing import Any

from app.workers.handler import handle_scheduled_job, handle_sqs_webhooks

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def handler(event: dict, context: Any) -> dict:
    """Lambda workers entry point."""
    logger.info(f"Received event: {json.dumps(event)[:500]}")

    # EventBridge scheduled job
    if "job_type" in event:
        return handle_scheduled_job(event)

    # SQS webhook processing
    if "Records" in event:
        return handle_sqs_webhooks(event["Records"])

    logger.warning(f"Unknown event type: {event}")
    return {"statusCode": 400, "body": "Unknown event type"}
