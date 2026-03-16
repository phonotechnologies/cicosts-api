# CICosts API

FastAPI backend for the CICosts platform.

## URLs

| Environment | URL |
|-------------|-----|
| Production | https://api.cicosts.dev |
| Development | https://dev-api.cicosts.dev |
| API Docs | https://dev-api.cicosts.dev/docs |

## Tech Stack

- **Framework**: FastAPI (Python 3.11)
- **Database**: PostgreSQL (Supabase)
- **ORM**: SQLAlchemy
- **Auth**: GitHub OAuth + JWT
- **Hosting**: AWS Lambda + API Gateway
- **Queue**: SQS for webhook processing

## Project Structure

```
app/
├── main.py              # FastAPI app entry
├── config.py            # Settings from env/secrets
├── database.py          # SQLAlchemy session
├── dependencies.py      # Auth dependency
├── routers/
│   ├── auth.py          # GitHub OAuth
│   ├── dashboard.py     # Dashboard endpoints
│   ├── alerts.py        # Alerts CRUD
│   ├── settings.py      # User settings
│   ├── billing.py       # Stripe integration
│   ├── limits.py        # Plan limits
│   └── webhooks.py      # GitHub/Stripe webhooks
├── models/              # SQLAlchemy models
├── schemas/             # Pydantic schemas
├── services/
│   ├── cost_calculator.py    # Runner pricing
│   ├── alert_service.py      # Alert logic
│   ├── plan_limits.py        # Tier enforcement
│   ├── redis_rate_limiter.py # Rate limiting
│   └── logging_service.py    # Structured logging
├── middleware/
│   └── rate_limit.py    # Rate limit middleware
└── workers/
    └── handler.py       # SQS webhook processor

tests/                   # pytest tests (235 passing)
load-tests/              # k6 load testing suite
alembic/                 # Database migrations
```

## API Endpoints

### Auth
- `GET /api/v1/auth/login` - Start OAuth flow
- `GET /api/v1/auth/callback` - OAuth callback
- `GET /api/v1/auth/me` - Current user
- `POST /api/v1/auth/refresh` - Refresh token

### Dashboard
- `GET /api/v1/dashboard/summary` - Cost summary
- `GET /api/v1/dashboard/trends` - Cost trends
- `GET /api/v1/dashboard/top-workflows` - Top workflows by cost
- `GET /api/v1/dashboard/workflows` - Workflow list

### Alerts
- `GET/POST /api/v1/alerts` - List/create alerts
- `GET/PUT/DELETE /api/v1/alerts/{id}` - CRUD operations

## Running Locally

```bash
# Install dependencies
pip install -r requirements.txt

# Run server
uvicorn app.main:app --reload

# Run tests
pytest tests/ -v

# Run load tests
cd load-tests && k6 run smoke-test.js
```

## Environment Variables

Set in AWS Secrets Manager (`cicosts-{env}/api-secrets`):
- `jwt_secret` - JWT signing key
- `stripe_secret_key` - Stripe API key
- `resend_api_key` - Email API key

## Deployment

Push to main triggers CI/CD pipeline:
1. Tests (pytest)
2. Lint (ruff, mypy)
3. Build Lambda package
4. Deploy to dev
5. Deploy to prod (requires approval)

## Cost Calculator

Runner pricing per minute:
| Runner | Price |
|--------|-------|
| ubuntu-latest | $0.008 |
| ubuntu-arm | $0.005 |
| windows-latest | $0.016 |
| macos-latest | $0.08 |

## Plan Limits

| Tier | Repos | History | Team |
|------|-------|---------|------|
| Free | 3 | 30 days | 1 |
| Pro | Unlimited | 365 days | 1 |
| Team | Unlimited | 365 days | 5 |
