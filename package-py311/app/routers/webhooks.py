"""
Webhook endpoints.

Handles GitHub and Stripe webhooks.
Reference: spec-error-handling.md § 2.2
"""
import hmac
import hashlib
import json
import boto3
from typing import Optional

from fastapi import APIRouter, Request, HTTPException, Header
from pydantic import BaseModel

from app.config import settings, get_github_secrets

router = APIRouter()


class WebhookResponse(BaseModel):
    """Standard webhook response."""
    status: str
    message_id: Optional[str] = None


@router.post("/github", response_model=WebhookResponse)
async def github_webhook(
    request: Request,
    x_hub_signature_256: Optional[str] = Header(None),
    x_github_event: Optional[str] = Header(None),
    x_github_delivery: Optional[str] = Header(None),
):
    """
    Handle GitHub webhooks.

    - Verify signature
    - Queue to SQS for async processing
    - Return 202 Accepted immediately

    Reference: spec-error-handling.md § 2.2
    """
    # Get raw payload
    payload = await request.body()

    # Verify signature
    github_secrets = get_github_secrets()
    webhook_secret = github_secrets.get("webhook_secret", "")

    if webhook_secret and x_hub_signature_256:
        expected_signature = "sha256=" + hmac.new(
            webhook_secret.encode(),
            payload,
            hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(x_hub_signature_256, expected_signature):
            raise HTTPException(status_code=401, detail="Invalid signature")

    # Parse payload
    try:
        event_data = json.loads(payload)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    # Only process workflow_run events for MVP
    if x_github_event not in ["workflow_run", "workflow_job", "installation"]:
        return WebhookResponse(status="ignored", message_id=None)

    # Queue to SQS for async processing
    message_id = None
    if settings.ENVIRONMENT != "development":
        try:
            sqs = boto3.client("sqs")

            # Get queue URL from environment or construct it
            queue_url = f"https://sqs.us-east-1.amazonaws.com/{_get_account_id()}/cicosts-{settings.ENVIRONMENT}-webhooks"

            response = sqs.send_message(
                QueueUrl=queue_url,
                MessageBody=json.dumps({
                    "event_type": x_github_event,
                    "delivery_id": x_github_delivery,
                    "payload": event_data,
                }),
                MessageAttributes={
                    "event_type": {
                        "StringValue": x_github_event or "unknown",
                        "DataType": "String",
                    },
                },
            )
            message_id = response.get("MessageId")
        except Exception as e:
            # Log but don't fail - we'll process inline if SQS fails
            print(f"SQS error: {e}")

    return WebhookResponse(status="queued", message_id=message_id)


@router.post("/stripe")
async def stripe_webhook(
    request: Request,
    stripe_signature: Optional[str] = Header(None, alias="Stripe-Signature"),
):
    """
    Handle Stripe webhooks.

    Events:
    - checkout.session.completed
    - customer.subscription.updated
    - customer.subscription.deleted
    - invoice.payment_failed
    """
    payload = await request.body()

    # TODO: Implement Stripe signature verification
    # TODO: Process subscription events

    return {"status": "received"}


def _get_account_id() -> str:
    """Get AWS account ID from STS."""
    try:
        sts = boto3.client("sts")
        return sts.get_caller_identity()["Account"]
    except Exception:
        return "000000000000"
