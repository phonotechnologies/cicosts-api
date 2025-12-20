#!/usr/bin/env python3
"""
Seed script for populating the database with sample data.

Usage:
    python scripts/seed_data.py

This will create:
- 2 users (alice, bob)
- 2 organizations (acme-corp, startup-xyz)
- Organization memberships
- 30 workflow runs with varying costs
- Jobs for workflow runs
- Alerts
- GitHub installations
"""
import os
import sys
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import uuid4
import random

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.user import User
from app.models.organization import Organization
from app.models.org_membership import OrgMembership
from app.models.workflow_run import WorkflowRun
from app.models.job import Job
from app.models.alert import Alert, AlertType, AlertPeriod
from app.models.github_installation import GitHubInstallation


def seed_database():
    """Seed the database with sample data."""
    db = SessionLocal()

    try:
        print("Starting database seed...")

        # Check if data already exists
        existing_users = db.query(User).count()
        if existing_users > 0:
            print(f"Database already has {existing_users} users. Skipping seed.")
            print("To re-seed, clear the database first.")
            return

        # Create users
        print("Creating users...")
        users = create_users(db)

        # Create organizations
        print("Creating organizations...")
        orgs = create_organizations(db)

        # Create memberships
        print("Creating organization memberships...")
        create_memberships(db, users, orgs)

        # Create workflow runs
        print("Creating workflow runs...")
        runs = create_workflow_runs(db, orgs[0])

        # Create jobs
        print("Creating jobs...")
        create_jobs(db, orgs[0], runs)

        # Create alerts
        print("Creating alerts...")
        create_alerts(db, orgs[0])

        # Create GitHub installations
        print("Creating GitHub installations...")
        create_installations(db, orgs)

        db.commit()
        print("\nDatabase seeded successfully!")
        print_summary(db)

    except Exception as e:
        db.rollback()
        print(f"Error seeding database: {e}")
        raise
    finally:
        db.close()


def create_users(db: Session) -> list[User]:
    """Create sample users."""
    users = []

    user1 = User(
        id=uuid4(),
        email="alice@example.com",
        github_id=10001,
        github_login="alice",
        github_avatar_url="https://avatars.githubusercontent.com/u/10001",
        notification_email="alice@example.com",
        weekly_digest_enabled=True,
        alert_emails_enabled=True,
        created_at=datetime.utcnow() - timedelta(days=30),
        updated_at=datetime.utcnow(),
    )
    db.add(user1)
    users.append(user1)

    user2 = User(
        id=uuid4(),
        email="bob@example.com",
        github_id=10002,
        github_login="bob",
        github_avatar_url="https://avatars.githubusercontent.com/u/10002",
        notification_email="bob@example.com",
        weekly_digest_enabled=False,
        alert_emails_enabled=True,
        created_at=datetime.utcnow() - timedelta(days=15),
        updated_at=datetime.utcnow(),
    )
    db.add(user2)
    users.append(user2)

    user3 = User(
        id=uuid4(),
        email="charlie@example.com",
        github_id=10003,
        github_login="charlie",
        github_avatar_url="https://avatars.githubusercontent.com/u/10003",
        created_at=datetime.utcnow() - timedelta(days=7),
        updated_at=datetime.utcnow(),
    )
    db.add(user3)
    users.append(user3)

    return users


def create_organizations(db: Session) -> list[Organization]:
    """Create sample organizations."""
    orgs = []

    org1 = Organization(
        id=uuid4(),
        github_org_id=20001,
        github_org_slug="acme-corp",
        github_org_name="Acme Corporation",
        billing_email="billing@acme-corp.com",
        subscription_tier="pro",
        created_at=datetime.utcnow() - timedelta(days=60),
    )
    db.add(org1)
    orgs.append(org1)

    org2 = Organization(
        id=uuid4(),
        github_org_id=20002,
        github_org_slug="startup-xyz",
        github_org_name="Startup XYZ",
        billing_email="admin@startup-xyz.com",
        subscription_tier="free",
        created_at=datetime.utcnow() - timedelta(days=30),
    )
    db.add(org2)
    orgs.append(org2)

    return orgs


def create_memberships(db: Session, users: list[User], orgs: list[Organization]):
    """Create organization memberships."""
    # Alice owns acme-corp and is member of startup-xyz
    db.add(OrgMembership(
        user_id=users[0].id,
        org_id=orgs[0].id,
        role="owner",
        created_at=datetime.utcnow() - timedelta(days=60),
    ))

    db.add(OrgMembership(
        user_id=users[0].id,
        org_id=orgs[1].id,
        role="member",
        created_at=datetime.utcnow() - timedelta(days=15),
    ))

    # Bob is a member of acme-corp
    db.add(OrgMembership(
        user_id=users[1].id,
        org_id=orgs[0].id,
        role="admin",
        created_at=datetime.utcnow() - timedelta(days=30),
    ))

    # Charlie owns startup-xyz
    db.add(OrgMembership(
        user_id=users[2].id,
        org_id=orgs[1].id,
        role="owner",
        created_at=datetime.utcnow() - timedelta(days=30),
    ))


def create_workflow_runs(db: Session, org: Organization) -> list[WorkflowRun]:
    """Create sample workflow runs over the past 30 days."""
    runs = []

    repos = ["main-app", "frontend", "backend-api", "infrastructure"]
    workflows = ["CI Pipeline", "Deploy Production", "Deploy Staging", "Nightly Tests", "Security Scan"]
    conclusions = ["success", "success", "success", "success", "failure", "cancelled"]
    events = ["push", "push", "push", "pull_request", "schedule"]

    for day in range(30):
        # 2-5 runs per day
        num_runs = random.randint(2, 5)

        for _ in range(num_runs):
            repo = random.choice(repos)
            workflow = random.choice(workflows)
            conclusion = random.choice(conclusions)
            event = random.choice(events)

            # Cost varies by workflow type
            if workflow == "Deploy Production":
                base_cost = Decimal("0.50")
                billable_ms = 600000  # 10 minutes
            elif workflow == "CI Pipeline":
                base_cost = Decimal("0.15")
                billable_ms = 180000  # 3 minutes
            elif workflow == "Nightly Tests":
                base_cost = Decimal("1.20")
                billable_ms = 1500000  # 25 minutes
            else:
                base_cost = Decimal("0.08")
                billable_ms = 120000  # 2 minutes

            # Add some randomness
            cost_variation = Decimal(str(random.uniform(0.8, 1.2)))
            cost = (base_cost * cost_variation).quantize(Decimal("0.0001"))

            run = WorkflowRun(
                org_id=org.id,
                github_run_id=30000 + len(runs),
                repo_name=repo,
                workflow_name=workflow,
                run_number=len(runs) + 1,
                status="completed",
                conclusion=conclusion,
                event=event,
                triggered_by=random.choice(["alice", "bob", "charlie", "dependabot"]),
                billable_ms=billable_ms,
                cost_usd=cost,
                created_at=datetime.utcnow() - timedelta(days=day, hours=random.randint(0, 23)),
                updated_at=datetime.utcnow() - timedelta(days=day),
            )
            db.add(run)
            runs.append(run)

    return runs


def create_jobs(db: Session, org: Organization, runs: list[WorkflowRun]):
    """Create jobs for workflow runs."""
    job_names = ["build", "test", "lint", "security-scan", "deploy"]
    runner_types = [
        "ubuntu-latest",
        "ubuntu-latest",
        "ubuntu-latest",
        "ubuntu-latest-4-cores",
        "macos-latest",
    ]

    for run in runs[:20]:  # Create jobs for first 20 runs
        num_jobs = random.randint(1, 4)

        for i in range(num_jobs):
            job_name = job_names[i % len(job_names)]
            runner = runner_types[i % len(runner_types)]

            # Calculate cost based on runner
            if runner == "ubuntu-latest":
                cost_per_min = Decimal("0.008")
            elif runner == "ubuntu-latest-4-cores":
                cost_per_min = Decimal("0.016")
            else:
                cost_per_min = Decimal("0.08")

            duration_mins = random.randint(1, 10)
            cost = (cost_per_min * duration_mins).quantize(Decimal("0.0001"))

            job = Job(
                id=uuid4(),
                github_job_id=40000 + random.randint(1, 999999),
                org_id=org.id,
                run_github_id=run.github_run_id,
                repo_name=run.repo_name,
                job_name=job_name,
                status="completed",
                conclusion=run.conclusion,
                runner_type=runner,
                billable_ms=duration_mins * 60000,
                cost_usd=cost,
                created_at=run.created_at,
            )
            db.add(job)


def create_alerts(db: Session, org: Organization):
    """Create sample alerts."""
    alerts = [
        {
            "name": "Daily Cost Limit",
            "alert_type": AlertType.COST_THRESHOLD,
            "threshold_amount": Decimal("50.00"),
            "period": AlertPeriod.DAILY,
            "enabled": True,
            "notify_email": True,
        },
        {
            "name": "Weekly Budget Alert",
            "alert_type": AlertType.BUDGET_LIMIT,
            "threshold_amount": Decimal("200.00"),
            "period": AlertPeriod.WEEKLY,
            "enabled": True,
            "notify_email": True,
        },
        {
            "name": "Monthly Spend Limit",
            "alert_type": AlertType.BUDGET_LIMIT,
            "threshold_amount": Decimal("500.00"),
            "period": AlertPeriod.MONTHLY,
            "enabled": True,
            "notify_email": True,
            "notify_slack": True,
        },
        {
            "name": "Critical Spend Alert",
            "alert_type": AlertType.COST_THRESHOLD,
            "threshold_amount": Decimal("100.00"),
            "period": AlertPeriod.DAILY,
            "enabled": False,  # Disabled
            "notify_email": True,
        },
    ]

    for alert_data in alerts:
        alert = Alert(
            id=uuid4(),
            org_id=org.id,
            **alert_data,
            created_at=datetime.utcnow() - timedelta(days=random.randint(1, 30)),
            updated_at=datetime.utcnow(),
        )
        db.add(alert)


def create_installations(db: Session, orgs: list[Organization]):
    """Create GitHub App installations."""
    for org in orgs:
        installation = GitHubInstallation(
            id=uuid4(),
            installation_id=50000 + orgs.index(org),
            account_id=org.github_org_id,
            account_login=org.github_org_slug,
            account_type="Organization",
            org_id=org.id,
            target_type="Organization",
            repository_selection="all",
            is_active=True,
            installed_at=org.created_at,
            updated_at=datetime.utcnow(),
        )
        db.add(installation)


def print_summary(db: Session):
    """Print summary of seeded data."""
    print("\n" + "=" * 50)
    print("SEED SUMMARY")
    print("=" * 50)
    print(f"Users:            {db.query(User).count()}")
    print(f"Organizations:    {db.query(Organization).count()}")
    print(f"Memberships:      {db.query(OrgMembership).count()}")
    print(f"Workflow Runs:    {db.query(WorkflowRun).count()}")
    print(f"Jobs:             {db.query(Job).count()}")
    print(f"Alerts:           {db.query(Alert).count()}")
    print(f"Installations:    {db.query(GitHubInstallation).count()}")
    print("=" * 50)

    # Calculate total cost
    total_cost = db.query(WorkflowRun).with_entities(
        db.query(WorkflowRun.cost_usd).subquery()
    ).scalar()
    # Note: This is a simplified query, actual total would need sum()

    print("\nSample login credentials:")
    print("  Email: alice@example.com")
    print("  GitHub: alice (ID: 10001)")
    print("\nUse GitHub OAuth to authenticate in the real app.")


if __name__ == "__main__":
    seed_database()
