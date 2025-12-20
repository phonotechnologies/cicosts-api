"""
Email queue handler for async email sending.

Processes email messages from SQS queue with retry logic.
"""
import json
import logging
from typing import Dict, Any, List

from app.services.email_service import get_email_service

logger = logging.getLogger(__name__)


def handle_email_queue(records: List[dict]) -> Dict[str, Any]:
    """
    Process email messages from SQS queue.

    Uses partial batch failure reporting to retry failed sends.

    Args:
        records: List of SQS message records

    Returns:
        Dict with batchItemFailures for retry
    """
    batch_item_failures = []
    email_service = get_email_service()

    for record in records:
        try:
            # Parse message body
            body = json.loads(record["body"])
            email_type = body.get("type")
            payload = body.get("payload", {})
            message_id = record.get("messageId")

            logger.info(f"Processing email: {email_type} (message: {message_id})")

            # Route to appropriate handler
            if email_type == "alert_notification":
                result = _send_alert_notification(email_service, payload)
            elif email_type == "weekly_digest":
                result = _send_weekly_digest(email_service, payload)
            elif email_type == "welcome":
                result = _send_welcome_email(email_service, payload)
            else:
                logger.warning(f"Unknown email type: {email_type}")
                # Don't retry unknown types
                continue

            # Check if send was successful
            if not result.get("success"):
                logger.error(
                    f"Failed to send {email_type} email: {result.get('error')}",
                )
                # Add to batch failures for retry
                batch_item_failures.append({
                    "itemIdentifier": message_id
                })
            else:
                logger.info(f"Successfully sent {email_type} email")

        except json.JSONDecodeError as e:
            logger.error(
                f"Invalid JSON in message {record['messageId']}: {e}",
                exc_info=True
            )
            # Don't retry invalid JSON
            continue

        except Exception as e:
            logger.error(
                f"Error processing email message {record['messageId']}: {e}",
                exc_info=True
            )
            # Add to batch failures for retry
            batch_item_failures.append({
                "itemIdentifier": record["messageId"]
            })

    logger.info(
        f"Email processing complete: {len(records) - len(batch_item_failures)}/{len(records)} successful"
    )

    return {"batchItemFailures": batch_item_failures}


def _send_alert_notification(email_service, payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Send alert notification email.

    Args:
        email_service: EmailService instance
        payload: Alert notification payload with 'alert' and 'trigger'

    Returns:
        Result dict with success status
    """
    alert = payload.get("alert")
    trigger = payload.get("trigger")

    if not alert or not trigger:
        logger.error("Missing alert or trigger in payload")
        return {"success": False, "error": "Missing required data"}

    return email_service.send_alert_notification(alert, trigger)


def _send_weekly_digest(email_service, payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Send weekly digest email.

    Args:
        email_service: EmailService instance
        payload: Digest payload with 'user', 'org', 'cost_summary'

    Returns:
        Result dict with success status
    """
    user = payload.get("user")
    org = payload.get("org")
    cost_summary = payload.get("cost_summary")

    if not all([user, org, cost_summary]):
        logger.error("Missing user, org, or cost_summary in payload")
        return {"success": False, "error": "Missing required data"}

    return email_service.send_weekly_digest(user, org, cost_summary)


def _send_welcome_email(email_service, payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Send welcome email.

    Args:
        email_service: EmailService instance
        payload: Welcome email payload with 'user'

    Returns:
        Result dict with success status
    """
    user = payload.get("user")

    if not user:
        logger.error("Missing user in payload")
        return {"success": False, "error": "Missing user data"}

    return email_service.send_welcome_email(user)


def queue_email(email_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Queue an email for async sending via SQS.

    Args:
        email_type: Type of email (alert_notification, weekly_digest, welcome)
        payload: Email-specific payload

    Returns:
        Dict with queue status
    """
    import boto3
    from app.config import settings

    if not settings.SES_QUEUE_URL:
        logger.warning("SES_QUEUE_URL not configured, skipping queue")
        return {"success": False, "error": "Queue not configured"}

    try:
        sqs = boto3.client('sqs')

        message_body = json.dumps({
            "type": email_type,
            "payload": payload
        })

        response = sqs.send_message(
            QueueUrl=settings.SES_QUEUE_URL,
            MessageBody=message_body
        )

        message_id = response.get('MessageId')
        logger.info(f"Queued {email_type} email: {message_id}")

        return {
            "success": True,
            "message_id": message_id
        }

    except Exception as e:
        logger.error(f"Error queuing email: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e)
        }
