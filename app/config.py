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

    # URLs
    FRONTEND_URL: str = "http://localhost:3000"
    API_URL: str = "http://localhost:8000"

    # Sentry
    SENTRY_DSN: str = ""

    # Redis (optional)
    UPSTASH_REDIS_URL: str = ""

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
