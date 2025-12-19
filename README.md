# CICosts API

FastAPI backend for CICosts - Track and optimize your CI/CD costs.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    AWS Lambda                           │
│  ┌─────────────────┐     ┌─────────────────────────┐   │
│  │   handler.py    │     │      workers.py         │   │
│  │   (API Lambda)  │     │   (Workers Lambda)      │   │
│  │                 │     │                         │   │
│  │  FastAPI +      │     │  EventBridge Jobs       │   │
│  │  Mangum         │     │  SQS Webhooks           │   │
│  └────────┬────────┘     └────────────┬────────────┘   │
│           │                           │                 │
│  ┌────────▼───────────────────────────▼────────────┐   │
│  │                  app/                            │   │
│  │  ├── main.py       (FastAPI app)                │   │
│  │  ├── config.py     (Settings)                   │   │
│  │  ├── database.py   (SQLAlchemy)                 │   │
│  │  ├── routers/      (API endpoints)              │   │
│  │  ├── models/       (Database models)            │   │
│  │  ├── services/     (Business logic)             │   │
│  │  └── workers/      (Background jobs)            │   │
│  └─────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
              ┌───────────────────────┐
              │   Supabase Postgres   │
              └───────────────────────┘
```

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

Visit http://localhost:8000/docs for Swagger UI.

## Project Structure

```
cicosts-api/
├── handler.py          # Lambda API entry point
├── workers.py          # Lambda workers entry point
├── app/
│   ├── main.py         # FastAPI application
│   ├── config.py       # Environment settings
│   ├── database.py     # Database connection
│   ├── routers/
│   │   ├── health.py   # Health check endpoints
│   │   ├── auth.py     # GitHub OAuth
│   │   └── webhooks.py # Webhook handlers
│   ├── models/
│   │   ├── organization.py
│   │   ├── user.py
│   │   ├── org_membership.py
│   │   ├── workflow_run.py
│   │   └── job.py
│   ├── services/
│   │   └── cost_calculator.py
│   └── workers/
│       └── handler.py  # Background job handlers
├── tests/
├── requirements.txt
└── .env.example
```

## API Endpoints

### Health
- `GET /health` - Health check with database status
- `GET /health/ready` - Readiness probe
- `GET /health/live` - Liveness probe

### Authentication
- `GET /api/v1/auth/login` - Initiate GitHub OAuth
- `GET /api/v1/auth/callback` - OAuth callback
- `GET /api/v1/auth/me` - Get current user
- `POST /api/v1/auth/logout` - Logout

### Webhooks
- `POST /api/v1/webhooks/github` - GitHub webhook receiver
- `POST /api/v1/webhooks/stripe` - Stripe webhook receiver

## Deployment

Deployed to AWS Lambda via GitHub Actions.

```bash
# Build Lambda package
pip install -r requirements.txt -t package/
cp -r app package/
cp handler.py workers.py package/
cd package && zip -r ../lambda-package.zip .
```

## References

- [spec-data-lifecycle.md](../docs/spec-data-lifecycle.md) - Data retention, trials, soft delete
- [spec-cost-calculation.md](../docs/spec-cost-calculation.md) - Cost calculation logic
- [spec-error-handling.md](../docs/spec-error-handling.md) - Error handling, webhooks
