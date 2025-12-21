# CICosts API

[![API Tests](https://github.com/phonotechnologies/cicosts-api/actions/workflows/api-tests.yml/badge.svg)](https://github.com/phonotechnologies/cicosts-api/actions/workflows/api-tests.yml)
[![CI/CD](https://github.com/phonotechnologies/cicosts-api/actions/workflows/deploy.yml/badge.svg)](https://github.com/phonotechnologies/cicosts-api/actions/workflows/deploy.yml)

FastAPI backend for CICosts - Track and optimize your CI/CD costs.

**Live:** https://api.cicosts.dev

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      AWS Lambda                              │
│  ┌─────────────────┐           ┌─────────────────────────┐  │
│  │   handler.py    │           │      workers.py         │  │
│  │   (API Lambda)  │           │   (Workers Lambda)      │  │
│  │                 │           │                         │  │
│  │  FastAPI +      │           │  SQS → Process webhooks │  │
│  │  Mangum         │           │  Calculate costs        │  │
│  └────────┬────────┘           └────────────┬────────────┘  │
│           │                                 │                │
│           └────────────────┬────────────────┘                │
│                            ▼                                 │
│  ┌─────────────────────────────────────────────────────────┐│
│  │                       app/                               ││
│  │  routers/   → API endpoints (auth, dashboard, alerts)   ││
│  │  services/  → Business logic (cost calc, alerts, email) ││
│  │  workers/   → Webhook processing (workflow_run, job)    ││
│  │  models/    → SQLAlchemy models                         ││
│  └─────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
              ┌───────────────────────┐
              │   Supabase Postgres   │
              │  (Transaction Pooler) │
              └───────────────────────┘
```

## Tech Stack

- **Framework**: FastAPI (Python 3.11)
- **ORM**: SQLAlchemy 2.0
- **Database**: PostgreSQL (Supabase)
- **Auth**: GitHub OAuth + JWT
- **Email**: AWS SES
- **Queue**: AWS SQS
- **Testing**: pytest + SQLite in-memory
- **Deployment**: AWS Lambda via GitHub Actions

## Local Development

### Prerequisites

- Python 3.11+
- PostgreSQL (or Supabase connection)

### Setup

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows

# Install dependencies
pip install -r requirements.txt

# Copy environment file
cp .env.example .env
# Edit .env with your credentials

# Run development server
uvicorn app.main:app --reload --port 8000
```

### API Docs

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Project Structure

```
cicosts-api/
├── handler.py              # Lambda API entry point
├── workers.py              # Lambda workers entry point
├── app/
│   ├── main.py             # FastAPI application
│   ├── config.py           # Environment settings
│   ├── database.py         # Database connection
│   ├── dependencies.py     # Auth middleware
│   ├── routers/
│   │   ├── health.py       # Health check
│   │   ├── auth.py         # GitHub OAuth
│   │   ├── dashboard.py    # Dashboard data
│   │   ├── alerts.py       # Alerts CRUD
│   │   ├── settings.py     # User settings
│   │   └── webhooks.py     # GitHub/Stripe webhooks
│   ├── models/
│   │   ├── user.py
│   │   ├── organization.py
│   │   ├── org_membership.py
│   │   ├── workflow_run.py
│   │   ├── job.py
│   │   ├── alert.py
│   │   └── github_installation.py
│   ├── services/
│   │   ├── cost_calculator.py  # Runner pricing
│   │   ├── alert_service.py    # Alert logic
│   │   └── email_service.py    # AWS SES
│   └── workers/
│       └── handler.py          # SQS processing
├── alembic/                # Database migrations
├── tests/                  # Test suite (189 tests)
├── scripts/
│   ├── seed_data.py        # Sample data
│   └── simulate_webhooks.py
└── requirements.txt
```

## API Endpoints

### Health
```
GET /health           # Full health check
GET /health/ready     # Readiness probe
GET /health/live      # Liveness probe
```

### Authentication
```
GET  /api/v1/auth/login      # Initiate GitHub OAuth
GET  /api/v1/auth/callback   # OAuth callback
GET  /api/v1/auth/me         # Get current user
POST /api/v1/auth/logout     # Logout
POST /api/v1/auth/refresh    # Refresh token
```

### Dashboard
```
GET /api/v1/dashboard/summary        # Cost summary (today, week, month)
GET /api/v1/dashboard/trends         # Cost trends over time
GET /api/v1/dashboard/top-workflows  # Top workflows by cost
GET /api/v1/dashboard/recent-runs    # Recent workflow runs
GET /api/v1/dashboard/workflows      # Paginated workflow list
```

### Alerts
```
GET    /api/v1/alerts              # List alerts
POST   /api/v1/alerts              # Create alert
GET    /api/v1/alerts/{id}         # Get alert
PUT    /api/v1/alerts/{id}         # Update alert
DELETE /api/v1/alerts/{id}         # Delete alert
GET    /api/v1/alerts/{id}/triggers # Alert trigger history
POST   /api/v1/alerts/{id}/check   # Manually check alert
```

### Settings
```
GET   /api/v1/settings/user          # Get user profile
PATCH /api/v1/settings/user          # Update profile
GET   /api/v1/settings/notifications # Notification preferences
PATCH /api/v1/settings/notifications # Update notifications
GET   /api/v1/settings/organizations # List organizations
POST  /api/v1/settings/organizations/{id}/leave # Leave org
DELETE /api/v1/settings/account      # Delete account
```

### Webhooks
```
POST /api/v1/webhooks/github   # GitHub App webhooks
POST /api/v1/webhooks/stripe   # Stripe webhooks
```

## Testing

```bash
# Run all tests (189 tests)
python -m pytest tests/ -v

# With coverage
python -m pytest tests/ --cov=app --cov-report=html

# Specific test file
python -m pytest tests/test_cost_calculator.py -v

# With short tracebacks
python -m pytest tests/ -v --tb=short
```

### Test Coverage

| Test File | Tests | Description |
|-----------|-------|-------------|
| `test_cost_calculator.py` | 34 | Runner pricing logic |
| `test_email_service.py` | 11 | Email templates |
| `test_dashboard.py` | 26 | Dashboard endpoints |
| `test_alerts_router.py` | 34 | Alerts CRUD |
| `test_auth.py` | 18 | OAuth flow |
| `test_settings.py` | 17 | User settings |
| `test_webhooks.py` | 9 | Webhook handling |
| `test_worker_handler.py` | 12 | SQS processing |

**Total: 189/189 passing (100%)**

### Seed Data

For local development, populate the database:

```bash
python scripts/seed_data.py
```

## Cost Calculator

GitHub Actions runner pricing (per minute):

| Runner | Price/min |
|--------|-----------|
| ubuntu-latest (2-core) | $0.008 |
| ubuntu-latest-4-cores | $0.016 |
| ubuntu-latest-8-cores | $0.032 |
| ubuntu-latest-16-cores | $0.064 |
| windows-latest | $0.016 |
| macos-latest | $0.080 |
| macos-latest-large | $0.120 |
| ubuntu-latest-arm | $0.005 |

## Deployment

Auto-deploys to AWS Lambda via GitHub Actions on push to `main`.

```bash
# Manual deployment
pip install -r requirements.txt -t package/
cp -r app package/
cp handler.py workers.py package/
cd package && zip -r ../lambda-package.zip .

aws lambda update-function-code \
  --function-name cicosts-prod-api \
  --zip-file fileb://lambda-package.zip
```

## Environment Variables

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL connection string |
| `JWT_SECRET` | JWT signing secret |
| `GITHUB_CLIENT_ID` | OAuth client ID |
| `GITHUB_CLIENT_SECRET` | OAuth client secret |
| `GITHUB_APP_PRIVATE_KEY` | GitHub App private key |
| `GITHUB_WEBHOOK_SECRET` | Webhook signature secret |
| `AWS_SQS_QUEUE_URL` | SQS queue for webhooks |
| `STRIPE_SECRET_KEY` | Stripe API key |
| `RESEND_API_KEY` | Email service API key |

## Production Data

As of December 21, 2025:
- **41 workflow runs** tracked
- **64 jobs** with cost data
- **$0.22** total costs calculated
- **35.78 minutes** billable time

## References

- [spec-cost-calculation.md](../spec-cost-calculation.md) - Cost calculation logic
- [spec-data-lifecycle.md](../spec-data-lifecycle.md) - Data retention
- [spec-error-handling.md](../spec-error-handling.md) - Error handling
