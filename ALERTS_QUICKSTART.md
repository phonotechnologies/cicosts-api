# Alerts System - Quick Start Guide

## Setup

### 1. Run the Database Migration

```bash
cd ~/mateen/saas/cicosts/cicosts-api

# Check current migration status
alembic current

# Apply the alerts migration
alembic upgrade head

# Verify tables were created
# (Connect to your database and check for 'alerts' and 'alert_triggers' tables)
```

### 2. Verify API is Running

The alerts endpoints should now be available at `/api/v1/alerts`.

Check the API documentation:
```bash
# Start the API server
uvicorn app.main:app --reload

# Visit http://localhost:8000/docs
# Look for the "Alerts" section
```

## Usage Examples

### Create Your First Alert

```bash
# Set your auth token and org ID
export AUTH_TOKEN="your-jwt-token"
export ORG_ID="your-organization-uuid"

# Create a daily cost alert
curl -X POST "http://localhost:8000/api/v1/alerts?org_id=${ORG_ID}" \
  -H "Authorization: Bearer ${AUTH_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Daily CI Cost Limit",
    "alert_type": "cost_threshold",
    "threshold_amount": 100.00,
    "period": "daily",
    "enabled": true,
    "notify_email": true,
    "notify_slack": false
  }'
```

### List All Alerts

```bash
curl -X GET "http://localhost:8000/api/v1/alerts?org_id=${ORG_ID}" \
  -H "Authorization: Bearer ${AUTH_TOKEN}"
```

### Check an Alert Manually

```bash
# Get the alert ID from the list above
export ALERT_ID="alert-uuid"

# Manually trigger a check
curl -X POST "http://localhost:8000/api/v1/alerts/${ALERT_ID}/check" \
  -H "Authorization: Bearer ${AUTH_TOKEN}"
```

This will return:
```json
{
  "alert_id": "uuid",
  "current_cost": 45.67,
  "threshold": 100.00,
  "threshold_exceeded": false,
  "triggered": false,
  "trigger_id": null
}
```

### View Trigger History

```bash
curl -X GET "http://localhost:8000/api/v1/alerts/${ALERT_ID}/triggers?limit=10" \
  -H "Authorization: Bearer ${AUTH_TOKEN}"
```

### Update an Alert

```bash
# Increase the threshold
curl -X PUT "http://localhost:8000/api/v1/alerts/${ALERT_ID}" \
  -H "Authorization: Bearer ${AUTH_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "threshold_amount": 150.00
  }'

# Disable an alert
curl -X PUT "http://localhost:8000/api/v1/alerts/${ALERT_ID}" \
  -H "Authorization: Bearer ${AUTH_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "enabled": false
  }'
```

### Delete an Alert

```bash
curl -X DELETE "http://localhost:8000/api/v1/alerts/${ALERT_ID}" \
  -H "Authorization: Bearer ${AUTH_TOKEN}"
```

## Common Alert Configurations

### 1. Daily Budget Alert
Prevents daily spending from exceeding $100:
```json
{
  "name": "Daily Budget Limit",
  "alert_type": "budget_limit",
  "threshold_amount": 100.00,
  "period": "daily",
  "enabled": true,
  "notify_email": true
}
```

### 2. Weekly Cost Threshold
Alerts when weekly costs exceed $500:
```json
{
  "name": "Weekly Cost Alert",
  "alert_type": "cost_threshold",
  "threshold_amount": 500.00,
  "period": "weekly",
  "enabled": true,
  "notify_email": true
}
```

### 3. Monthly Budget with Slack
Monthly budget alert with Slack notification:
```json
{
  "name": "Monthly Budget",
  "alert_type": "budget_limit",
  "threshold_amount": 2000.00,
  "period": "monthly",
  "enabled": true,
  "notify_email": true,
  "notify_slack": true,
  "slack_webhook_url": "https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
}
```

## Testing Your Alerts

### 1. Create Test Workflow Runs

To test alerts, you need workflow runs with costs. You can either:
- Wait for real GitHub Actions to run
- Manually insert test data into the database
- Trigger GitHub Actions workflows

### 2. Manually Check Alert

Use the `/check` endpoint to test without waiting:

```bash
curl -X POST "http://localhost:8000/api/v1/alerts/${ALERT_ID}/check" \
  -H "Authorization: Bearer ${AUTH_TOKEN}"
```

This will:
1. Calculate current period costs
2. Compare against threshold
3. Create a trigger if exceeded
4. Return the result immediately

### 3. View Trigger History

After an alert has triggered, view the history:

```bash
curl -X GET "http://localhost:8000/api/v1/alerts/${ALERT_ID}/triggers" \
  -H "Authorization: Bearer ${AUTH_TOKEN}"
```

## Automation

### Schedule Regular Alert Checks

To automatically check alerts, you can:

1. **AWS Lambda + EventBridge** (recommended for production):
```python
# lambda_function.py
import os
import requests

def lambda_handler(event, context):
    """Check all alerts for all organizations."""
    api_url = os.environ['API_URL']

    # Get all organizations (you'll need to implement this endpoint)
    orgs = requests.get(f"{api_url}/api/v1/organizations").json()

    for org in orgs:
        # Check all alerts for this org
        alerts = requests.get(
            f"{api_url}/api/v1/alerts",
            params={"org_id": org["id"]}
        ).json()

        for alert in alerts["alerts"]:
            if alert["enabled"]:
                # Check the alert
                requests.post(
                    f"{api_url}/api/v1/alerts/{alert['id']}/check"
                )

    return {"statusCode": 200}
```

2. **Cron Job** (for self-hosted):
```bash
# Add to crontab: Check alerts every hour
0 * * * * /usr/local/bin/check-alerts.sh
```

```bash
#!/bin/bash
# check-alerts.sh
ALERT_IDS=("alert-id-1" "alert-id-2" "alert-id-3")

for ALERT_ID in "${ALERT_IDS[@]}"; do
    curl -X POST "http://localhost:8000/api/v1/alerts/${ALERT_ID}/check" \
      -H "Authorization: Bearer ${AUTH_TOKEN}"
done
```

## Troubleshooting

### Alert Not Triggering

1. **Check if alert is enabled**:
   ```bash
   curl -X GET "http://localhost:8000/api/v1/alerts/${ALERT_ID}" \
     -H "Authorization: Bearer ${AUTH_TOKEN}"
   ```

2. **Verify current costs**:
   ```bash
   curl -X POST "http://localhost:8000/api/v1/alerts/${ALERT_ID}/check" \
     -H "Authorization: Bearer ${AUTH_TOKEN}"
   ```

3. **Check for existing triggers in the same period**:
   Alerts won't trigger twice in the same period to prevent spam.

### Notifications Not Sending

Currently, notifications are not implemented. The system creates trigger records but doesn't send emails/Slack messages. To implement:

1. Add a notification service
2. Integrate with email provider (Resend, SendGrid, etc.)
3. Update `AlertService.trigger_alert()` to send notifications
4. Mark `trigger.notified = True` after success

### Database Connection Issues

If migrations fail:
```bash
# Check database connection
psql $DATABASE_URL -c "SELECT 1"

# Verify Alembic config
cat alembic.ini

# Check alembic/env.py imports
```

## Next Steps

1. **Implement Notification Service**: Add email/Slack delivery
2. **Add Scheduled Checks**: Set up Lambda or cron job
3. **Create Alert Templates**: Pre-configure common alerts
4. **Add Dashboard UI**: Show alerts and triggers in the frontend
5. **Implement Anomaly Detection**: Use ML for unusual cost patterns

## Support

- API Docs: http://localhost:8000/docs
- Full Documentation: `ALERTS_SYSTEM.md`
- Tests: `tests/test_alerts.py`
