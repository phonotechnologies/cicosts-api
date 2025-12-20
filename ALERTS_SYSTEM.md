# CICosts Alerts System

## Overview

The alerts system enables organizations to set up automated notifications when their CI/CD costs exceed defined thresholds. This helps teams stay on budget and catch cost anomalies early.

## Features

- **Multiple Alert Types**: Cost threshold, budget limit, and anomaly detection
- **Flexible Periods**: Daily, weekly, and monthly monitoring
- **Multi-channel Notifications**: Email and Slack (extensible)
- **Trigger History**: Complete audit trail of all alert activations
- **Manual Testing**: Ability to test alerts on-demand

## Architecture

### Models

#### Alert (`app/models/alert.py`)
- Stores alert configuration for an organization
- Fields:
  - `name`: Human-readable alert name
  - `alert_type`: Type of alert (cost_threshold, budget_limit, anomaly)
  - `threshold_amount`: Dollar amount that triggers the alert
  - `period`: Time period to monitor (daily, weekly, monthly)
  - `enabled`: Whether the alert is active
  - `notify_email`: Send email notifications
  - `notify_slack`: Send Slack notifications
  - `slack_webhook_url`: Slack webhook for notifications
  - `last_triggered_at`: Timestamp of last trigger

#### AlertTrigger (`app/models/alert_trigger.py`)
- Records each time an alert is triggered
- Fields:
  - `triggered_at`: When the alert fired
  - `actual_amount`: Actual cost that exceeded threshold
  - `threshold_amount`: Threshold at time of trigger
  - `notified`: Whether notifications were sent

### Service Layer

#### AlertService (`app/services/alert_service.py`)

Key methods:

- `get_period_cost(org_id, period, end_time)`: Calculate total cost for a period
- `check_alerts(org_id)`: Check all enabled alerts for an organization
- `trigger_alert(alert, amount)`: Create trigger record and queue notification
- `get_alert_triggers(alert_id, limit, offset)`: Get trigger history

Period calculation:
- **Daily**: Current day (midnight to now)
- **Weekly**: Current week (Monday to now)
- **Monthly**: Current month (1st to now)

### API Endpoints

All endpoints are prefixed with `/api/v1/alerts` and require authentication.

#### List Alerts
```
GET /api/v1/alerts?org_id={uuid}&enabled={bool}
```

Returns all alerts for an organization, optionally filtered by enabled status.

#### Create Alert
```
POST /api/v1/alerts?org_id={uuid}
Content-Type: application/json

{
  "name": "Daily Cost Alert",
  "alert_type": "cost_threshold",
  "threshold_amount": 100.00,
  "period": "daily",
  "enabled": true,
  "notify_email": true,
  "notify_slack": false,
  "slack_webhook_url": null
}
```

#### Get Alert
```
GET /api/v1/alerts/{alert_id}
```

Returns details of a specific alert.

#### Update Alert
```
PUT /api/v1/alerts/{alert_id}
Content-Type: application/json

{
  "threshold_amount": 150.00,
  "enabled": false
}
```

Partial update - only include fields you want to change.

#### Delete Alert
```
DELETE /api/v1/alerts/{alert_id}
```

Deletes an alert and all its trigger history.

#### Get Trigger History
```
GET /api/v1/alerts/{alert_id}/triggers?limit=50&offset=0
```

Returns paginated list of alert triggers.

#### Manual Check
```
POST /api/v1/alerts/{alert_id}/check
```

Manually check an alert and trigger if threshold exceeded. Useful for testing.

Response:
```json
{
  "alert_id": "uuid",
  "current_cost": 125.50,
  "threshold": 100.00,
  "threshold_exceeded": true,
  "triggered": true,
  "trigger_id": "uuid"
}
```

## Database Schema

### alerts table
```sql
CREATE TABLE alerts (
    id UUID PRIMARY KEY,
    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    alert_type alert_type_enum NOT NULL,
    threshold_amount NUMERIC(10, 2) NOT NULL,
    period alert_period_enum NOT NULL,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    notify_email BOOLEAN NOT NULL DEFAULT TRUE,
    notify_slack BOOLEAN NOT NULL DEFAULT FALSE,
    slack_webhook_url VARCHAR(512),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    last_triggered_at TIMESTAMP
);

CREATE INDEX ix_alerts_org_id ON alerts(org_id);
```

### alert_triggers table
```sql
CREATE TABLE alert_triggers (
    id UUID PRIMARY KEY,
    alert_id UUID NOT NULL REFERENCES alerts(id) ON DELETE CASCADE,
    triggered_at TIMESTAMP NOT NULL DEFAULT NOW(),
    actual_amount NUMERIC(10, 2) NOT NULL,
    threshold_amount NUMERIC(10, 2) NOT NULL,
    notified BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE INDEX ix_alert_triggers_alert_id ON alert_triggers(alert_id);
CREATE INDEX ix_alert_triggers_triggered_at ON alert_triggers(triggered_at);
```

## Migration

To create the alerts tables in your database:

```bash
# Review the migration
alembic upgrade head --sql

# Apply the migration
alembic upgrade head
```

To rollback:
```bash
alembic downgrade -1
```

## Usage Examples

### Create a Daily Cost Alert

```python
import httpx

response = httpx.post(
    "https://api.cicosts.dev/api/v1/alerts",
    params={"org_id": "your-org-uuid"},
    headers={"Authorization": "Bearer your-token"},
    json={
        "name": "Daily CI Cost Alert",
        "alert_type": "cost_threshold",
        "threshold_amount": 100.00,
        "period": "daily",
        "enabled": True,
        "notify_email": True,
        "notify_slack": False
    }
)

alert = response.json()
print(f"Created alert: {alert['id']}")
```

### Check Alert Manually

```python
response = httpx.post(
    f"https://api.cicosts.dev/api/v1/alerts/{alert_id}/check",
    headers={"Authorization": "Bearer your-token"}
)

result = response.json()
if result["triggered"]:
    print(f"Alert triggered! Cost: ${result['current_cost']}")
else:
    print(f"Alert OK. Cost: ${result['current_cost']} / ${result['threshold']}")
```

### List All Triggers

```python
response = httpx.get(
    f"https://api.cicosts.dev/api/v1/alerts/{alert_id}/triggers",
    headers={"Authorization": "Bearer your-token"},
    params={"limit": 50, "offset": 0}
)

triggers = response.json()
print(f"Total triggers: {triggers['total']}")
for trigger in triggers["triggers"]:
    print(f"  {trigger['triggered_at']}: ${trigger['actual_amount']}")
```

## Security

- All endpoints require authentication via JWT token
- Users can only access alerts for organizations they are members of
- Organization membership is verified on every request
- Slack webhook URLs are validated to prevent SSRF attacks

## Future Enhancements

### Notification System
Currently, the alert system creates trigger records but doesn't send notifications. To implement:

1. Create a notification service (`app/services/notification_service.py`)
2. Integrate with email provider (e.g., Resend, SendGrid)
3. Implement Slack webhook delivery
4. Add retry logic for failed notifications
5. Update `trigger.notified` after successful delivery

### Anomaly Detection
The `anomaly` alert type is a placeholder for future ML-based cost anomaly detection:

1. Calculate baseline costs using historical data
2. Detect significant deviations (e.g., >2 standard deviations)
3. Consider time-of-day, day-of-week patterns
4. Trigger alerts on unusual spending patterns

### Advanced Features
- Budget alerts with forecasting (predict if monthly budget will be exceeded)
- Per-repository or per-workflow alerts
- Alert templates for common scenarios
- Alert groups for team notifications
- Snooze functionality
- Alert escalation (multiple notification channels based on severity)

## Testing

Run the test suite:

```bash
pytest tests/test_alerts.py -v
```

Current test coverage:
- AlertService period calculations
- Model creation and validation
- Enum types and values

To add integration tests, set up a test database and test:
- Alert creation and updates
- Trigger generation
- Period cost calculation with real data
- Notification delivery

## Performance Considerations

- Alerts are checked on-demand (not automatically scheduled yet)
- Add a scheduled job (e.g., AWS Lambda + EventBridge) to check alerts periodically
- Use database indexes for efficient queries (already created)
- Cache period costs for frequently checked alerts
- Consider rate limiting on manual check endpoint

## Support

For issues or questions:
- Check API documentation at `/docs` (development only)
- Review source code in `app/routers/alerts.py`
- Submit issues to the CICosts repository
