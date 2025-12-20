"""
Lambda workers handler.

Processes EventBridge scheduled jobs and SQS webhook messages.
Reference: infrastructure/eventbridge.tf
"""
import json
import logging
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


def handle_scheduled_job(event: dict) -> dict:
    """
    Handle EventBridge scheduled job.

    Jobs:
    - daily_sync: Sync GitHub/AWS costs (2 AM UTC)
    - trial_eligibility_check: Check trial eligibility (2:30 AM UTC)
    - data_cleanup: Delete expired data (3 AM UTC)
    - hard_delete_expired_users: Hard delete after 30 days (4 AM UTC)
    - weekly_digest_email: Send weekly digests (Monday 8 AM UTC)
    - health_check: System health check (every 5 min)
    """
    job_type = event.get("job_type")
    tasks = event.get("tasks", [])

    logger.info(f"Processing scheduled job: {job_type}")

    handlers = {
        "daily_sync": _handle_daily_sync,
        "trial_eligibility_check": _handle_trial_check,
        "data_cleanup": _handle_data_cleanup,
        "hard_delete_expired_users": _handle_hard_delete,
        "weekly_digest_email": _handle_weekly_digest,
        "health_check": _handle_health_check,
    }

    handler_fn = handlers.get(job_type)
    if not handler_fn:
        logger.warning(f"Unknown job type: {job_type}")
        return {"statusCode": 400, "body": f"Unknown job: {job_type}"}

    try:
        result = handler_fn(tasks)
        return {"statusCode": 200, "body": json.dumps(result)}
    except Exception as e:
        logger.error(f"Job {job_type} failed: {e}")
        return {"statusCode": 500, "body": str(e)}


def handle_sqs_webhooks(records: list) -> dict:
    """
    Process webhook messages from SQS queue.

    Uses partial batch failure reporting.
    Reference: spec-error-handling.md § 2.2
    """
    batch_item_failures = []

    for record in records:
        try:
            body = json.loads(record["body"])
            event_type = body.get("event_type")
            payload = body.get("payload", {})
            delivery_id = body.get("delivery_id")

            logger.info(f"Processing webhook: {event_type} (delivery: {delivery_id})")

            if event_type == "workflow_run":
                _process_workflow_run(payload)
            elif event_type == "workflow_job":
                _process_workflow_job(payload)
            elif event_type == "installation":
                _process_installation(payload)
            else:
                logger.info(f"Ignoring event type: {event_type}")

        except Exception as e:
            logger.error(f"Failed to process message {record['messageId']}: {e}", exc_info=True)
            batch_item_failures.append({
                "itemIdentifier": record["messageId"]
            })

    return {"batchItemFailures": batch_item_failures}


# Job handlers

def _handle_daily_sync(tasks: list) -> dict:
    """Sync GitHub and AWS costs."""
    logger.info(f"Running daily sync tasks: {tasks}")
    # TODO: Implement
    return {"status": "completed", "tasks": tasks}


def _handle_trial_check(tasks: list) -> dict:
    """Check trial eligibility for engaged users."""
    logger.info("Checking trial eligibility")
    # TODO: Implement (spec-data-lifecycle.md § 6.3)
    return {"status": "completed", "checked": 0}


def _handle_data_cleanup(tasks: list) -> dict:
    """Delete expired data based on retention policy."""
    logger.info(f"Running data cleanup tasks: {tasks}")
    # TODO: Implement (spec-data-lifecycle.md § 2.2)
    return {"status": "completed", "deleted": 0}


def _handle_hard_delete(tasks: list) -> dict:
    """Hard delete users 30 days after soft delete."""
    logger.info("Processing hard deletes")
    # TODO: Implement (spec-data-lifecycle.md § 8.1)
    return {"status": "completed", "deleted": 0}


def _handle_weekly_digest(tasks: list) -> dict:
    """Send weekly cost digest emails."""
    logger.info("Sending weekly digests")
    # TODO: Implement
    return {"status": "completed", "sent": 0}


def _handle_health_check(tasks: list) -> dict:
    """Check system health."""
    logger.info(f"Running health checks: {tasks}")
    # TODO: Implement (spec-error-handling.md § 7.2)
    return {"status": "ok", "checks": tasks}


# Webhook processors

def _process_workflow_run(payload: dict) -> None:
    """
    Process workflow_run webhook.

    Reference: spec-cost-calculation.md § 4.3
    """
    from app.database import get_session_local
    from app.models.workflow_run import WorkflowRun
    from app.models.organization import Organization

    action = payload.get("action")
    run = payload.get("workflow_run", {})
    repository = payload.get("repository", {})
    organization = payload.get("organization", {})
    sender = payload.get("sender", {})

    run_id = run.get("id")
    logger.info(f"Workflow run {run_id}: {action}")

    # Only process completed runs
    if action != "completed":
        logger.info(f"Ignoring workflow_run action: {action}")
        return

    # Get database session
    SessionLocal = get_session_local()
    db = SessionLocal()

    try:
        # Find organization
        org = db.query(Organization).filter(
            Organization.github_org_id == organization.get("id")
        ).first()

        if not org:
            logger.warning(f"Organization not found: {organization.get('login')}")
            return

        # Parse timestamps
        created_at = _parse_github_timestamp(run.get("created_at"))
        updated_at = _parse_github_timestamp(run.get("updated_at"))
        completed_at = _parse_github_timestamp(run.get("run_started_at"))

        # Calculate billable time from usage if available
        billable_ms = 0
        timing = run.get("timing", {})
        if timing:
            # Sum up billable time from all runner types
            for runner_type, runner_timing in timing.items():
                billable_ms += runner_timing.get("total_ms", 0)

        # Check if run already exists
        existing = db.query(WorkflowRun).filter(
            WorkflowRun.org_id == org.id,
            WorkflowRun.github_run_id == run_id,
        ).first()

        if existing:
            # Update existing run
            existing.status = run.get("status", "completed")
            existing.conclusion = run.get("conclusion")
            existing.updated_at = updated_at or datetime.utcnow()
            existing.completed_at = completed_at
            existing.billable_ms = billable_ms
            logger.info(f"Updated workflow run {run_id}")
        else:
            # Create new run
            workflow_run = WorkflowRun(
                org_id=org.id,
                github_run_id=run_id,
                repo_name=repository.get("full_name", repository.get("name", "")),
                repo_id=repository.get("id"),
                workflow_name=run.get("name", ""),
                workflow_id=run.get("workflow_id"),
                run_number=run.get("run_number", 0),
                status=run.get("status", "completed"),
                conclusion=run.get("conclusion"),
                event=run.get("event"),
                triggered_by=sender.get("login"),
                created_at=created_at or datetime.utcnow(),
                updated_at=updated_at or datetime.utcnow(),
                completed_at=completed_at,
                billable_ms=billable_ms,
                cost_usd=Decimal("0"),  # Will be calculated from jobs
            )
            db.add(workflow_run)
            logger.info(f"Created workflow run {run_id}")

        db.commit()

    except Exception as e:
        logger.error(f"Error processing workflow_run: {e}", exc_info=True)
        db.rollback()
        raise
    finally:
        db.close()


def _process_workflow_job(payload: dict) -> None:
    """
    Process workflow_job webhook.

    This is where we calculate actual costs based on runner type and duration.
    Reference: spec-cost-calculation.md § 2.1
    """
    from app.database import get_session_local
    from app.models.job import Job
    from app.models.workflow_run import WorkflowRun
    from app.models.organization import Organization
    from app.services.cost_calculator import calculate_job_cost

    action = payload.get("action")
    job = payload.get("workflow_job", {})
    repository = payload.get("repository", {})
    organization = payload.get("organization", {})

    job_id = job.get("id")
    run_id = job.get("run_id")

    logger.info(f"Workflow job {job_id}: {action}")

    # Only process completed jobs
    if action != "completed":
        logger.info(f"Ignoring workflow_job action: {action}")
        return

    # Get database session
    SessionLocal = get_session_local()
    db = SessionLocal()

    try:
        # Find organization
        org = db.query(Organization).filter(
            Organization.github_org_id == organization.get("id")
        ).first()

        if not org:
            logger.warning(f"Organization not found: {organization.get('login')}")
            return

        # Parse timestamps
        created_at = _parse_github_timestamp(job.get("created_at"))
        started_at = _parse_github_timestamp(job.get("started_at"))
        completed_at = _parse_github_timestamp(job.get("completed_at"))

        # Calculate billable time
        billable_ms = 0
        if started_at and completed_at:
            billable_ms = int((completed_at - started_at).total_seconds() * 1000)

        # Determine runner type from labels
        runner_labels = job.get("labels", [])
        runner_type = _determine_runner_type(runner_labels)

        # Calculate cost
        cost = calculate_job_cost(runner_type, billable_ms)

        # Check if job already exists
        existing = db.query(Job).filter(
            Job.github_job_id == job_id,
            Job.org_id == org.id,
        ).first()

        if existing:
            # Update existing job
            existing.status = job.get("status", "completed")
            existing.conclusion = job.get("conclusion")
            existing.completed_at = completed_at
            existing.billable_ms = billable_ms
            existing.cost_usd = cost
            existing.runner_type = runner_type
            logger.info(f"Updated job {job_id}, cost: ${cost}")
        else:
            # Create new job
            new_job = Job(
                id=uuid4(),
                github_job_id=job_id,
                org_id=org.id,
                run_github_id=run_id,
                repo_name=repository.get("full_name", repository.get("name", "")),
                job_name=job.get("name", ""),
                status=job.get("status", "completed"),
                conclusion=job.get("conclusion"),
                runner_type=runner_type,
                billable_ms=billable_ms,
                cost_usd=cost,
                created_at=created_at or datetime.utcnow(),
                started_at=started_at,
                completed_at=completed_at,
            )
            db.add(new_job)
            logger.info(f"Created job {job_id}, cost: ${cost}")

        # Update workflow run total cost
        _update_workflow_run_cost(db, org.id, run_id)

        db.commit()

    except Exception as e:
        logger.error(f"Error processing workflow_job: {e}", exc_info=True)
        db.rollback()
        raise
    finally:
        db.close()


def _process_installation(payload: dict) -> None:
    """
    Process GitHub App installation webhook.

    Handles: created, deleted, suspend, unsuspend
    """
    from app.database import get_session_local
    from app.models.github_installation import GitHubInstallation
    from app.models.organization import Organization

    action = payload.get("action")
    installation = payload.get("installation", {})
    sender = payload.get("sender", {})

    installation_id = installation.get("id")
    account = installation.get("account", {})

    logger.info(f"Installation {installation_id}: {action} by {sender.get('login')}")

    # Get database session
    SessionLocal = get_session_local()
    db = SessionLocal()

    try:
        if action == "created":
            # Check if installation already exists
            existing = db.query(GitHubInstallation).filter(
                GitHubInstallation.installation_id == installation_id
            ).first()

            if existing:
                # Reactivate if previously uninstalled
                existing.is_active = True
                existing.uninstalled_at = None
                existing.updated_at = datetime.utcnow()
                logger.info(f"Reactivated installation {installation_id}")
            else:
                # Find or create organization
                org = db.query(Organization).filter(
                    Organization.github_org_id == account.get("id")
                ).first()

                org_id = org.id if org else None

                # Create new installation
                new_installation = GitHubInstallation(
                    id=uuid4(),
                    installation_id=installation_id,
                    account_id=account.get("id"),
                    account_type=account.get("type", "Organization"),
                    account_login=account.get("login", ""),
                    org_id=org_id,
                    target_type=installation.get("target_type", "Organization"),
                    repository_selection=installation.get("repository_selection", "all"),
                    permissions=json.dumps(installation.get("permissions", {})),
                    events=json.dumps(installation.get("events", [])),
                    installed_at=datetime.utcnow(),
                )
                db.add(new_installation)
                logger.info(f"Created installation {installation_id} for {account.get('login')}")

        elif action == "deleted":
            # Mark installation as inactive
            existing = db.query(GitHubInstallation).filter(
                GitHubInstallation.installation_id == installation_id
            ).first()

            if existing:
                existing.is_active = False
                existing.uninstalled_at = datetime.utcnow()
                existing.updated_at = datetime.utcnow()
                logger.info(f"Deactivated installation {installation_id}")

        elif action == "suspend":
            existing = db.query(GitHubInstallation).filter(
                GitHubInstallation.installation_id == installation_id
            ).first()

            if existing:
                existing.suspended_at = datetime.utcnow()
                existing.suspended_by = sender.get("login")
                existing.updated_at = datetime.utcnow()
                logger.info(f"Suspended installation {installation_id}")

        elif action == "unsuspend":
            existing = db.query(GitHubInstallation).filter(
                GitHubInstallation.installation_id == installation_id
            ).first()

            if existing:
                existing.suspended_at = None
                existing.suspended_by = None
                existing.updated_at = datetime.utcnow()
                logger.info(f"Unsuspended installation {installation_id}")

        db.commit()

    except Exception as e:
        logger.error(f"Error processing installation: {e}", exc_info=True)
        db.rollback()
        raise
    finally:
        db.close()


# Helper functions

def _parse_github_timestamp(timestamp: Optional[str]) -> Optional[datetime]:
    """Parse GitHub ISO 8601 timestamp."""
    if not timestamp:
        return None
    try:
        # Remove 'Z' suffix and parse
        if timestamp.endswith("Z"):
            timestamp = timestamp[:-1] + "+00:00"
        return datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except Exception:
        return None


def _determine_runner_type(labels: list) -> str:
    """
    Determine runner type from job labels.

    Labels like ["ubuntu-latest", "self-hosted"] - we pick the most specific.
    """
    # Priority order for runner type detection
    runner_keywords = [
        "macos-latest-xlarge", "macos-latest-large",
        "macos-14", "macos-13", "macos-12", "macos-latest",
        "windows-2022", "windows-2019", "windows-latest",
        "ubuntu-latest-64-cores", "ubuntu-latest-32-cores",
        "ubuntu-latest-16-cores", "ubuntu-latest-8-cores",
        "ubuntu-latest-4-cores",
        "ubuntu-22.04-arm", "ubuntu-latest-arm",
        "ubuntu-22.04", "ubuntu-20.04", "ubuntu-latest",
    ]

    labels_lower = [l.lower() for l in labels]

    for runner in runner_keywords:
        if runner in labels_lower:
            return runner

    # Default to ubuntu-latest if self-hosted or unknown
    return "ubuntu-latest"


def _update_workflow_run_cost(db, org_id, run_id) -> None:
    """Update workflow run total cost from its jobs."""
    from sqlalchemy import func
    from app.models.job import Job
    from app.models.workflow_run import WorkflowRun

    try:
        # Sum all job costs for this run
        result = db.query(func.sum(Job.cost_usd)).filter(
            Job.org_id == org_id,
            Job.run_github_id == run_id,
        ).scalar()

        total_cost = result or Decimal("0")

        # Update workflow run
        workflow_run = db.query(WorkflowRun).filter(
            WorkflowRun.org_id == org_id,
            WorkflowRun.github_run_id == run_id,
        ).first()

        if workflow_run:
            workflow_run.cost_usd = total_cost
            logger.info(f"Updated workflow run {run_id} total cost: ${total_cost}")

    except Exception as e:
        logger.error(f"Error updating workflow run cost: {e}")
