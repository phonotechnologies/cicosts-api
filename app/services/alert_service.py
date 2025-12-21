"""Alert service for checking and triggering alerts."""
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from sqlalchemy import func, desc
from sqlalchemy.orm import Session

from app.models.alert import Alert, AlertPeriod
from app.models.alert_trigger import AlertTrigger
from app.models.workflow_run import WorkflowRun
from app.models.user import User
from app.models.organization import Organization
from app.models.org_membership import OrgMembership

logger = logging.getLogger(__name__)


class AlertService:
    """Service for managing cost alerts."""

    def __init__(self, db: Session):
        """Initialize alert service with database session."""
        self.db = db

    def get_period_cost(
        self,
        org_id: UUID,
        period: AlertPeriod,
        end_time: Optional[datetime] = None
    ) -> Decimal:
        """
        Get total cost for the specified period.

        Args:
            org_id: Organization ID
            period: Alert period (daily, weekly, monthly)
            end_time: End of period (defaults to now)

        Returns:
            Total cost in USD for the period
        """
        if end_time is None:
            end_time = datetime.utcnow()

        start_time = self._get_period_start(period, end_time)

        result = self.db.query(
            func.sum(WorkflowRun.cost_usd)
        ).filter(
            WorkflowRun.org_id == org_id,
            WorkflowRun.completed_at >= start_time,
            WorkflowRun.completed_at <= end_time,
        ).scalar()

        return result or Decimal("0.00")

    def check_alerts(self, org_id: UUID) -> List[AlertTrigger]:
        """
        Check all enabled alerts for an organization.

        Args:
            org_id: Organization ID

        Returns:
            List of alert triggers created (if any)
        """
        # Get all enabled alerts for the organization
        alerts = self.db.query(Alert).filter(
            Alert.org_id == org_id,
            Alert.enabled == True
        ).all()

        triggered_alerts = []

        for alert in alerts:
            trigger = self._check_single_alert(alert)
            if trigger:
                triggered_alerts.append(trigger)

        return triggered_alerts

    def _check_single_alert(self, alert: Alert) -> Optional[AlertTrigger]:
        """
        Check a single alert and trigger if threshold exceeded.

        Args:
            alert: Alert to check

        Returns:
            AlertTrigger if alert was triggered, None otherwise
        """
        # Get current period cost
        actual_cost = self.get_period_cost(alert.org_id, alert.period)

        # Check if threshold exceeded
        if actual_cost <= alert.threshold_amount:
            return None

        # Check if we already triggered this alert in the current period
        # to avoid duplicate notifications
        period_start = self._get_period_start(alert.period, datetime.utcnow())
        existing_trigger = self.db.query(AlertTrigger).filter(
            AlertTrigger.alert_id == alert.id,
            AlertTrigger.triggered_at >= period_start
        ).first()

        if existing_trigger:
            # Already triggered in this period
            return None

        # Trigger the alert
        return self.trigger_alert(alert, actual_cost)

    def _get_alert_recipients(self, org_id: UUID) -> List[str]:
        """
        Get email addresses for alert notifications.

        Returns emails of org owners/admins who have alert_emails_enabled.
        Falls back to organization billing_email if no eligible users.

        Args:
            org_id: Organization ID

        Returns:
            List of email addresses to notify
        """
        # Query org members who are owners/admins and have alerts enabled
        eligible_members = self.db.query(User).join(
            OrgMembership, OrgMembership.user_id == User.id
        ).filter(
            OrgMembership.org_id == org_id,
            OrgMembership.role.in_(["owner", "admin"]),
            User.alert_emails_enabled == True,
            User.is_deleted == False
        ).all()

        recipients = []
        for user in eligible_members:
            # Use notification_email if set, otherwise primary email
            email = user.notification_email or user.email
            if email and email not in recipients:
                recipients.append(email)

        # Fallback to org billing_email if no eligible members
        if not recipients:
            org = self.db.query(Organization).filter(
                Organization.id == org_id
            ).first()
            if org and org.billing_email:
                recipients.append(org.billing_email)

        return recipients

    def trigger_alert(
        self,
        alert: Alert,
        actual_amount: Decimal
    ) -> AlertTrigger:
        """
        Create an alert trigger record and send notifications.

        Args:
            alert: Alert that was triggered
            actual_amount: Actual cost amount that triggered the alert

        Returns:
            Created AlertTrigger record
        """
        now = datetime.utcnow()

        # Create trigger record
        trigger = AlertTrigger(
            alert_id=alert.id,
            triggered_at=now,
            actual_amount=actual_amount,
            threshold_amount=alert.threshold_amount,
            notified=False  # Will be set to True after notification is sent
        )

        self.db.add(trigger)

        # Update alert's last triggered timestamp
        alert.last_triggered_at = now

        self.db.commit()
        self.db.refresh(trigger)

        # Send notifications
        notification_sent = False

        # Send email notification if enabled
        if alert.notify_email:
            try:
                from app.services.email_service import get_email_service

                recipients = self._get_alert_recipients(alert.org_id)
                if recipients:
                    email_service = get_email_service()

                    # Prepare alert data for email template
                    alert_data = {
                        "name": alert.name,
                        "threshold": float(alert.threshold_amount),
                        "period": alert.period.value,
                        "recipients": recipients,
                    }

                    # Prepare trigger data for email template
                    trigger_data = {
                        "current_cost": float(actual_amount),
                        "triggered_at": now.isoformat(),
                    }

                    result = email_service.send_alert_notification(alert_data, trigger_data)

                    if result.get("success"):
                        notification_sent = True
                        logger.info(
                            f"Alert notification sent: {alert.name} to {len(recipients)} recipients"
                        )
                    else:
                        logger.error(
                            f"Failed to send alert notification: {result.get('error')}"
                        )
                else:
                    logger.warning(
                        f"No recipients found for alert {alert.name} (org_id: {alert.org_id})"
                    )

            except Exception as e:
                logger.error(f"Error sending alert email: {e}", exc_info=True)

        # Send Slack notification if enabled
        if alert.notify_slack and alert.slack_webhook_url:
            try:
                self._send_slack_notification(alert, actual_amount)
                notification_sent = True
            except Exception as e:
                logger.error(f"Error sending Slack notification: {e}", exc_info=True)

        # Update trigger as notified if any notification was sent
        if notification_sent:
            trigger.notified = True
            self.db.commit()

        return trigger

    def _send_slack_notification(
        self,
        alert: Alert,
        actual_amount: Decimal
    ) -> None:
        """
        Send Slack webhook notification.

        Args:
            alert: Alert that was triggered
            actual_amount: Actual cost amount
        """
        import httpx

        if not alert.slack_webhook_url:
            return

        payload = {
            "text": f":warning: *Cost Alert Triggered*",
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": f":warning: {alert.name}",
                        "emoji": True
                    }
                },
                {
                    "type": "section",
                    "fields": [
                        {
                            "type": "mrkdwn",
                            "text": f"*Current Cost:*\n${actual_amount:.2f}"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Threshold:*\n${alert.threshold_amount:.2f}"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Period:*\n{alert.period.value.capitalize()}"
                        }
                    ]
                },
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {
                                "type": "plain_text",
                                "text": "View Dashboard",
                                "emoji": True
                            },
                            "url": "https://app.cicosts.dev/dashboard"
                        }
                    ]
                }
            ]
        }

        with httpx.Client() as client:
            response = client.post(
                alert.slack_webhook_url,
                json=payload,
                timeout=10.0
            )
            response.raise_for_status()
            logger.info(f"Slack notification sent for alert: {alert.name}")

    def get_alert_triggers(
        self,
        alert_id: UUID,
        limit: int = 50,
        offset: int = 0
    ) -> List[AlertTrigger]:
        """
        Get trigger history for an alert.

        Args:
            alert_id: Alert ID
            limit: Maximum number of triggers to return
            offset: Number of triggers to skip

        Returns:
            List of alert triggers, most recent first
        """
        return self.db.query(AlertTrigger).filter(
            AlertTrigger.alert_id == alert_id
        ).order_by(
            desc(AlertTrigger.triggered_at)
        ).limit(limit).offset(offset).all()

    def _get_period_start(
        self,
        period: AlertPeriod,
        end_time: datetime
    ) -> datetime:
        """
        Get start datetime for a period.

        Args:
            period: Alert period
            end_time: End of period

        Returns:
            Start datetime for the period
        """
        if period == AlertPeriod.DAILY:
            # Start of current day
            return end_time.replace(hour=0, minute=0, second=0, microsecond=0)

        elif period == AlertPeriod.WEEKLY:
            # Start of current week (Monday)
            start_of_day = end_time.replace(hour=0, minute=0, second=0, microsecond=0)
            days_since_monday = start_of_day.weekday()
            return start_of_day - timedelta(days=days_since_monday)

        elif period == AlertPeriod.MONTHLY:
            # Start of current month
            return end_time.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        else:
            raise ValueError(f"Unknown period: {period}")

    def mark_trigger_notified(self, trigger_id: UUID, notified: bool = True) -> None:
        """
        Mark an alert trigger as notified.

        Args:
            trigger_id: Alert trigger ID
            notified: Whether notification was successful
        """
        trigger = self.db.query(AlertTrigger).filter(
            AlertTrigger.id == trigger_id
        ).first()

        if trigger:
            trigger.notified = notified
            self.db.commit()
