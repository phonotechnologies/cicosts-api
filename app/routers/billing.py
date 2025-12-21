"""
Billing endpoints.

Handles Stripe checkout, subscription management, and customer portal.
"""
import logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.dependencies import get_current_user, CurrentUser
from app.models.organization import Organization
from app.models.org_membership import OrgMembership
from app.services import stripe_service

logger = logging.getLogger(__name__)

router = APIRouter()


class CheckoutRequest(BaseModel):
    """Request body for creating checkout session."""
    price_id: str
    org_id: str


class CheckoutResponse(BaseModel):
    """Response with checkout URL."""
    checkout_url: str


class PortalRequest(BaseModel):
    """Request body for customer portal."""
    org_id: str


class PortalResponse(BaseModel):
    """Response with portal URL."""
    portal_url: str


class PricesResponse(BaseModel):
    """Available price IDs."""
    pro_monthly: str
    pro_annual: str
    team_monthly: str
    team_annual: str


class SubscriptionStatus(BaseModel):
    """Current subscription status for an org."""
    org_id: str
    tier: str
    stripe_customer_id: Optional[str]
    has_subscription: bool


@router.get("/prices", response_model=PricesResponse)
async def get_prices():
    """
    Get available Stripe price IDs.

    Frontend uses these to create checkout sessions.
    """
    prices = stripe_service.get_price_ids()
    return PricesResponse(
        pro_monthly=prices["pro_monthly"],
        pro_annual=prices["pro_annual"],
        team_monthly=prices["team_monthly"],
        team_annual=prices["team_annual"],
    )


@router.post("/checkout", response_model=CheckoutResponse)
async def create_checkout(
    request: CheckoutRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Create a Stripe Checkout session for subscription.

    Returns URL to redirect user to Stripe Checkout.
    """
    # Verify user has access to this org
    membership = db.query(OrgMembership).filter(
        OrgMembership.user_id == current_user.user_id,
        OrgMembership.org_id == request.org_id,
    ).first()

    if not membership:
        raise HTTPException(status_code=403, detail="Not a member of this organization")

    # Only admins/owners can manage billing
    if membership.role not in ["admin", "owner"]:
        raise HTTPException(status_code=403, detail="Only admins can manage billing")

    # Get organization
    org = db.query(Organization).filter(Organization.id == request.org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    # Validate price ID
    valid_prices = stripe_service.get_price_ids()
    valid_price_list = [v for v in valid_prices.values() if v]
    if request.price_id not in valid_price_list:
        raise HTTPException(status_code=400, detail="Invalid price ID")

    try:
        print(f"[BILLING] Creating checkout: org={org.id}, price={request.price_id}, email={current_user.email}")
        checkout_url = stripe_service.create_checkout_session(
            price_id=request.price_id,
            org_id=org.id,
            user_id=current_user.user_id,
            customer_email=current_user.email,
            stripe_customer_id=org.stripe_customer_id,
        )
        print(f"[BILLING] Checkout created: {checkout_url[:50]}...")
        return CheckoutResponse(checkout_url=checkout_url)
    except Exception as e:
        print(f"[BILLING ERROR] {type(e).__name__}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create checkout: {str(e)}")


@router.post("/portal", response_model=PortalResponse)
async def create_portal(
    request: PortalRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Create a Stripe Customer Portal session.

    Allows customers to manage their subscription, update payment methods, etc.
    """
    # Verify user has access to this org
    membership = db.query(OrgMembership).filter(
        OrgMembership.user_id == current_user.user_id,
        OrgMembership.org_id == request.org_id,
    ).first()

    if not membership:
        raise HTTPException(status_code=403, detail="Not a member of this organization")

    # Only admins/owners can access billing portal
    if membership.role not in ["admin", "owner"]:
        raise HTTPException(status_code=403, detail="Only admins can access billing")

    # Get organization
    org = db.query(Organization).filter(Organization.id == request.org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    if not org.stripe_customer_id:
        raise HTTPException(status_code=400, detail="No billing account found. Please subscribe first.")

    try:
        portal_url = stripe_service.create_portal_session(org.stripe_customer_id)
        return PortalResponse(portal_url=portal_url)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create portal: {str(e)}")


@router.get("/status/{org_id}", response_model=SubscriptionStatus)
async def get_subscription_status(
    org_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get current subscription status for an organization.
    """
    # Verify user has access to this org
    membership = db.query(OrgMembership).filter(
        OrgMembership.user_id == current_user.user_id,
        OrgMembership.org_id == org_id,
    ).first()

    if not membership:
        raise HTTPException(status_code=403, detail="Not a member of this organization")

    # Get organization
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    return SubscriptionStatus(
        org_id=str(org.id),
        tier=org.subscription_tier or "free",
        stripe_customer_id=org.stripe_customer_id,
        has_subscription=org.stripe_customer_id is not None,
    )
