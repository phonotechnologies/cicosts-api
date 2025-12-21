"""
Plan limits API endpoints.

Provides usage status and limit information for organizations.
"""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, CurrentUser
from app.services.plan_limits import (
    get_usage_status,
    get_plan_limits,
    get_tracked_repos,
    UsageStatus,
)

router = APIRouter()


class PlanLimitsResponse(BaseModel):
    """Plan limits for the organization's tier."""
    max_repos: Optional[int]  # None = unlimited
    max_history_days: int
    max_team_members: Optional[int]  # None = unlimited


class UsageStatusResponse(BaseModel):
    """Current usage status for an organization."""
    tier: str
    repos_used: int
    repos_limit: Optional[int]
    repos_at_limit: bool
    history_days_limit: int
    team_members_used: int
    team_members_limit: Optional[int]
    tracked_repos: list[str]


class UpgradeSuggestion(BaseModel):
    """Upgrade suggestion when at or near limits."""
    should_upgrade: bool
    reason: Optional[str]
    suggested_tier: Optional[str]


@router.get("/usage", response_model=UsageStatusResponse)
async def get_org_usage(
    org_id: UUID = Query(..., description="Organization ID"),
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get current usage status for an organization.

    Returns the organization's plan tier, current usage, and limits.
    Use this to show upgrade prompts or limit warnings in the UI.
    """
    status = get_usage_status(db, org_id)
    tracked_repos = get_tracked_repos(db, org_id)

    return UsageStatusResponse(
        tier=status.tier,
        repos_used=status.repos_used,
        repos_limit=status.repos_limit,
        repos_at_limit=status.repos_at_limit,
        history_days_limit=status.history_days_limit,
        team_members_used=status.team_members_used,
        team_members_limit=status.team_members_limit,
        tracked_repos=tracked_repos,
    )


@router.get("/plan", response_model=PlanLimitsResponse)
async def get_plan_info(
    org_id: UUID = Query(..., description="Organization ID"),
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get plan limits for an organization.

    Returns the limits for the organization's current subscription tier.
    """
    from app.services.plan_limits import get_org_tier

    tier = get_org_tier(db, org_id)
    limits = get_plan_limits(tier)

    return PlanLimitsResponse(
        max_repos=limits.max_repos,
        max_history_days=limits.max_history_days,
        max_team_members=limits.max_team_members,
    )


@router.get("/upgrade-suggestion", response_model=UpgradeSuggestion)
async def get_upgrade_suggestion(
    org_id: UUID = Query(..., description="Organization ID"),
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get upgrade suggestion based on current usage.

    Returns whether the organization should consider upgrading and why.
    """
    status = get_usage_status(db, org_id)

    # Determine if upgrade is needed
    if status.tier == "team":
        # Already on highest tier
        return UpgradeSuggestion(
            should_upgrade=False,
            reason=None,
            suggested_tier=None,
        )

    if status.tier == "free":
        # Check if at repo limit
        if status.repos_at_limit:
            return UpgradeSuggestion(
                should_upgrade=True,
                reason="You've reached the 3 repository limit on the Free plan. Upgrade to track unlimited repos.",
                suggested_tier="pro",
            )

        # Check if nearing repo limit
        if status.repos_limit and status.repos_used >= status.repos_limit - 1:
            return UpgradeSuggestion(
                should_upgrade=True,
                reason=f"You're using {status.repos_used} of {status.repos_limit} repositories. Upgrade before you hit the limit.",
                suggested_tier="pro",
            )

        # Check if history limit is constraining
        if status.history_days_limit <= 30:
            return UpgradeSuggestion(
                should_upgrade=True,
                reason="Free plan only shows 30 days of history. Upgrade for 1 year of data retention.",
                suggested_tier="pro",
            )

    if status.tier == "pro":
        # Check if team members limit is constraining
        if status.team_members_limit and status.team_members_used >= status.team_members_limit:
            return UpgradeSuggestion(
                should_upgrade=True,
                reason="Pro plan is limited to 1 user. Upgrade to Team for up to 5 team members.",
                suggested_tier="team",
            )

    return UpgradeSuggestion(
        should_upgrade=False,
        reason=None,
        suggested_tier=None,
    )
