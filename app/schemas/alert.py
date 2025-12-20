"""Alert API schemas."""
from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.models.alert import AlertType, AlertPeriod


# Request models

class AlertCreate(BaseModel):
    """Schema for creating an alert."""
    name: str = Field(..., min_length=1, max_length=255, description="Alert name")
    alert_type: AlertType = Field(default=AlertType.COST_THRESHOLD, description="Type of alert")
    threshold_amount: Decimal = Field(..., gt=0, description="Threshold amount in USD")
    period: AlertPeriod = Field(default=AlertPeriod.DAILY, description="Period to check")
    enabled: bool = Field(default=True, description="Whether alert is enabled")
    notify_email: bool = Field(default=True, description="Send email notifications")
    notify_slack: bool = Field(default=False, description="Send Slack notifications")
    slack_webhook_url: Optional[str] = Field(None, max_length=512, description="Slack webhook URL")

    @field_validator("slack_webhook_url")
    @classmethod
    def validate_slack_webhook(cls, v: Optional[str], info) -> Optional[str]:
        """Validate Slack webhook URL format."""
        if v and not v.startswith("https://hooks.slack.com/"):
            raise ValueError("Invalid Slack webhook URL format")
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "name": "Daily Cost Alert",
                "alert_type": "cost_threshold",
                "threshold_amount": 100.00,
                "period": "daily",
                "enabled": True,
                "notify_email": True,
                "notify_slack": False,
                "slack_webhook_url": None
            }
        }


class AlertUpdate(BaseModel):
    """Schema for updating an alert."""
    name: Optional[str] = Field(None, min_length=1, max_length=255, description="Alert name")
    alert_type: Optional[AlertType] = Field(None, description="Type of alert")
    threshold_amount: Optional[Decimal] = Field(None, gt=0, description="Threshold amount in USD")
    period: Optional[AlertPeriod] = Field(None, description="Period to check")
    enabled: Optional[bool] = Field(None, description="Whether alert is enabled")
    notify_email: Optional[bool] = Field(None, description="Send email notifications")
    notify_slack: Optional[bool] = Field(None, description="Send Slack notifications")
    slack_webhook_url: Optional[str] = Field(None, max_length=512, description="Slack webhook URL")

    @field_validator("slack_webhook_url")
    @classmethod
    def validate_slack_webhook(cls, v: Optional[str], info) -> Optional[str]:
        """Validate Slack webhook URL format."""
        if v and not v.startswith("https://hooks.slack.com/"):
            raise ValueError("Invalid Slack webhook URL format")
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "threshold_amount": 150.00,
                "enabled": False
            }
        }


# Response models

class AlertResponse(BaseModel):
    """Schema for alert response."""
    id: UUID
    org_id: UUID
    name: str
    alert_type: AlertType
    threshold_amount: Decimal
    period: AlertPeriod
    enabled: bool
    notify_email: bool
    notify_slack: bool
    slack_webhook_url: Optional[str]
    created_at: datetime
    updated_at: datetime
    last_triggered_at: Optional[datetime]

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "org_id": "123e4567-e89b-12d3-a456-426614174000",
                "name": "Daily Cost Alert",
                "alert_type": "cost_threshold",
                "threshold_amount": 100.00,
                "period": "daily",
                "enabled": True,
                "notify_email": True,
                "notify_slack": False,
                "slack_webhook_url": None,
                "created_at": "2024-12-19T12:00:00Z",
                "updated_at": "2024-12-19T12:00:00Z",
                "last_triggered_at": None
            }
        }


class AlertTriggerResponse(BaseModel):
    """Schema for alert trigger response."""
    id: UUID
    alert_id: UUID
    triggered_at: datetime
    actual_amount: Decimal
    threshold_amount: Decimal
    notified: bool

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": "660e8400-e29b-41d4-a716-446655440000",
                "alert_id": "550e8400-e29b-41d4-a716-446655440000",
                "triggered_at": "2024-12-19T18:00:00Z",
                "actual_amount": 125.50,
                "threshold_amount": 100.00,
                "notified": True
            }
        }


class AlertListResponse(BaseModel):
    """Schema for list of alerts."""
    alerts: list[AlertResponse]
    total: int

    class Config:
        json_schema_extra = {
            "example": {
                "alerts": [],
                "total": 0
            }
        }


class AlertTriggerListResponse(BaseModel):
    """Schema for list of alert triggers."""
    triggers: list[AlertTriggerResponse]
    total: int

    class Config:
        json_schema_extra = {
            "example": {
                "triggers": [],
                "total": 0
            }
        }
