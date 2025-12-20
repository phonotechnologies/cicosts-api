"""Settings API endpoints."""
from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, CurrentUser
from app.models.user import User
from app.models.organization import Organization
from app.models.org_membership import OrgMembership

router = APIRouter()


# Response models

class UserSettingsResponse(BaseModel):
    """User settings response."""
    id: str
    email: str
    github_login: Optional[str]
    github_id: Optional[int]
    github_avatar_url: Optional[str]
    created_at: datetime
    notification_email: Optional[str]
    weekly_digest_enabled: bool
    alert_emails_enabled: bool

    class Config:
        from_attributes = True


class NotificationSettingsResponse(BaseModel):
    """Notification settings response."""
    notification_email: Optional[str]
    weekly_digest_enabled: bool
    alert_emails_enabled: bool


class UserOrganizationResponse(BaseModel):
    """User organization response."""
    id: str
    github_org_slug: str
    github_org_name: Optional[str]
    role: str
    joined_at: datetime


# Request models

class NotificationSettingsUpdate(BaseModel):
    """Update notification settings."""
    notification_email: Optional[str] = None
    weekly_digest_enabled: Optional[bool] = None
    alert_emails_enabled: Optional[bool] = None


# Endpoints

@router.get("/user", response_model=UserSettingsResponse)
async def get_user_settings(
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get current user settings.
    """
    user = db.query(User).filter(
        User.id == current_user.user_id,
        User.is_deleted == False,
    ).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    return UserSettingsResponse(
        id=str(user.id),
        email=user.email,
        github_login=user.github_login,
        github_id=user.github_id,
        github_avatar_url=user.github_avatar_url,
        created_at=user.created_at,
        notification_email=user.notification_email,
        weekly_digest_enabled=user.weekly_digest_enabled,
        alert_emails_enabled=user.alert_emails_enabled,
    )


@router.patch("/user", response_model=UserSettingsResponse)
async def update_user_settings(
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Update current user settings.

    Note: Most user fields are read-only (synced from GitHub).
    Use /notifications endpoint for notification preferences.
    """
    user = db.query(User).filter(
        User.id == current_user.user_id,
        User.is_deleted == False,
    ).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    return UserSettingsResponse(
        id=str(user.id),
        email=user.email,
        github_login=user.github_login,
        github_id=user.github_id,
        github_avatar_url=user.github_avatar_url,
        created_at=user.created_at,
        notification_email=user.notification_email,
        weekly_digest_enabled=user.weekly_digest_enabled,
        alert_emails_enabled=user.alert_emails_enabled,
    )


@router.get("/notifications", response_model=NotificationSettingsResponse)
async def get_notification_settings(
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get notification settings for current user.
    """
    user = db.query(User).filter(
        User.id == current_user.user_id,
        User.is_deleted == False,
    ).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    return NotificationSettingsResponse(
        notification_email=user.notification_email or user.email,
        weekly_digest_enabled=user.weekly_digest_enabled,
        alert_emails_enabled=user.alert_emails_enabled,
    )


@router.patch("/notifications", response_model=NotificationSettingsResponse)
async def update_notification_settings(
    settings: NotificationSettingsUpdate,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Update notification settings for current user.
    """
    user = db.query(User).filter(
        User.id == current_user.user_id,
        User.is_deleted == False,
    ).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Update fields that were provided
    if settings.notification_email is not None:
        user.notification_email = settings.notification_email
    if settings.weekly_digest_enabled is not None:
        user.weekly_digest_enabled = settings.weekly_digest_enabled
    if settings.alert_emails_enabled is not None:
        user.alert_emails_enabled = settings.alert_emails_enabled

    db.commit()
    db.refresh(user)

    return NotificationSettingsResponse(
        notification_email=user.notification_email or user.email,
        weekly_digest_enabled=user.weekly_digest_enabled,
        alert_emails_enabled=user.alert_emails_enabled,
    )


@router.get("/organizations", response_model=list[UserOrganizationResponse])
async def get_user_organizations(
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get all organizations the current user is a member of.
    """
    memberships = db.query(OrgMembership, Organization).join(
        Organization, OrgMembership.org_id == Organization.id
    ).filter(
        OrgMembership.user_id == current_user.user_id,
    ).all()

    return [
        UserOrganizationResponse(
            id=str(org.id),
            github_org_slug=org.github_org_slug,
            github_org_name=org.github_org_name,
            role=membership.role,
            joined_at=membership.created_at,
        )
        for membership, org in memberships
    ]


@router.post("/organizations/{org_id}/leave")
async def leave_organization(
    org_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Leave an organization.

    Owners cannot leave their organization - they must transfer ownership first.
    """
    # Check if membership exists
    membership = db.query(OrgMembership).filter(
        OrgMembership.user_id == current_user.user_id,
        OrgMembership.org_id == org_id,
    ).first()

    if not membership:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="You are not a member of this organization"
        )

    # Owners cannot leave
    if membership.role == "owner":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Owners cannot leave their organization. Transfer ownership first."
        )

    # Delete membership
    db.delete(membership)
    db.commit()

    return {"success": True}


@router.delete("/account")
async def delete_account(
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Delete current user's account.

    This is a soft delete that:
    - Marks the user as deleted
    - Archives the email address
    - Removes all organization memberships

    Data is retained for 30 days before permanent deletion.
    """
    user = db.query(User).filter(
        User.id == current_user.user_id,
        User.is_deleted == False,
    ).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Check if user is owner of any organizations
    owner_memberships = db.query(OrgMembership).filter(
        OrgMembership.user_id == current_user.user_id,
        OrgMembership.role == "owner",
    ).all()

    if owner_memberships:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete account while you own organizations. Transfer ownership first."
        )

    # Remove all memberships
    db.query(OrgMembership).filter(
        OrgMembership.user_id == current_user.user_id,
    ).delete()

    # Soft delete user
    user.is_deleted = True
    user.deleted_at = datetime.utcnow()
    user.deleted_email_archived = user.email
    user.email = f"deleted-{user.id}@deleted.cicosts.dev"

    db.commit()

    return {"success": True}
