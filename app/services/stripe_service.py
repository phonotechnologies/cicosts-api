"""
Stripe service for payment operations.

Handles checkout sessions, customer management, and subscription operations.
"""
import logging
import stripe
from typing import Optional
from uuid import UUID

from app.config import get_stripe_secrets, settings

logger = logging.getLogger(__name__)


def _get_stripe_client() -> None:
    """Initialize Stripe with API key."""
    secrets = get_stripe_secrets()
    api_key = secrets.get("secret_key", "")
    if api_key:
        logger.info(f"Stripe API key loaded: {api_key[:10]}...{api_key[-4:]}")
    else:
        logger.error("Stripe API key is empty!")
    stripe.api_key = api_key


def get_price_ids() -> dict:
    """Get all configured price IDs."""
    secrets = get_stripe_secrets()
    return {
        "pro_monthly": secrets.get("pro_monthly_price_id", ""),
        "pro_annual": secrets.get("pro_annual_price_id", ""),
        "team_monthly": secrets.get("team_monthly_price_id", ""),
        "team_annual": secrets.get("team_annual_price_id", ""),
    }


def create_checkout_session(
    price_id: str,
    org_id: UUID,
    user_id: UUID,
    customer_email: str,
    stripe_customer_id: Optional[str] = None,
) -> str:
    """
    Create a Stripe Checkout session for subscription.

    Returns the checkout URL.
    """
    _get_stripe_client()

    session_params = {
        "payment_method_types": ["card"],
        "line_items": [{"price": price_id, "quantity": 1}],
        "mode": "subscription",
        "success_url": f"{settings.FRONTEND_URL}/dashboard/settings?success=true",
        "cancel_url": f"{settings.FRONTEND_URL}/dashboard/settings?canceled=true",
        "metadata": {
            "org_id": str(org_id),
            "user_id": str(user_id),
        },
        "subscription_data": {
            "metadata": {
                "org_id": str(org_id),
            }
        },
        "allow_promotion_codes": True,
    }

    # Use existing customer or create by email
    if stripe_customer_id:
        session_params["customer"] = stripe_customer_id
    else:
        session_params["customer_email"] = customer_email

    logger.info(f"Creating Stripe checkout session with params: price_id={price_id}, org_id={org_id}")
    try:
        session = stripe.checkout.Session.create(**session_params)
        logger.info(f"Stripe checkout session created: {session.id}")
        return session.url
    except stripe.error.StripeError as e:
        logger.error(f"Stripe API error: {type(e).__name__}: {e.user_message if hasattr(e, 'user_message') else str(e)}")
        raise


def create_portal_session(stripe_customer_id: str) -> str:
    """
    Create a Stripe Customer Portal session.

    Returns the portal URL for managing subscription.
    """
    _get_stripe_client()

    session = stripe.billing_portal.Session.create(
        customer=stripe_customer_id,
        return_url=f"{settings.FRONTEND_URL}/dashboard/settings",
    )
    return session.url


def get_subscription(subscription_id: str) -> dict:
    """Get subscription details from Stripe."""
    _get_stripe_client()
    return stripe.Subscription.retrieve(subscription_id)


def get_customer(customer_id: str) -> dict:
    """Get customer details from Stripe."""
    _get_stripe_client()
    return stripe.Customer.retrieve(customer_id)


def cancel_subscription(subscription_id: str, at_period_end: bool = True) -> dict:
    """
    Cancel a subscription.

    By default, cancels at the end of the billing period.
    """
    _get_stripe_client()
    return stripe.Subscription.modify(
        subscription_id,
        cancel_at_period_end=at_period_end,
    )


def verify_webhook_signature(payload: bytes, signature: str) -> dict:
    """
    Verify Stripe webhook signature and return the event.

    Raises stripe.error.SignatureVerificationError if invalid.
    """
    _get_stripe_client()
    secrets = get_stripe_secrets()
    webhook_secret = secrets.get("webhook_secret", "")

    return stripe.Webhook.construct_event(payload, signature, webhook_secret)


def determine_tier_from_price(price_id: str) -> str:
    """
    Determine subscription tier from Stripe price ID.

    Returns: "pro", "team", or "free"
    """
    prices = get_price_ids()

    if price_id in [prices["pro_monthly"], prices["pro_annual"]]:
        return "pro"
    elif price_id in [prices["team_monthly"], prices["team_annual"]]:
        return "team"
    else:
        return "free"
