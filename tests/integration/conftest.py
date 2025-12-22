"""
Integration test configuration.

These tests run against the real dev API at dev-api.cicosts.dev.
Run with: pytest tests/integration -v --integration
"""

import os
import pytest
import httpx


def pytest_addoption(parser):
    """Add custom command line options."""
    parser.addoption(
        "--integration",
        action="store_true",
        default=False,
        help="Run integration tests against real API",
    )


def pytest_configure(config):
    """Configure custom markers."""
    config.addinivalue_line(
        "markers", "integration: mark test as integration test"
    )


def pytest_collection_modifyitems(config, items):
    """Skip integration tests unless --integration flag is provided."""
    if config.getoption("--integration"):
        return

    skip_integration = pytest.mark.skip(reason="Need --integration flag to run")
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip_integration)


# Environment configuration
API_BASE_URL = os.getenv("INTEGRATION_API_URL", "https://dev-api.cicosts.dev")
TEST_USER_TOKEN = os.getenv("INTEGRATION_TEST_TOKEN", "")  # Set via env for auth tests


@pytest.fixture(scope="session")
def api_url():
    """Base URL for the API."""
    return API_BASE_URL


@pytest.fixture(scope="session")
def http_client():
    """HTTP client for making requests."""
    with httpx.Client(base_url=API_BASE_URL, timeout=30.0) as client:
        yield client


@pytest.fixture(scope="session")
def auth_token():
    """Auth token for authenticated requests."""
    return TEST_USER_TOKEN


@pytest.fixture(scope="session")
def authenticated_client():
    """HTTP client with auth headers."""
    headers = {}
    if TEST_USER_TOKEN:
        headers["Authorization"] = f"Bearer {TEST_USER_TOKEN}"

    with httpx.Client(
        base_url=API_BASE_URL,
        timeout=30.0,
        headers=headers
    ) as client:
        yield client
