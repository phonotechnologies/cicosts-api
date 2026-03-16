"""
Plan limits service.

Enforces subscription tier limits for organizations.
Reference: pricing page - Free (3 repos, 30 days), Pro (unlimited, 1 year), Team (unlimited, 1 year)
"""
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.organization import Organization
from app.models.workflow_run import WorkflowRun


@dataclass
class PlanLimits:
    """Limits for a subscription tier."""
    max_repos: Optional[int]  # None = unlimited
    max_history_days: int
    max_team_members: Optional[int]  # None = unlimited (for Team tier)


@dataclass
class UsageStatus:
    """Current usage vs limits."""
    tier: str
    repos_used: int
    repos_limit: Optional[int]
    repos_at_limit: bool
    history_days_limit: int
    team_members_used: int
    team_members_limit: Optional[int]


# Tier definitions
# CICosts is open source and free for everyone.
# Enterprise tier is for organizations that need SLA, dedicated support, or custom integrations.
PLAN_LIMITS = {
    "free": PlanLimits(
        max_repos=None,       # Unlimited
        max_history_days=365,
        max_team_members=None,  # Unlimited
    ),
    "pro": PlanLimits(
        max_repos=None,
        max_history_days=365,
        max_team_members=None,
    ),
    "team": PlanLimits(
        max_repos=None,
        max_history_days=365,
        max_team_members=None,
    ),
    "enterprise": PlanLimits(
        max_repos=None,
        max_history_days=365,
        max_team_members=None,
    ),
}


def get_plan_limits(tier: str) -> PlanLimits:
    """Get limits for a subscription tier."""
    return PLAN_LIMITS.get(tier.lower(), PLAN_LIMITS["free"])


def get_org_tier(db: Session, org_id: UUID) -> str:
    """Get the subscription tier for an organization."""
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        return "free"
    return org.subscription_tier or "free"


def get_tracked_repo_count(db: Session, org_id: UUID) -> int:
    """Get the number of unique repositories being tracked for an org."""
    count = db.query(func.count(func.distinct(WorkflowRun.repo_name))).filter(
        WorkflowRun.org_id == org_id
    ).scalar()
    return count or 0


def get_tracked_repos(db: Session, org_id: UUID) -> list[str]:
    """Get list of tracked repository names for an org."""
    repos = db.query(func.distinct(WorkflowRun.repo_name)).filter(
        WorkflowRun.org_id == org_id
    ).all()
    return [r[0] for r in repos]


def get_usage_status(db: Session, org_id: UUID) -> UsageStatus:
    """Get current usage status for an organization."""
    tier = get_org_tier(db, org_id)
    limits = get_plan_limits(tier)
    repos_used = get_tracked_repo_count(db, org_id)

    # Check team members (count org memberships)
    from app.models.org_membership import OrgMembership
    team_members = db.query(func.count(OrgMembership.user_id)).filter(
        OrgMembership.org_id == org_id
    ).scalar() or 0

    repos_at_limit = limits.max_repos is not None and repos_used >= limits.max_repos

    return UsageStatus(
        tier=tier,
        repos_used=repos_used,
        repos_limit=limits.max_repos,
        repos_at_limit=repos_at_limit,
        history_days_limit=limits.max_history_days,
        team_members_used=team_members,
        team_members_limit=limits.max_team_members,
    )


def can_track_repo(db: Session, org_id: UUID, repo_name: str) -> bool:
    """
    Check if an organization can track a repository.

    Returns True if:
    - The repo is already being tracked (existing repos always allowed)
    - The org hasn't hit their repo limit
    - The org has unlimited repos (Pro/Team tier)
    """
    tier = get_org_tier(db, org_id)
    limits = get_plan_limits(tier)

    # Unlimited repos
    if limits.max_repos is None:
        return True

    # Check if repo is already tracked
    existing = db.query(WorkflowRun).filter(
        WorkflowRun.org_id == org_id,
        WorkflowRun.repo_name == repo_name
    ).first()

    if existing:
        return True  # Already tracking this repo

    # Check if at limit for new repos
    current_count = get_tracked_repo_count(db, org_id)
    return current_count < limits.max_repos


def get_effective_history_days(db: Session, org_id: UUID, requested_days: int) -> int:
    """
    Get the effective number of history days based on plan limits.

    Caps the requested days to the plan's maximum.
    """
    tier = get_org_tier(db, org_id)
    limits = get_plan_limits(tier)
    return min(requested_days, limits.max_history_days)


def get_history_start_date(db: Session, org_id: UUID) -> datetime:
    """
    Get the earliest date that data should be shown for this org.

    Based on their plan's history limit.
    """
    tier = get_org_tier(db, org_id)
    limits = get_plan_limits(tier)
    return datetime.utcnow() - timedelta(days=limits.max_history_days)
