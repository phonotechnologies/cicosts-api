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
    - customer.subscription.created
    - customer.subscription.updated
    - customer.subscription.deleted
    - invoice.paid
    - invoice.payment_failed
    """
    from uuid import UUID
    from datetime import datetime
    from app.database import get_session_local
    from app.models.organization import Organization
    from app.services import stripe_service

    payload = await request.body()

    # Verify signature
    if not stripe_signature:
        raise HTTPException(status_code=401, detail="Missing Stripe signature")

    try:
        event = stripe_service.verify_webhook_signature(payload, stripe_signature)
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid signature: {str(e)}")

    event_type = event.get("type", "")
    data = event.get("data", {}).get("object", {})

    # Get database session
    SessionLocal = get_session_local()
    db = SessionLocal()

    try:
        if event_type == "checkout.session.completed":
            # User completed checkout - create/update subscription
            org_id = data.get("metadata", {}).get("org_id")
            customer_id = data.get("customer")
            subscription_id = data.get("subscription")

            if org_id and customer_id:
                org = db.query(Organization).filter(Organization.id == UUID(org_id)).first()
                if org:
                    # Get subscription to determine tier
                    subscription = stripe_service.get_subscription(subscription_id)
                    price_id = subscription.get("items", {}).get("data", [{}])[0].get("price", {}).get("id", "")
                    tier = stripe_service.determine_tier_from_price(price_id)

                    org.stripe_customer_id = customer_id
                    org.subscription_tier = tier
                    org.trial_converted = True
                    db.commit()
                    print(f"[Stripe] Org {org_id} upgraded to {tier}")

        elif event_type == "customer.subscription.created":
            # New subscription created
            customer_id = data.get("customer")
            price_id = data.get("items", {}).get("data", [{}])[0].get("price", {}).get("id", "")
            org_id = data.get("metadata", {}).get("org_id")

            if org_id:
                org = db.query(Organization).filter(Organization.id == UUID(org_id)).first()
                if org:
                    tier = stripe_service.determine_tier_from_price(price_id)
                    org.subscription_tier = tier
                    org.stripe_customer_id = customer_id
                    db.commit()
                    print(f"[Stripe] Subscription created for org {org_id}: {tier}")

        elif event_type == "customer.subscription.updated":
            # Subscription changed (upgrade/downgrade)
            customer_id = data.get("customer")
            status = data.get("status")
            price_id = data.get("items", {}).get("data", [{}])[0].get("price", {}).get("id", "")

            org = db.query(Organization).filter(
                Organization.stripe_customer_id == customer_id
            ).first()

            if org:
                if status == "active":
                    tier = stripe_service.determine_tier_from_price(price_id)
                    org.subscription_tier = tier
                elif status in ["canceled", "unpaid", "past_due"]:
                    org.subscription_tier = "free"
                db.commit()
                print(f"[Stripe] Subscription updated for org {org.id}: {org.subscription_tier}")

        elif event_type == "customer.subscription.deleted":
            # Subscription canceled
            customer_id = data.get("customer")

            org = db.query(Organization).filter(
                Organization.stripe_customer_id == customer_id
            ).first()

            if org:
                org.subscription_tier = "free"
                db.commit()
                print(f"[Stripe] Subscription deleted for org {org.id}")

        elif event_type == "invoice.paid":
            # Payment successful - ensure subscription is active
            customer_id = data.get("customer")
            subscription_id = data.get("subscription")

            if subscription_id:
                org = db.query(Organization).filter(
                    Organization.stripe_customer_id == customer_id
                ).first()

                if org:
                    subscription = stripe_service.get_subscription(subscription_id)
                    price_id = subscription.get("items", {}).get("data", [{}])[0].get("price", {}).get("id", "")
                    tier = stripe_service.determine_tier_from_price(price_id)
                    org.subscription_tier = tier
                    db.commit()
                    print(f"[Stripe] Invoice paid for org {org.id}")

        elif event_type == "invoice.payment_failed":
            # Payment failed - could send notification
            customer_id = data.get("customer")
            print(f"[Stripe] Payment failed for customer {customer_id}")
            # TODO: Send email notification about failed payment

    except Exception as e:
        db.rollback()
        print(f"[Stripe] Error processing webhook: {e}")
        raise HTTPException(status_code=500, detail=f"Webhook processing failed: {str(e)}")
    finally:
        db.close()

    return {"status": "received", "event_type": event_type}


def _get_account_id() -> str:
    """Get AWS account ID from STS."""
    try:
        sts = boto3.client("sts")
        return sts.get_caller_identity()["Account"]
    except Exception:
        return "000000000000"
