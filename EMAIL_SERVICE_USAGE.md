# Email Service Usage Guide

The CICosts email service provides AWS SES integration for sending transactional emails.

## Configuration

Add the following environment variables to your `.env` file:

```env
SES_FROM_EMAIL=noreply@cicosts.dev
SES_REPLY_TO=support@cicosts.dev
SES_REGION=us-east-1
SES_QUEUE_URL=https://sqs.us-east-1.amazonaws.com/123456789/cicosts-emails
```

## Using the Email Service

### Basic Email Sending

```python
from app.services.email_service import get_email_service

email_service = get_email_service()

result = email_service.send_email(
    to='user@example.com',
    subject='Test Email',
    html_body='<h1>Hello</h1><p>This is a test email.</p>',
    text_body='Hello\n\nThis is a test email.'
)

if result['success']:
    print(f"Email sent! Message ID: {result['message_id']}")
else:
    print(f"Failed to send: {result['error']}")
```

### Send Alert Notification

```python
from app.services.email_service import get_email_service

email_service = get_email_service()

alert = {
    'name': 'Daily Cost Alert',
    'threshold': 100.0,
    'period': 'daily',
    'recipients': ['admin@example.com', 'finance@example.com']
}

trigger = {
    'current_cost': 150.50,
    'triggered_at': '2024-01-01T00:00:00Z',
    'breakdown': [
        {'name': 'CI Pipeline', 'cost': 100.0},
        {'name': 'Deploy Workflow', 'cost': 50.5}
    ]
}

result = email_service.send_alert_notification(alert, trigger)
print(f"Sent to {result['sent']} of {result['total']} recipients")
```

### Send Weekly Digest

```python
from app.services.email_service import get_email_service

email_service = get_email_service()

user = {
    'email': 'user@example.com',
    'github_login': 'johndoe'
}

org = {
    'github_org_name': 'MyCompany'
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
```

### Send Welcome Email

```python
from app.services.email_service import get_email_service

email_service = get_email_service()

user = {
    'email': 'newuser@example.com',
    'github_login': 'newuser'
}

result = email_service.send_welcome_email(user)
```

## Async Email Sending (Queue)

For better performance and reliability, queue emails for async processing:

```python
from app.workers.email_handler import queue_email

# Queue an alert notification
result = queue_email('alert_notification', {
    'alert': alert_data,
    'trigger': trigger_data
})

# Queue a weekly digest
result = queue_email('weekly_digest', {
    'user': user_data,
    'org': org_data,
    'cost_summary': cost_summary_data
})

# Queue a welcome email
result = queue_email('welcome', {
    'user': user_data
})
```

The email worker (`email_handler.py`) processes queued emails from SQS with automatic retry logic for failed sends.

## Lambda Worker Integration

The email handler is designed to work with AWS Lambda and SQS:

```python
# In your Lambda handler (workers.py)
from app.workers.email_handler import handle_email_queue

def lambda_handler(event, context):
    """Process SQS email queue."""
    if 'Records' in event:
        return handle_email_queue(event['Records'])
```

## Error Handling

The email service handles various SES errors:

- **Throttling**: Logged with warning, email will be retried via SQS
- **MessageRejected**: Email address not verified or bounced
- **EmailAddressNotVerified**: Domain/email not verified in SES

All errors are logged with full context for debugging.

## Email Templates

Templates are located in `app/templates/`:

- `alert_notification.py` - Cost alert triggered
- `weekly_digest.py` - Weekly cost summary
- `welcome.py` - Welcome email after signup

Templates use inline CSS for maximum email client compatibility.

## Testing

Run tests with:

```bash
pytest tests/test_email_service.py -v
```

## AWS SES Setup

1. Verify your sending domain in AWS SES:
   ```bash
   aws ses verify-domain-identity --domain cicosts.dev
   ```

2. Add DNS records (DKIM, SPF) for better deliverability

3. Move out of SES sandbox (production only):
   - Request production access in AWS Console
   - Provide use case details

4. Create SQS queue for async email processing:
   ```bash
   aws sqs create-queue --queue-name cicosts-emails
   ```

5. Set up Lambda trigger for SQS queue

## Best Practices

1. **Always queue emails in production** - Don't block API requests
2. **Monitor bounce rates** - Set up SNS notifications for bounces
3. **Respect unsubscribe requests** - Track opt-outs in database
4. **Use SES configuration sets** - For tracking opens/clicks
5. **Test templates** - Send to multiple email clients before deploying

## Monitoring

Monitor email delivery with CloudWatch metrics:

- SES Send metrics (success/bounce/complaint rates)
- SQS queue depth
- Lambda execution errors

Set up alarms for:
- High bounce rate (> 5%)
- High complaint rate (> 0.1%)
- SQS message age (> 15 minutes)
