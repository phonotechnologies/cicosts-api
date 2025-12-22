"""
CICosts API - Configuration

Load settings from environment variables.
"""
import json
import boto3
from functools import lru_cache
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings."""

    # Environment
    ENVIRONMENT: str = "development"

    # Database
    DATABASE_URL: str = ""
    SUPABASE_URL: str = ""
    SUPABASE_KEY: str = ""  # Anon key for REST API

    # GitHub App
    GITHUB_APP_ID: str = ""
    GITHUB_CLIENT_ID: str = ""

    # Secrets (loaded from AWS Secrets Manager)
    SECRETS_GITHUB_ARN: str = ""
    SECRETS_API_ARN: str = ""
    SECRETS_DATABASE_ARN: str = ""

    # URLs
    FRONTEND_URL: str = "http://localhost:3000"
    API_URL: str = "http://localhost:8000"

    # Sentry
    SENTRY_DSN: str = ""

    # Upstash Redis (for rate limiting)
    UPSTASH_REDIS_REST_URL: str = ""
    UPSTASH_REDIS_REST_TOKEN: str = ""

    # AWS SES Email
    SES_FROM_EMAIL: str = "noreply@cicosts.dev"
    SES_REPLY_TO: str = "support@cicosts.dev"
    SES_REGION: str = "us-east-1"
    SES_QUEUE_URL: str = ""  # SQS queue URL for async email sending

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()


# Secrets cache
_secrets_cache: dict = {}


def get_secret(secret_arn: str) -> dict:
    """
    Fetch secret from AWS Secrets Manager.

    Results are cached to avoid repeated API calls.
    """
    if secret_arn in _secrets_cache:
        return _secrets_cache[secret_arn]

    if not secret_arn:
        return {}

    try:
        client = boto3.client("secretsmanager")
        response = client.get_secret_value(SecretId=secret_arn)
        secret = json.loads(response["SecretString"])
        _secrets_cache[secret_arn] = secret
        return secret
    except Exception as e:
        print(f"Error fetching secret {secret_arn}: {e}")
        return {}


def get_github_secrets() -> dict:
    """Get GitHub App secrets."""
    return get_secret(settings.SECRETS_GITHUB_ARN)


def get_api_secrets() -> dict:
    """Get API secrets (Stripe, Resend, JWT, etc.)."""
    return get_secret(settings.SECRETS_API_ARN)


def get_database_secrets() -> dict:
    """Get database secrets (DATABASE_URL)."""
    return get_secret(settings.SECRETS_DATABASE_ARN)


def get_upstash_secrets() -> dict:
    """
    Get Upstash Redis secrets from API secrets or environment.

    Falls back to environment variables if not in Secrets Manager.
    """
    api_secrets = get_api_secrets()

    # Try secrets first, then fall back to env vars
    url = api_secrets.get("upstash_redis_rest_url") or settings.UPSTASH_REDIS_REST_URL
    token = api_secrets.get("upstash_redis_rest_token") or settings.UPSTASH_REDIS_REST_TOKEN

    return {
        "url": url,
        "token": token,
    }


def get_stripe_secrets() -> dict:
    """
    Get Stripe secrets from API secrets.

    Expected keys in api-secrets:
    - stripe_secret_key or STRIPE_SECRET_KEY
    - stripe_webhook_secret or STRIPE_WEBHOOK_SECRET
    - stripe_publishable_key or STRIPE_PUBLISHABLE_KEY
    - stripe_pro_monthly_price_id or STRIPE_PRO_MONTHLY_PRICE_ID
    - stripe_pro_annual_price_id or STRIPE_PRO_ANNUAL_PRICE_ID
    - stripe_team_monthly_price_id or STRIPE_TEAM_MONTHLY_PRICE_ID
    - stripe_team_annual_price_id or STRIPE_TEAM_ANNUAL_PRICE_ID
    """
    api_secrets = get_api_secrets()

    # Normalize keys (support both lowercase and uppercase)
    def get_key(name: str) -> str:
        return api_secrets.get(name) or api_secrets.get(name.upper()) or api_secrets.get(name.lower()) or ""

    return {
        "secret_key": get_key("stripe_secret_key"),
        "webhook_secret": get_key("stripe_webhook_secret"),
        "publishable_key": get_key("stripe_publishable_key"),
        "pro_monthly_price_id": get_key("stripe_pro_monthly_price_id"),
        "pro_annual_price_id": get_key("stripe_pro_annual_price_id"),
        "team_monthly_price_id": get_key("stripe_team_monthly_price_id"),
        "team_annual_price_id": get_key("stripe_team_annual_price_id"),
    }
