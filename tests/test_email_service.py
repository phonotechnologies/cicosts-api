"""
Tests for email service.

Run with: pytest tests/test_email_service.py -v
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from botocore.exceptions import ClientError

from app.services.email_service import EmailService, get_email_service


class TestEmailService:
    """Test EmailService class."""

    @pytest.fixture
    def email_service(self):
        """Create email service instance."""
        return EmailService()

    @pytest.fixture
    def mock_ses_client(self):
        """Mock SES client."""
        with patch('boto3.client') as mock_client:
            mock_ses = MagicMock()
            mock_client.return_value = mock_ses
            yield mock_ses

    def test_send_email_success(self, email_service, mock_ses_client):
        """Test successful email send."""
        # Mock successful response
        mock_ses_client.send_email.return_value = {
            'MessageId': 'test-message-id-123'
        }
        email_service.ses_client = mock_ses_client

        result = email_service.send_email(
            to='test@example.com',
            subject='Test Subject',
            html_body='<p>Test HTML</p>',
            text_body='Test Text'
        )

        assert result['success'] is True
        assert result['message_id'] == 'test-message-id-123'
        mock_ses_client.send_email.assert_called_once()

    def test_send_email_throttling_error(self, email_service, mock_ses_client):
        """Test email send with throttling error."""
        # Mock throttling error
        error_response = {
            'Error': {
                'Code': 'Throttling',
                'Message': 'Rate exceeded'
            }
        }
        mock_ses_client.send_email.side_effect = ClientError(
            error_response, 'SendEmail'
        )
        email_service.ses_client = mock_ses_client

        result = email_service.send_email(
            to='test@example.com',
            subject='Test',
            html_body='<p>Test</p>',
            text_body='Test'
        )

        assert result['success'] is False
        assert 'Throttling' in result['error']

    def test_send_email_rejected_error(self, email_service, mock_ses_client):
        """Test email send with message rejected error."""
        error_response = {
            'Error': {
                'Code': 'MessageRejected',
                'Message': 'Email address not verified'
            }
        }
        mock_ses_client.send_email.side_effect = ClientError(
            error_response, 'SendEmail'
        )
        email_service.ses_client = mock_ses_client

        result = email_service.send_email(
            to='invalid@example.com',
            subject='Test',
            html_body='<p>Test</p>',
            text_body='Test'
        )

        assert result['success'] is False
        assert 'MessageRejected' in result['error']

    def test_send_alert_notification(self, email_service, mock_ses_client):
        """Test alert notification email."""
        mock_ses_client.send_email.return_value = {
            'MessageId': 'alert-123'
        }
        email_service.ses_client = mock_ses_client

        alert = {
            'name': 'High Cost Alert',
            'threshold': 100.0,
            'period': 'daily',
            'recipients': ['admin@example.com']
        }

        trigger = {
            'current_cost': 150.50,
            'triggered_at': '2024-01-01T00:00:00Z',
            'breakdown': [
                {'name': 'Workflow 1', 'cost': 100.0},
                {'name': 'Workflow 2', 'cost': 50.5}
            ]
        }

        result = email_service.send_alert_notification(alert, trigger)

        assert result['success'] is True
        assert result['sent'] == 1
        assert result['total'] == 1
        mock_ses_client.send_email.assert_called_once()

    def test_send_alert_notification_multiple_recipients(
        self, email_service, mock_ses_client
    ):
        """Test alert notification to multiple recipients."""
        mock_ses_client.send_email.return_value = {
            'MessageId': 'alert-123'
        }
        email_service.ses_client = mock_ses_client

        alert = {
            'name': 'Test Alert',
            'threshold': 50.0,
            'period': 'weekly',
            'recipients': [
                'admin1@example.com',
                'admin2@example.com',
                'admin3@example.com'
            ]
        }

        trigger = {
            'current_cost': 75.0,
            'triggered_at': '2024-01-01T00:00:00Z'
        }

        result = email_service.send_alert_notification(alert, trigger)

        assert result['success'] is True
        assert result['sent'] == 3
        assert result['total'] == 3
        assert mock_ses_client.send_email.call_count == 3

    def test_send_weekly_digest(self, email_service, mock_ses_client):
        """Test weekly digest email."""
        mock_ses_client.send_email.return_value = {
            'MessageId': 'digest-123'
        }
        email_service.ses_client = mock_ses_client

        user = {
            'email': 'user@example.com',
            'github_login': 'testuser'
        }

        org = {
            'github_org_name': 'TestOrg'
        }

        cost_summary = {
            'total_cost': 250.75,
            'previous_week_cost': 200.00,
            'change_percent': 25.4,
            'top_workflows': [
                {'name': 'CI Pipeline', 'cost': 150.00, 'runs': 50},
                {'name': 'Deploy', 'cost': 100.75, 'runs': 20}
            ],
            'top_repos': [
                {'name': 'main-repo', 'cost': 200.00},
                {'name': 'frontend', 'cost': 50.75}
            ]
        }

        result = email_service.send_weekly_digest(user, org, cost_summary)

        assert result['success'] is True
        assert result['message_id'] == 'digest-123'
        mock_ses_client.send_email.assert_called_once()

    def test_send_welcome_email(self, email_service, mock_ses_client):
        """Test welcome email."""
        mock_ses_client.send_email.return_value = {
            'MessageId': 'welcome-123'
        }
        email_service.ses_client = mock_ses_client

        user = {
            'email': 'newuser@example.com',
            'github_login': 'newuser'
        }

        result = email_service.send_welcome_email(user)

        assert result['success'] is True
        assert result['message_id'] == 'welcome-123'
        mock_ses_client.send_email.assert_called_once()

    def test_get_email_service_singleton(self):
        """Test email service singleton pattern."""
        service1 = get_email_service()
        service2 = get_email_service()

        assert service1 is service2


class TestEmailTemplates:
    """Test email template rendering."""

    def test_alert_notification_template(self):
        """Test alert notification template renders correctly."""
        from app.templates.alert_notification import render_alert_email

        alert = {
            'name': 'Test Alert',
            'threshold': 100.0,
            'period': 'daily'
        }

        trigger = {
            'current_cost': 150.0,
            'breakdown': [
                {'name': 'Workflow 1', 'cost': 100.0},
                {'name': 'Workflow 2', 'cost': 50.0}
            ]
        }

        html_body, text_body = render_alert_email(alert, trigger)

        # Check HTML
        assert 'Test Alert' in html_body
        assert '$150.00' in html_body
        assert '$100.00' in html_body
        assert 'Workflow 1' in html_body

        # Check text
        assert 'Test Alert' in text_body
        assert '$150.00' in text_body
        assert 'Workflow 1' in text_body

    def test_weekly_digest_template(self):
        """Test weekly digest template renders correctly."""
        from app.templates.weekly_digest import render_weekly_digest

        user = {'github_login': 'testuser', 'email': 'test@example.com'}
        org = {'github_org_name': 'TestOrg'}
        cost_summary = {
            'total_cost': 200.0,
            'previous_week_cost': 150.0,
            'change_percent': 33.3,
            'top_workflows': [
                {'name': 'CI', 'cost': 100.0, 'runs': 10}
            ],
            'top_repos': [
                {'name': 'main-repo', 'cost': 100.0}
            ]
        }

        html_body, text_body = render_weekly_digest(user, org, cost_summary)

        # Check HTML
        assert 'testuser' in html_body
        assert 'TestOrg' in html_body
        assert '$200.00' in html_body
        assert '$150.00' in html_body

        # Check text
        assert 'testuser' in text_body
        assert 'TestOrg' in text_body
        assert '$200.00' in text_body

    def test_welcome_template(self):
        """Test welcome email template renders correctly."""
        from app.templates.welcome import render_welcome_email

        user = {'github_login': 'newuser', 'email': 'new@example.com'}

        html_body, text_body = render_welcome_email(user)

        # Check HTML
        assert 'newuser' in html_body
        assert 'Welcome to CICosts' in html_body
        assert 'Getting Started' in html_body

        # Check text
        assert 'newuser' in text_body
        assert 'WELCOME TO CICOSTS' in text_body
        assert 'GETTING STARTED' in text_body
