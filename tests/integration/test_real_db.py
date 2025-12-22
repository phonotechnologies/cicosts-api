"""
Real Database Integration Tests

Run the existing test suite against a real Supabase database
instead of SQLite in-memory mocks.

Run with:
    INTEGRATION_DATABASE_URL="postgresql://..." pytest tests/integration/test_real_db.py -v --integration

This module re-runs select tests from the unit test suite against
the real database to verify ORM compatibility.
"""

import os
import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import uuid4

pytestmark = pytest.mark.integration

# Check for real database URL
DATABASE_URL = os.getenv("INTEGRATION_DATABASE_URL", "")


@pytest.fixture(scope="module")
def skip_without_database():
    """Skip all tests in this module if DATABASE_URL not set."""
    if not DATABASE_URL:
        pytest.skip("INTEGRATION_DATABASE_URL not set")


@pytest.fixture(scope="module")
def real_db(skip_without_database):
    """Create real database session."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()

    yield session

    session.close()


@pytest.fixture(scope="function")
def clean_test_data(real_db):
    """Clean up test data after each test."""
    yield

    # Clean up any test data created during tests
    # Only clean data with specific test markers
    from app.models.workflow_run import WorkflowRun
    from app.models.job import Job
    from app.models.alert import Alert
    from app.models.alert_trigger import AlertTrigger

    # Delete test workflow runs (those with 'integration-test-' prefix)
    real_db.query(WorkflowRun).filter(
        WorkflowRun.repo_name.like("integration-test-%")
    ).delete(synchronize_session=False)

    real_db.query(Job).filter(
        Job.repo_name.like("integration-test-%")
    ).delete(synchronize_session=False)

    real_db.commit()


class TestDatabaseConnection:
    """Test database connectivity and basic operations."""

    def test_can_connect(self, real_db):
        """Test database connection works."""
        result = real_db.execute("SELECT 1").scalar()
        assert result == 1

    def test_can_query_users(self, real_db):
        """Test can query users table."""
        from app.models.user import User

        count = real_db.query(User).count()
        assert count >= 0  # Just verify query works

    def test_can_query_organizations(self, real_db):
        """Test can query organizations table."""
        from app.models.organization import Organization

        count = real_db.query(Organization).count()
        assert count >= 0


class TestWorkflowRunOperations:
    """Test WorkflowRun CRUD operations against real database."""

    def test_create_workflow_run(self, real_db, clean_test_data):
        """Test creating a workflow run."""
        from app.models.workflow_run import WorkflowRun
        from app.models.organization import Organization

        # Get first org
        org = real_db.query(Organization).first()
        if not org:
            pytest.skip("No organizations in database")

        # Create test run
        run = WorkflowRun(
            org_id=org.id,
            github_run_id=int(datetime.utcnow().timestamp() * 1000),
            repo_name="integration-test-repo",
            workflow_name="Integration Test",
            run_number=1,
            status="completed",
            conclusion="success",
            event="push",
            triggered_by="integration-test",
            billable_ms=60000,
            cost_usd=Decimal("0.008"),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            completed_at=datetime.utcnow(),
        )
        real_db.add(run)
        real_db.commit()

        # Verify it was created
        saved = real_db.query(WorkflowRun).filter(
            WorkflowRun.github_run_id == run.github_run_id
        ).first()
        assert saved is not None
        assert saved.workflow_name == "Integration Test"

        # Clean up
        real_db.delete(saved)
        real_db.commit()

    def test_query_workflow_runs_with_date_filter(self, real_db):
        """Test querying workflow runs with date filter."""
        from app.models.workflow_run import WorkflowRun

        # Query runs from last 30 days
        since = datetime.utcnow() - timedelta(days=30)
        runs = real_db.query(WorkflowRun).filter(
            WorkflowRun.created_at >= since
        ).all()

        assert isinstance(runs, list)

    def test_aggregate_costs(self, real_db):
        """Test aggregating workflow costs."""
        from sqlalchemy import func
        from app.models.workflow_run import WorkflowRun

        # Sum costs from last 7 days
        since = datetime.utcnow() - timedelta(days=7)
        total = real_db.query(
            func.sum(WorkflowRun.cost_usd)
        ).filter(
            WorkflowRun.created_at >= since
        ).scalar()

        # Total could be None if no runs, or a Decimal
        assert total is None or isinstance(total, Decimal)


class TestJobOperations:
    """Test Job CRUD operations against real database."""

    def test_query_jobs(self, real_db):
        """Test querying jobs."""
        from app.models.job import Job

        jobs = real_db.query(Job).limit(10).all()
        assert isinstance(jobs, list)

    def test_job_cost_calculation(self, real_db):
        """Test job cost fields are correct types."""
        from app.models.job import Job

        job = real_db.query(Job).first()
        if job:
            assert isinstance(job.billable_ms, int)
            assert isinstance(job.cost_usd, Decimal)


class TestAlertOperations:
    """Test Alert CRUD operations."""

    def test_query_alerts(self, real_db):
        """Test querying alerts."""
        from app.models.alert import Alert

        alerts = real_db.query(Alert).limit(10).all()
        assert isinstance(alerts, list)

    def test_alert_trigger_relationship(self, real_db):
        """Test alert-trigger relationship works."""
        from app.models.alert import Alert
        from app.models.alert_trigger import AlertTrigger

        alert = real_db.query(Alert).first()
        if alert:
            # Access relationship
            triggers = alert.triggers
            assert isinstance(triggers, list)


class TestOrganizationOperations:
    """Test Organization operations."""

    def test_org_membership_relationship(self, real_db):
        """Test org membership relationship."""
        from app.models.organization import Organization

        org = real_db.query(Organization).first()
        if org:
            # Access relationship
            memberships = org.members
            assert isinstance(memberships, list)

    def test_org_subscription_tier(self, real_db):
        """Test org subscription tier field."""
        from app.models.organization import Organization

        org = real_db.query(Organization).first()
        if org:
            assert org.subscription_tier in ("free", "pro", "team", "enterprise")


class TestDashboardQueries:
    """Test dashboard-specific queries that mimic actual API usage."""

    def test_summary_query(self, real_db):
        """Test dashboard summary query."""
        from sqlalchemy import func
        from app.models.workflow_run import WorkflowRun
        from app.models.organization import Organization

        org = real_db.query(Organization).first()
        if not org:
            pytest.skip("No organizations in database")

        since = datetime.utcnow() - timedelta(days=30)

        # Mimic dashboard summary query
        result = real_db.query(
            func.count(WorkflowRun.id).label("total_runs"),
            func.sum(WorkflowRun.cost_usd).label("total_cost"),
            func.sum(WorkflowRun.billable_ms).label("total_ms")
        ).filter(
            WorkflowRun.org_id == org.id,
            WorkflowRun.created_at >= since
        ).first()

        assert result is not None
        assert result.total_runs >= 0

    def test_top_workflows_query(self, real_db):
        """Test top workflows query."""
        from sqlalchemy import func
        from app.models.workflow_run import WorkflowRun
        from app.models.organization import Organization

        org = real_db.query(Organization).first()
        if not org:
            pytest.skip("No organizations in database")

        since = datetime.utcnow() - timedelta(days=30)

        # Top workflows by cost
        results = real_db.query(
            WorkflowRun.workflow_name,
            WorkflowRun.repo_name,
            func.sum(WorkflowRun.cost_usd).label("total_cost"),
            func.count(WorkflowRun.id).label("run_count")
        ).filter(
            WorkflowRun.org_id == org.id,
            WorkflowRun.created_at >= since
        ).group_by(
            WorkflowRun.workflow_name,
            WorkflowRun.repo_name
        ).order_by(
            func.sum(WorkflowRun.cost_usd).desc()
        ).limit(5).all()

        assert isinstance(results, list)

    def test_trends_query(self, real_db):
        """Test daily trends query."""
        from sqlalchemy import func, cast, Date
        from app.models.workflow_run import WorkflowRun
        from app.models.organization import Organization

        org = real_db.query(Organization).first()
        if not org:
            pytest.skip("No organizations in database")

        since = datetime.utcnow() - timedelta(days=30)

        # Daily cost trends
        results = real_db.query(
            cast(WorkflowRun.created_at, Date).label("date"),
            func.sum(WorkflowRun.cost_usd).label("cost")
        ).filter(
            WorkflowRun.org_id == org.id,
            WorkflowRun.created_at >= since
        ).group_by(
            cast(WorkflowRun.created_at, Date)
        ).order_by(
            cast(WorkflowRun.created_at, Date)
        ).all()

        assert isinstance(results, list)


class TestPlanLimitsQueries:
    """Test plan limits related queries."""

    def test_tracked_repos_count(self, real_db):
        """Test counting unique tracked repos."""
        from sqlalchemy import func
        from app.models.workflow_run import WorkflowRun
        from app.models.organization import Organization

        org = real_db.query(Organization).first()
        if not org:
            pytest.skip("No organizations in database")

        # Count unique repos
        count = real_db.query(
            func.count(func.distinct(WorkflowRun.repo_name))
        ).filter(
            WorkflowRun.org_id == org.id
        ).scalar()

        assert count >= 0

    def test_unique_repos_list(self, real_db):
        """Test listing unique tracked repos."""
        from app.models.workflow_run import WorkflowRun
        from app.models.organization import Organization

        org = real_db.query(Organization).first()
        if not org:
            pytest.skip("No organizations in database")

        # Get unique repos
        repos = real_db.query(
            WorkflowRun.repo_name
        ).filter(
            WorkflowRun.org_id == org.id
        ).distinct().all()

        assert isinstance(repos, list)
        for repo in repos:
            assert isinstance(repo[0], str)
