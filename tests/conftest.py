"""
Test configuration and fixtures.

Provides:
- Test database (SQLite in-memory)
- FastAPI test client with dependency overrides
- Factory functions for creating test data
- JWT authentication mocking
"""
import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Generator, Optional
from uuid import uuid4, UUID
from unittest.mock import patch, MagicMock

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from jose import jwt

from app.main import app
from app.database import Base, get_db
from app.dependencies import get_current_user, CurrentUser
from app.models.user import User
from app.models.organization import Organization
from app.models.org_membership import OrgMembership
from app.models.workflow_run import WorkflowRun
from app.models.job import Job
from app.models.alert import Alert, AlertType, AlertPeriod
from app.models.alert_trigger import AlertTrigger
from app.models.github_installation import GitHubInstallation


# Test database setup - use StaticPool to maintain single connection for SQLite :memory:
SQLALCHEMY_TEST_DATABASE_URL = "sqlite:///:memory:"

test_engine = create_engine(
    SQLALCHEMY_TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,  # Ensures same connection is reused for all operations
)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


# JWT secret for tests
TEST_JWT_SECRET = "test-jwt-secret-for-testing"


def get_test_db() -> Generator[Session, None, None]:
    """Get test database session."""
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_test_token(
    user_id: UUID,
    email: str = "test@example.com",
    github_login: str = "testuser",
    github_id: int = 12345,
    expires_delta: timedelta = timedelta(hours=1),
) -> str:
    """Create a test JWT token."""
    expire = datetime.utcnow() + expires_delta
    payload = {
        "user_id": str(user_id),
        "email": email,
        "github_login": github_login,
        "github_id": github_id,
        "exp": expire,
    }
    return jwt.encode(payload, TEST_JWT_SECRET, algorithm="HS256")


@pytest.fixture(scope="function")
def db() -> Generator[Session, None, None]:
    """Create a fresh database for each test."""
    # Create all tables
    Base.metadata.create_all(bind=test_engine)

    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()
        # Drop all tables after test
        Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def client(db: Session) -> TestClient:
    """Create test client with database override."""
    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture
def mock_api_secrets():
    """Mock API secrets for testing."""
    mock_secrets = {
        "jwt_secret": TEST_JWT_SECRET,
        "github_client_id": "test-client-id",
        "github_client_secret": "test-client-secret",
        "github_app_id": "12345",
        "github_app_private_key": "test-private-key",
        "github_webhook_secret": "test-webhook-secret",
    }
    with patch("app.config.get_api_secrets", return_value=mock_secrets):
        with patch("app.dependencies.get_api_secrets", return_value=mock_secrets):
            yield mock_secrets


@pytest.fixture
def authenticated_client(db: Session, mock_api_secrets) -> tuple[TestClient, User]:
    """Create authenticated test client with a test user."""
    # Create test user
    user = UserFactory.create(db)
    db.commit()

    # Create token
    token = create_test_token(
        user_id=user.id,
        email=user.email,
        github_login=user.github_login,
        github_id=user.github_id,
    )

    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    test_client = TestClient(app)
    test_client.headers["Authorization"] = f"Bearer {token}"

    yield test_client, user

    app.dependency_overrides.clear()


@pytest.fixture
def authenticated_client_with_org(db: Session, mock_api_secrets) -> tuple[TestClient, User, Organization]:
    """Create authenticated test client with a user and organization."""
    # Create test user and org
    user = UserFactory.create(db)
    org = OrganizationFactory.create(db)
    membership = OrgMembershipFactory.create(db, user_id=user.id, org_id=org.id)
    db.commit()

    # Create token
    token = create_test_token(
        user_id=user.id,
        email=user.email,
        github_login=user.github_login,
        github_id=user.github_id,
    )

    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    test_client = TestClient(app)
    test_client.headers["Authorization"] = f"Bearer {token}"

    yield test_client, user, org

    app.dependency_overrides.clear()


# ============================================================================
# Factory Classes for Creating Test Data
# ============================================================================

class UserFactory:
    """Factory for creating test users."""

    _counter = 0

    @classmethod
    def create(
        cls,
        db: Session,
        id: Optional[UUID] = None,
        email: Optional[str] = None,
        github_id: Optional[int] = None,
        github_login: Optional[str] = None,
        github_avatar_url: Optional[str] = None,
        notification_email: Optional[str] = None,
        weekly_digest_enabled: bool = False,
        alert_emails_enabled: bool = True,
        is_deleted: bool = False,
    ) -> User:
        """Create a test user."""
        cls._counter += 1

        user = User(
            id=id or uuid4(),
            email=email or f"testuser{cls._counter}@example.com",
            github_id=github_id or (10000 + cls._counter),
            github_login=github_login or f"testuser{cls._counter}",
            github_avatar_url=github_avatar_url or f"https://avatars.githubusercontent.com/u/{10000 + cls._counter}",
            notification_email=notification_email,
            weekly_digest_enabled=weekly_digest_enabled,
            alert_emails_enabled=alert_emails_enabled,
            is_deleted=is_deleted,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(user)
        return user


class OrganizationFactory:
    """Factory for creating test organizations."""

    _counter = 0

    @classmethod
    def create(
        cls,
        db: Session,
        id: Optional[UUID] = None,
        github_org_id: Optional[int] = None,
        github_org_slug: Optional[str] = None,
        github_org_name: Optional[str] = None,
        billing_email: Optional[str] = None,
        subscription_tier: str = "free",
    ) -> Organization:
        """Create a test organization."""
        cls._counter += 1

        org = Organization(
            id=id or uuid4(),
            github_org_id=github_org_id or (20000 + cls._counter),
            github_org_slug=github_org_slug or f"test-org-{cls._counter}",
            github_org_name=github_org_name or f"Test Organization {cls._counter}",
            billing_email=billing_email or f"billing{cls._counter}@example.com",
            subscription_tier=subscription_tier,
            created_at=datetime.utcnow(),
        )
        db.add(org)
        return org


class OrgMembershipFactory:
    """Factory for creating test org memberships."""

    @classmethod
    def create(
        cls,
        db: Session,
        user_id: UUID,
        org_id: UUID,
        role: str = "member",
        invited_by: Optional[UUID] = None,
    ) -> OrgMembership:
        """Create a test org membership."""
        membership = OrgMembership(
            user_id=user_id,
            org_id=org_id,
            role=role,
            invited_by=invited_by,
            created_at=datetime.utcnow(),
        )
        db.add(membership)
        return membership


class WorkflowRunFactory:
    """Factory for creating test workflow runs."""

    _counter = 0

    @classmethod
    def create(
        cls,
        db: Session,
        org_id: UUID,
        github_run_id: Optional[int] = None,
        repo_name: str = "test-repo",
        workflow_name: str = "CI",
        run_number: int = 1,
        status: str = "completed",
        conclusion: str = "success",
        event: str = "push",
        triggered_by: str = "testuser",
        billable_ms: int = 60000,
        cost_usd: Optional[Decimal] = None,
        created_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None,
    ) -> WorkflowRun:
        """Create a test workflow run."""
        cls._counter += 1

        now = created_at or datetime.utcnow()
        run = WorkflowRun(
            org_id=org_id,
            github_run_id=github_run_id or (30000 + cls._counter),
            repo_name=repo_name,
            workflow_name=workflow_name,
            run_number=run_number,
            status=status,
            conclusion=conclusion,
            event=event,
            triggered_by=triggered_by,
            billable_ms=billable_ms,
            cost_usd=cost_usd or Decimal("0.0080"),
            created_at=now,
            updated_at=datetime.utcnow(),
            completed_at=completed_at or now,  # Default to created_at if not specified
        )
        db.add(run)
        return run


class JobFactory:
    """Factory for creating test jobs."""

    _counter = 0

    @classmethod
    def create(
        cls,
        db: Session,
        org_id: UUID,
        run_github_id: int,
        github_job_id: Optional[int] = None,
        repo_name: str = "test-repo",
        job_name: str = "build",
        status: str = "completed",
        conclusion: str = "success",
        runner_type: str = "ubuntu-latest",
        billable_ms: int = 60000,
        cost_usd: Optional[Decimal] = None,
    ) -> Job:
        """Create a test job."""
        cls._counter += 1

        job = Job(
            id=uuid4(),
            github_job_id=github_job_id or (40000 + cls._counter),
            org_id=org_id,
            run_github_id=run_github_id,
            repo_name=repo_name,
            job_name=job_name,
            status=status,
            conclusion=conclusion,
            runner_type=runner_type,
            billable_ms=billable_ms,
            cost_usd=cost_usd or Decimal("0.0080"),
            created_at=datetime.utcnow(),
        )
        db.add(job)
        return job


class AlertFactory:
    """Factory for creating test alerts."""

    _counter = 0

    @classmethod
    def create(
        cls,
        db: Session,
        org_id: UUID,
        name: Optional[str] = None,
        alert_type: AlertType = AlertType.COST_THRESHOLD,
        threshold_amount: Decimal = Decimal("100.00"),
        period: AlertPeriod = AlertPeriod.DAILY,
        enabled: bool = True,
        notify_email: bool = True,
        notify_slack: bool = False,
        slack_webhook_url: Optional[str] = None,
    ) -> Alert:
        """Create a test alert."""
        cls._counter += 1

        alert = Alert(
            id=uuid4(),
            org_id=org_id,
            name=name or f"Test Alert {cls._counter}",
            alert_type=alert_type,
            threshold_amount=threshold_amount,
            period=period,
            enabled=enabled,
            notify_email=notify_email,
            notify_slack=notify_slack,
            slack_webhook_url=slack_webhook_url,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(alert)
        return alert


class AlertTriggerFactory:
    """Factory for creating test alert triggers."""

    @classmethod
    def create(
        cls,
        db: Session,
        alert_id: UUID,
        threshold_amount: Decimal = Decimal("100.00"),
        actual_amount: Decimal = Decimal("150.00"),
        notified: bool = True,
        triggered_at: Optional[datetime] = None,
    ) -> AlertTrigger:
        """Create a test alert trigger."""
        trigger = AlertTrigger(
            id=uuid4(),
            alert_id=alert_id,
            threshold_amount=threshold_amount,
            actual_amount=actual_amount,
            notified=notified,
            triggered_at=triggered_at or datetime.utcnow(),
        )
        db.add(trigger)
        return trigger


class GitHubInstallationFactory:
    """Factory for creating test GitHub installations."""

    _counter = 0

    @classmethod
    def create(
        cls,
        db: Session,
        org_id: Optional[UUID] = None,
        installation_id: Optional[int] = None,
        account_id: Optional[int] = None,
        account_login: Optional[str] = None,
        account_type: str = "Organization",
        is_active: bool = True,
    ) -> GitHubInstallation:
        """Create a test GitHub installation."""
        cls._counter += 1

        installation = GitHubInstallation(
            id=uuid4(),
            installation_id=installation_id or (50000 + cls._counter),
            account_id=account_id or (60000 + cls._counter),
            account_login=account_login or f"test-org-{cls._counter}",
            account_type=account_type,
            org_id=org_id,
            target_type="Organization",
            repository_selection="all",
            is_active=is_active,
            installed_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(installation)
        return installation


# ============================================================================
# Sample Data Helper
# ============================================================================

def create_sample_data(db: Session) -> dict:
    """
    Create a full set of sample data for testing.

    Returns a dict with all created entities.
    """
    # Create users
    user1 = UserFactory.create(db, email="alice@example.com", github_login="alice")
    user2 = UserFactory.create(db, email="bob@example.com", github_login="bob")

    # Create organizations
    org1 = OrganizationFactory.create(db, github_org_slug="acme-corp", github_org_name="Acme Corporation")
    org2 = OrganizationFactory.create(db, github_org_slug="startup-xyz", github_org_name="Startup XYZ")

    # Create memberships
    mem1 = OrgMembershipFactory.create(db, user_id=user1.id, org_id=org1.id, role="owner")
    mem2 = OrgMembershipFactory.create(db, user_id=user1.id, org_id=org2.id, role="member")
    mem3 = OrgMembershipFactory.create(db, user_id=user2.id, org_id=org1.id, role="member")

    # Create workflow runs with varying costs
    runs = []
    for i in range(10):
        run = WorkflowRunFactory.create(
            db,
            org_id=org1.id,
            repo_name="main-app" if i < 5 else "frontend",
            workflow_name="CI" if i % 2 == 0 else "Deploy",
            billable_ms=60000 * (i + 1),
            cost_usd=Decimal(f"{0.008 * (i + 1):.4f}"),
            created_at=datetime.utcnow() - timedelta(days=i),
        )
        runs.append(run)

    # Create jobs for first few runs
    jobs = []
    for run in runs[:5]:
        job = JobFactory.create(
            db,
            org_id=org1.id,
            run_github_id=run.github_run_id,
            repo_name=run.repo_name,
        )
        jobs.append(job)

    # Create alerts
    alert1 = AlertFactory.create(db, org_id=org1.id, name="Daily Limit", threshold_amount=Decimal("50.00"))
    alert2 = AlertFactory.create(db, org_id=org1.id, name="Weekly Budget", period=AlertPeriod.WEEKLY, threshold_amount=Decimal("200.00"))

    # Create GitHub installation
    installation = GitHubInstallationFactory.create(db, org_id=org1.id, account_login="acme-corp")

    db.commit()

    return {
        "users": [user1, user2],
        "organizations": [org1, org2],
        "memberships": [mem1, mem2, mem3],
        "workflow_runs": runs,
        "jobs": jobs,
        "alerts": [alert1, alert2],
        "installations": [installation],
    }


@pytest.fixture
def sample_data(db: Session) -> dict:
    """Fixture that provides a full set of sample data."""
    return create_sample_data(db)
