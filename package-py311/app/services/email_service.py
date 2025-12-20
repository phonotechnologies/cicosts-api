"""
Email service using AWS SES.

Handles sending transactional emails for alerts, digests, and welcome messages.
"""
import logging
from datetime import datetime
from decimal import Decimal
from typing import Dict, Any, Optional
from pathlib import Path
import boto3
from botocore.exceptions import ClientError

from app.config import settings

logger = logging.getLogger(__name__)


class EmailService:
    """AWS SES email service."""

    def __init__(self):
        """Initialize SES client."""
        self.ses_client = boto3.client('ses', region_name=settings.SES_REGION)
        self.from_email = settings.SES_FROM_EMAIL
        self.reply_to = settings.SES_REPLY_TO

    def send_email(
        self,
        to: str,
        subject: str,
        html_body: str,
        text_body: str
    ) -> Dict[str, Any]:
        """
        Send email via AWS SES.

        Args:
            to: Recipient email address
            subject: Email subject line
            html_body: HTML version of email body
            text_body: Plain text version of email body

        Returns:
            Dict with 'success' (bool), 'message_id' (str if success), 'error' (str if failed)
        """
        try:
            response = self.ses_client.send_email(
                Source=self.from_email,
                Destination={
                    'ToAddresses': [to]
                },
                Message={
                    'Subject': {
                        'Data': subject,
                        'Charset': 'UTF-8'
                    },
                    'Body': {
                        'Text': {
                            'Data': text_body,
                            'Charset': 'UTF-8'
                        },
                        'Html': {
                            'Data': html_body,
                            'Charset': 'UTF-8'
                        }
                    }
                },
                ReplyToAddresses=[self.reply_to]
            )

            message_id = response['MessageId']
            logger.info(f"Email sent successfully to {to}, MessageId: {message_id}")

            return {
                'success': True,
                'message_id': message_id
            }

        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_message = e.response['Error']['Message']

            logger.error(
                f"SES error sending to {to}: {error_code} - {error_message}",
                exc_info=True
            )

            # Handle specific SES errors
            if error_code == 'Throttling':
                logger.warning(f"SES throttling detected for {to}")
            elif error_code == 'MessageRejected':
                logger.error(f"SES rejected message to {to}: {error_message}")
            elif error_code in ['MailFromDomainNotVerified', 'EmailAddressNotVerified']:
                logger.error(f"SES domain/email not verified: {error_message}")

            return {
                'success': False,
                'error': f"{error_code}: {error_message}"
            }

        except Exception as e:
            logger.error(f"Unexpected error sending email to {to}: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e)
            }

    def send_alert_notification(
        self,
        alert: Dict[str, Any],
        trigger: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Send cost alert notification email.

        Args:
            alert: Alert configuration dict with:
                - name: Alert name
                - threshold: Cost threshold
                - period: Time period
                - recipients: List of email addresses
            trigger: Trigger event dict with:
                - current_cost: Current cost amount
                - triggered_at: Timestamp when triggered
                - breakdown: Optional cost breakdown

        Returns:
            Dict with send status
        """
        from app.templates.alert_notification import render_alert_email

        try:
            html_body, text_body = render_alert_email(alert, trigger)

            subject = f"CICosts Alert: {alert['name']} - ${trigger['current_cost']:.2f}"

            results = []
            for recipient in alert.get('recipients', []):
                result = self.send_email(recipient, subject, html_body, text_body)
                results.append({
                    'recipient': recipient,
                    **result
                })

            success_count = sum(1 for r in results if r['success'])
            logger.info(
                f"Alert notification sent: {success_count}/{len(results)} successful"
            )

            return {
                'success': success_count > 0,
                'sent': success_count,
                'total': len(results),
                'results': results
            }

        except Exception as e:
            logger.error(f"Error sending alert notification: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e)
            }

    def send_weekly_digest(
        self,
        user: Dict[str, Any],
        org: Dict[str, Any],
        cost_summary: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Send weekly cost summary digest email.

        Args:
            user: User dict with 'email', 'github_login'
            org: Organization dict with 'github_org_name'
            cost_summary: Cost summary dict with:
                - total_cost: Total cost for the week
                - previous_week_cost: Previous week's cost
                - change_percent: Percentage change
                - top_workflows: List of top workflows by cost
                - top_repos: List of top repos by cost

        Returns:
            Dict with send status
        """
        from app.templates.weekly_digest import render_weekly_digest

        try:
            html_body, text_body = render_weekly_digest(user, org, cost_summary)

            subject = f"CICosts Weekly Digest - {org['github_org_name']}"

            result = self.send_email(user['email'], subject, html_body, text_body)

            if result['success']:
                logger.info(f"Weekly digest sent to {user['email']}")

            return result

        except Exception as e:
            logger.error(f"Error sending weekly digest: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e)
            }

    def send_welcome_email(self, user: Dict[str, Any]) -> Dict[str, Any]:
        """
        Send welcome email to new user.

        Args:
            user: User dict with 'email', 'github_login'

        Returns:
            Dict with send status
        """
        from app.templates.welcome import render_welcome_email

        try:
            html_body, text_body = render_welcome_email(user)

            subject = "Welcome to CICosts - Start Tracking Your CI/CD Costs"

            result = self.send_email(user['email'], subject, html_body, text_body)

            if result['success']:
                logger.info(f"Welcome email sent to {user['email']}")

            return result

        except Exception as e:
            logger.error(f"Error sending welcome email: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e)
            }


# Singleton instance
_email_service: Optional[EmailService] = None


def get_email_service() -> EmailService:
    """Get email service singleton instance."""
    global _email_service
    if _email_service is None:
        _email_service = EmailService()
    return _email_service
