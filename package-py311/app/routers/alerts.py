"""Alerts API endpoints."""
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, CurrentUser
from app.models.alert import Alert
from app.models.alert_trigger import AlertTrigger
from app.models.organization import Organization
from app.models.org_membership import OrgMembership
from app.services.alert_service import AlertService
from app.schemas.alert import (
    AlertCreate,
    AlertUpdate,
    AlertResponse,
    AlertListResponse,
    AlertTriggerResponse,
    AlertTriggerListResponse,
)

router = APIRouter()


def verify_org_access(org_id: UUID, current_user: CurrentUser, db: Session) -> Organization:
    """
    Verify that the current user has access to the organization.

    Args:
        org_id: Organization ID
        current_user: Current authenticated user
        db: Database session

    Returns:
        Organization if user has access

    Raises:
        HTTPException: If organization not found or user doesn't have access
    """
    # Check if organization exists
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found"
        )

    # Check if user is a member of the organization
    membership = db.query(OrgMembership).filter(
        OrgMembership.org_id == org_id,
        OrgMembership.user_id == current_user.user_id
    ).first()

    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this organization"
        )

    return org


@router.get("", response_model=AlertListResponse)
async def list_alerts(
    org_id: UUID = Query(..., description="Organization ID"),
    enabled: bool = Query(None, description="Filter by enabled status"),
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    List all alerts for an organization.

    Args:
        org_id: Organization ID to list alerts for
        enabled: Optional filter by enabled status
        current_user: Current authenticated user
        db: Database session

    Returns:
        List of alerts with total count
    """
    # Verify user has access to the organization
    verify_org_access(org_id, current_user, db)

    # Build query
    query = db.query(Alert).filter(Alert.org_id == org_id)

    # Apply filters
    if enabled is not None:
        query = query.filter(Alert.enabled == enabled)

    # Get alerts ordered by creation date (newest first)
    alerts = query.order_by(Alert.created_at.desc()).all()

    return AlertListResponse(
        alerts=alerts,
        total=len(alerts)
    )


@router.post("", response_model=AlertResponse, status_code=status.HTTP_201_CREATED)
async def create_alert(
    org_id: UUID = Query(..., description="Organization ID"),
    alert_data: AlertCreate = ...,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Create a new alert for an organization.

    Args:
        org_id: Organization ID
        alert_data: Alert creation data
        current_user: Current authenticated user
        db: Database session

    Returns:
        Created alert
    """
    # Verify user has access to the organization
    verify_org_access(org_id, current_user, db)

    # Validate Slack configuration
    if alert_data.notify_slack and not alert_data.slack_webhook_url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Slack webhook URL is required when Slack notifications are enabled"
        )

    # Create alert
    alert = Alert(
        org_id=org_id,
        name=alert_data.name,
        alert_type=alert_data.alert_type,
        threshold_amount=alert_data.threshold_amount,
        period=alert_data.period,
        enabled=alert_data.enabled,
        notify_email=alert_data.notify_email,
        notify_slack=alert_data.notify_slack,
        slack_webhook_url=alert_data.slack_webhook_url,
    )

    db.add(alert)
    db.commit()
    db.refresh(alert)

    return alert


@router.get("/{alert_id}", response_model=AlertResponse)
async def get_alert(
    alert_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get alert details by ID.

    Args:
        alert_id: Alert ID
        current_user: Current authenticated user
        db: Database session

    Returns:
        Alert details
    """
    # Get alert
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert not found"
        )

    # Verify user has access to the organization
    verify_org_access(alert.org_id, current_user, db)

    return alert


@router.put("/{alert_id}", response_model=AlertResponse)
async def update_alert(
    alert_id: UUID,
    alert_data: AlertUpdate,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Update an alert.

    Args:
        alert_id: Alert ID
        alert_data: Alert update data
        current_user: Current authenticated user
        db: Database session

    Returns:
        Updated alert
    """
    # Get alert
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert not found"
        )

    # Verify user has access to the organization
    verify_org_access(alert.org_id, current_user, db)

    # Update fields that were provided
    update_data = alert_data.model_dump(exclude_unset=True)

    # Validate Slack configuration if being updated
    if "notify_slack" in update_data or "slack_webhook_url" in update_data:
        notify_slack = update_data.get("notify_slack", alert.notify_slack)
        slack_webhook_url = update_data.get("slack_webhook_url", alert.slack_webhook_url)

        if notify_slack and not slack_webhook_url:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Slack webhook URL is required when Slack notifications are enabled"
            )

    for field, value in update_data.items():
        setattr(alert, field, value)

    db.commit()
    db.refresh(alert)

    return alert


@router.delete("/{alert_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_alert(
    alert_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Delete an alert.

    Args:
        alert_id: Alert ID
        current_user: Current authenticated user
        db: Database session

    Returns:
        None (204 No Content)
    """
    # Get alert
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert not found"
        )

    # Verify user has access to the organization
    verify_org_access(alert.org_id, current_user, db)

    # Delete alert (cascade will delete triggers)
    db.delete(alert)
    db.commit()

    return None


@router.get("/{alert_id}/triggers", response_model=AlertTriggerListResponse)
async def get_alert_triggers(
    alert_id: UUID,
    limit: int = Query(50, ge=1, le=100, description="Number of triggers to return"),
    offset: int = Query(0, ge=0, description="Number of triggers to skip"),
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get trigger history for an alert.

    Args:
        alert_id: Alert ID
        limit: Maximum number of triggers to return
        offset: Number of triggers to skip (for pagination)
        current_user: Current authenticated user
        db: Database session

    Returns:
        List of alert triggers with total count
    """
    # Get alert
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert not found"
        )

    # Verify user has access to the organization
    verify_org_access(alert.org_id, current_user, db)

    # Get triggers using service
    alert_service = AlertService(db)
    triggers = alert_service.get_alert_triggers(alert_id, limit, offset)

    # Get total count
    total = db.query(AlertTrigger).filter(
        AlertTrigger.alert_id == alert_id
    ).count()

    return AlertTriggerListResponse(
        triggers=triggers,
        total=total
    )


@router.post("/{alert_id}/check", response_model=dict)
async def check_alert(
    alert_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Manually check an alert and trigger if threshold exceeded.

    This is useful for testing alerts or running manual checks.

    Args:
        alert_id: Alert ID
        current_user: Current authenticated user
        db: Database session

    Returns:
        Dictionary with check results
    """
    # Get alert
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert not found"
        )

    # Verify user has access to the organization
    verify_org_access(alert.org_id, current_user, db)

    # Check alert using service
    alert_service = AlertService(db)
    actual_cost = alert_service.get_period_cost(alert.org_id, alert.period)

    # Check if threshold exceeded
    threshold_exceeded = actual_cost > alert.threshold_amount

    triggered = None
    if threshold_exceeded and alert.enabled:
        # Check and potentially trigger
        triggered = alert_service._check_single_alert(alert)

    return {
        "alert_id": str(alert_id),
        "current_cost": float(actual_cost),
        "threshold": float(alert.threshold_amount),
        "threshold_exceeded": threshold_exceeded,
        "triggered": triggered is not None,
        "trigger_id": str(triggered.id) if triggered else None
    }
