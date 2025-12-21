"""Tests for plan limits service."""
import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from app.services.plan_limits import (
    get_plan_limits,
    get_org_tier,
    get_tracked_repo_count,
    get_tracked_repos,
    get_usage_status,
    can_track_repo,
    get_effective_history_days,
    get_history_start_date,
    PLAN_LIMITS,
)
from tests.conftest import OrganizationFactory, WorkflowRunFactory


class TestPlanLimits:
    """Test plan limit definitions."""

    def test_free_tier_limits(self):
        """Free tier should have 3 repos, 30 days history."""
        limits = get_plan_limits("free")
        assert limits.max_repos == 3
        assert limits.max_history_days == 30
        assert limits.max_team_members == 1

    def test_pro_tier_limits(self):
        """Pro tier should have unlimited repos, 365 days history."""
        limits = get_plan_limits("pro")
        assert limits.max_repos is None  # Unlimited
        assert limits.max_history_days == 365
        assert limits.max_team_members == 1

    def test_team_tier_limits(self):
        """Team tier should have unlimited repos, 365 days history, 5 members."""
        limits = get_plan_limits("team")
        assert limits.max_repos is None  # Unlimited
        assert limits.max_history_days == 365
        assert limits.max_team_members == 5

    def test_unknown_tier_defaults_to_free(self):
        """Unknown tier should default to free tier limits."""
        limits = get_plan_limits("enterprise")
        assert limits.max_repos == 3
        assert limits.max_history_days == 30

    def test_case_insensitive_tier(self):
        """Tier names should be case insensitive."""
        limits = get_plan_limits("PRO")
        assert limits.max_repos is None
        assert limits.max_history_days == 365


class TestGetOrgTier:
    """Test getting organization tier."""

    def test_org_tier_returns_subscription_tier(self, db):
        """Should return the organization's subscription tier."""
        org = OrganizationFactory.create(db, subscription_tier="pro")
        db.commit()  # Commit to persist
        tier = get_org_tier(db, org.id)
        assert tier == "pro"

    def test_org_tier_defaults_to_free(self, db):
        """Should default to free if no tier set."""
        org = OrganizationFactory.create(db, subscription_tier="free")
        db.commit()
        tier = get_org_tier(db, org.id)
        assert tier == "free"

    def test_org_tier_not_found_returns_free(self, db):
        """Should return free if organization doesn't exist."""
        tier = get_org_tier(db, uuid4())
        assert tier == "free"


class TestTrackedRepos:
    """Test tracked repository counting."""

    def test_count_no_repos(self, db):
        """Should return 0 when no repos tracked."""
        org = OrganizationFactory.create(db)
        db.commit()
        count = get_tracked_repo_count(db, org.id)
        assert count == 0

    def test_count_with_repos(self, db):
        """Should count unique repos."""
        org = OrganizationFactory.create(db)
        db.commit()
        WorkflowRunFactory.create(db, org_id=org.id, repo_name="org/repo1")
        WorkflowRunFactory.create(db, org_id=org.id, repo_name="org/repo1")  # Duplicate
        WorkflowRunFactory.create(db, org_id=org.id, repo_name="org/repo2")
        db.commit()

        count = get_tracked_repo_count(db, org.id)
        assert count == 2  # Only unique repos

    def test_get_tracked_repos_list(self, db):
        """Should return list of tracked repo names."""
        org = OrganizationFactory.create(db)
        db.commit()
        WorkflowRunFactory.create(db, org_id=org.id, repo_name="org/repo1")
        WorkflowRunFactory.create(db, org_id=org.id, repo_name="org/repo2")
        db.commit()

        repos = get_tracked_repos(db, org.id)
        assert len(repos) == 2
        assert "org/repo1" in repos
        assert "org/repo2" in repos


class TestCanTrackRepo:
    """Test repository tracking permission."""

    def test_can_track_existing_repo(self, db):
        """Should allow tracking already tracked repos even at limit."""
        org = OrganizationFactory.create(db, subscription_tier="free")
        db.commit()
        # Create 3 repos (at limit)
        WorkflowRunFactory.create(db, org_id=org.id, repo_name="org/repo1")
        WorkflowRunFactory.create(db, org_id=org.id, repo_name="org/repo2")
        WorkflowRunFactory.create(db, org_id=org.id, repo_name="org/repo3")
        db.commit()

        # Should still be able to track existing repo
        assert can_track_repo(db, org.id, "org/repo1") is True

    def test_cannot_track_new_repo_at_limit(self, db):
        """Should not allow new repos when at limit."""
        org = OrganizationFactory.create(db, subscription_tier="free")
        db.commit()
        # Create 3 repos (at limit)
        WorkflowRunFactory.create(db, org_id=org.id, repo_name="org/repo1")
        WorkflowRunFactory.create(db, org_id=org.id, repo_name="org/repo2")
        WorkflowRunFactory.create(db, org_id=org.id, repo_name="org/repo3")
        db.commit()

        # Should not be able to track new repo
        assert can_track_repo(db, org.id, "org/repo4") is False

    def test_can_track_new_repo_below_limit(self, db):
        """Should allow new repos when below limit."""
        org = OrganizationFactory.create(db, subscription_tier="free")
        db.commit()
        # Create 2 repos (below limit)
        WorkflowRunFactory.create(db, org_id=org.id, repo_name="org/repo1")
        WorkflowRunFactory.create(db, org_id=org.id, repo_name="org/repo2")
        db.commit()

        # Should be able to track new repo
        assert can_track_repo(db, org.id, "org/repo3") is True

    def test_pro_tier_unlimited_repos(self, db):
        """Pro tier should have unlimited repos."""
        org = OrganizationFactory.create(db, subscription_tier="pro")
        db.commit()
        # Create many repos
        for i in range(10):
            WorkflowRunFactory.create(db, org_id=org.id, repo_name=f"org/repo{i}")
        db.commit()

        # Should always be able to track more
        assert can_track_repo(db, org.id, "org/repo99") is True


class TestEffectiveHistoryDays:
    """Test history day capping."""

    def test_free_tier_caps_at_30_days(self, db):
        """Free tier should cap history at 30 days."""
        org = OrganizationFactory.create(db, subscription_tier="free")
        db.commit()
        effective = get_effective_history_days(db, org.id, 90)
        assert effective == 30

    def test_free_tier_allows_less_than_30(self, db):
        """Free tier should allow fewer than 30 days."""
        org = OrganizationFactory.create(db, subscription_tier="free")
        db.commit()
        effective = get_effective_history_days(db, org.id, 7)
        assert effective == 7

    def test_pro_tier_caps_at_365_days(self, db):
        """Pro tier should cap history at 365 days."""
        org = OrganizationFactory.create(db, subscription_tier="pro")
        db.commit()
        effective = get_effective_history_days(db, org.id, 730)
        assert effective == 365

    def test_pro_tier_allows_less_than_365(self, db):
        """Pro tier should allow fewer than 365 days."""
        org = OrganizationFactory.create(db, subscription_tier="pro")
        db.commit()
        effective = get_effective_history_days(db, org.id, 90)
        assert effective == 90


class TestHistoryStartDate:
    """Test history start date calculation."""

    def test_free_tier_start_date(self, db):
        """Free tier should start 30 days ago."""
        org = OrganizationFactory.create(db, subscription_tier="free")
        db.commit()
        start = get_history_start_date(db, org.id)
        expected = datetime.utcnow() - timedelta(days=30)
        # Allow 1 minute tolerance
        assert abs((start - expected).total_seconds()) < 60

    def test_pro_tier_start_date(self, db):
        """Pro tier should start 365 days ago."""
        org = OrganizationFactory.create(db, subscription_tier="pro")
        db.commit()
        start = get_history_start_date(db, org.id)
        expected = datetime.utcnow() - timedelta(days=365)
        # Allow 1 minute tolerance
        assert abs((start - expected).total_seconds()) < 60


class TestUsageStatus:
    """Test usage status calculation."""

    def test_usage_status_empty_org(self, db):
        """Should return correct status for empty org."""
        org = OrganizationFactory.create(db, subscription_tier="free")
        db.commit()
        status = get_usage_status(db, org.id)

        assert status.tier == "free"
        assert status.repos_used == 0
        assert status.repos_limit == 3
        assert status.repos_at_limit is False
        assert status.history_days_limit == 30

    def test_usage_status_at_limit(self, db):
        """Should correctly detect when at limit."""
        org = OrganizationFactory.create(db, subscription_tier="free")
        db.commit()
        WorkflowRunFactory.create(db, org_id=org.id, repo_name="org/repo1")
        WorkflowRunFactory.create(db, org_id=org.id, repo_name="org/repo2")
        WorkflowRunFactory.create(db, org_id=org.id, repo_name="org/repo3")
        db.commit()

        status = get_usage_status(db, org.id)
        assert status.repos_used == 3
        assert status.repos_at_limit is True

    def test_usage_status_pro_tier(self, db):
        """Pro tier should show unlimited repos."""
        org = OrganizationFactory.create(db, subscription_tier="pro")
        db.commit()
        for i in range(5):
            WorkflowRunFactory.create(db, org_id=org.id, repo_name=f"org/repo{i}")
        db.commit()

        status = get_usage_status(db, org.id)
        assert status.tier == "pro"
        assert status.repos_used == 5
        assert status.repos_limit is None
        assert status.repos_at_limit is False
        assert status.history_days_limit == 365
