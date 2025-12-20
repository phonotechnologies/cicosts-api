"""Dashboard API endpoints."""
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, desc
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, CurrentUser
from app.models.workflow_run import WorkflowRun
from app.models.job import Job

router = APIRouter()


# Response models

class CostPeriod(BaseModel):
    """Cost data for a period."""
    amount: float
    change: float  # Percentage change from previous period


class CostSummary(BaseModel):
    """Cost summary across periods."""
    today: CostPeriod
    week: CostPeriod
    month: CostPeriod


class DailyCost(BaseModel):
    """Daily cost data point."""
    date: str
    cost: float


class TopWorkflow(BaseModel):
    """Top workflow by cost."""
    name: str
    repo: str
    runs: int
    cost: float
    avg_duration: str


class RecentRun(BaseModel):
    """Recent workflow run."""
    id: str
    workflow: str
    repo: str
    status: str
    cost: float
    duration: str
    time: str


# Endpoints

@router.get("/summary", response_model=CostSummary)
async def get_cost_summary(
    org_id: UUID = Query(..., description="Organization ID"),
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get cost summary for today, this week, and this month.

    Includes percentage change from previous period.
    """
    now = datetime.utcnow()

    # Today
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday_start = today_start - timedelta(days=1)

    today_cost = _get_period_cost(db, org_id, today_start, now)
    yesterday_cost = _get_period_cost(db, org_id, yesterday_start, today_start)
    today_change = _calculate_change(today_cost, yesterday_cost)

    # This week
    week_start = today_start - timedelta(days=today_start.weekday())
    prev_week_start = week_start - timedelta(days=7)

    week_cost = _get_period_cost(db, org_id, week_start, now)
    prev_week_cost = _get_period_cost(db, org_id, prev_week_start, week_start)
    week_change = _calculate_change(week_cost, prev_week_cost)

    # This month
    month_start = today_start.replace(day=1)
    if month_start.month == 1:
        prev_month_start = month_start.replace(year=month_start.year - 1, month=12)
    else:
        prev_month_start = month_start.replace(month=month_start.month - 1)

    month_cost = _get_period_cost(db, org_id, month_start, now)
    prev_month_cost = _get_period_cost(db, org_id, prev_month_start, month_start)
    month_change = _calculate_change(month_cost, prev_month_cost)

    return CostSummary(
        today=CostPeriod(amount=float(today_cost), change=today_change),
        week=CostPeriod(amount=float(week_cost), change=week_change),
        month=CostPeriod(amount=float(month_cost), change=month_change),
    )


@router.get("/trends", response_model=List[DailyCost])
async def get_cost_trends(
    org_id: UUID = Query(..., description="Organization ID"),
    days: int = Query(30, ge=7, le=90, description="Number of days"),
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get daily cost data for the specified number of days.

    Used for the cost trend chart.
    """
    now = datetime.utcnow()
    start_date = now - timedelta(days=days)

    # Query daily costs
    results = db.query(
        func.date(WorkflowRun.completed_at).label("date"),
        func.sum(WorkflowRun.cost_usd).label("cost"),
    ).filter(
        WorkflowRun.org_id == org_id,
        WorkflowRun.completed_at >= start_date,
        WorkflowRun.completed_at <= now,
    ).group_by(
        func.date(WorkflowRun.completed_at)
    ).order_by(
        func.date(WorkflowRun.completed_at)
    ).all()

    # Build date -> cost map
    cost_map = {str(r.date): float(r.cost or 0) for r in results}

    # Fill in missing dates with 0
    daily_costs = []
    current = start_date.date()
    end = now.date()

    while current <= end:
        date_str = str(current)
        daily_costs.append(DailyCost(
            date=date_str,
            cost=cost_map.get(date_str, 0.0),
        ))
        current += timedelta(days=1)

    return daily_costs


@router.get("/top-workflows", response_model=List[TopWorkflow])
async def get_top_workflows(
    org_id: UUID = Query(..., description="Organization ID"),
    days: int = Query(30, ge=1, le=90, description="Number of days to look back"),
    limit: int = Query(5, ge=1, le=20, description="Number of workflows to return"),
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get top workflows by cost for the specified period.
    """
    now = datetime.utcnow()
    start_date = now - timedelta(days=days)

    # Query aggregated workflow data
    results = db.query(
        WorkflowRun.workflow_name,
        WorkflowRun.repo_name,
        func.count().label("runs"),
        func.sum(WorkflowRun.cost_usd).label("total_cost"),
        func.avg(WorkflowRun.billable_ms).label("avg_billable_ms"),
    ).filter(
        WorkflowRun.org_id == org_id,
        WorkflowRun.completed_at >= start_date,
    ).group_by(
        WorkflowRun.workflow_name,
        WorkflowRun.repo_name,
    ).order_by(
        desc("total_cost")
    ).limit(limit).all()

    workflows = []
    for r in results:
        # Format average duration
        avg_ms = int(r.avg_billable_ms or 0)
        avg_duration = _format_duration(avg_ms)

        # Extract repo name without org prefix
        repo = r.repo_name.split("/")[-1] if "/" in r.repo_name else r.repo_name

        workflows.append(TopWorkflow(
            name=r.workflow_name or "Unknown",
            repo=repo,
            runs=r.runs or 0,
            cost=float(r.total_cost or 0),
            avg_duration=avg_duration,
        ))

    return workflows


@router.get("/recent-runs", response_model=List[RecentRun])
async def get_recent_runs(
    org_id: UUID = Query(..., description="Organization ID"),
    limit: int = Query(10, ge=1, le=50, description="Number of runs to return"),
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get the most recent workflow runs.
    """
    now = datetime.utcnow()

    results = db.query(WorkflowRun).filter(
        WorkflowRun.org_id == org_id,
    ).order_by(
        desc(WorkflowRun.created_at)
    ).limit(limit).all()

    runs = []
    for r in results:
        # Calculate duration
        if r.completed_at and r.created_at:
            duration_ms = int((r.completed_at - r.created_at).total_seconds() * 1000)
        else:
            duration_ms = r.billable_ms or 0

        duration = _format_duration(duration_ms)

        # Format relative time
        time_ago = _format_time_ago(r.created_at, now)

        # Extract repo name
        repo = r.repo_name.split("/")[-1] if "/" in r.repo_name else r.repo_name

        # Determine status
        if r.status == "completed":
            status = r.conclusion or "success"
        elif r.status == "in_progress":
            status = "running"
        else:
            status = r.status

        runs.append(RecentRun(
            id=str(r.github_run_id),
            workflow=r.workflow_name or "Unknown",
            repo=repo,
            status=status,
            cost=float(r.cost_usd or 0),
            duration=duration,
            time=time_ago,
        ))

    return runs


# Helper functions

def _get_period_cost(db: Session, org_id: UUID, start: datetime, end: datetime) -> Decimal:
    """Get total cost for a period."""
    result = db.query(func.sum(WorkflowRun.cost_usd)).filter(
        WorkflowRun.org_id == org_id,
        WorkflowRun.completed_at >= start,
        WorkflowRun.completed_at < end,
    ).scalar()
    return result or Decimal("0")


def _calculate_change(current: Decimal, previous: Decimal) -> float:
    """Calculate percentage change."""
    if previous == 0:
        return 0.0 if current == 0 else 100.0
    change = ((current - previous) / previous) * 100
    return round(float(change), 1)


def _format_duration(ms: int) -> str:
    """Format milliseconds as human-readable duration."""
    if ms <= 0:
        return "0s"

    seconds = ms // 1000
    minutes = seconds // 60
    hours = minutes // 60

    if hours > 0:
        return f"{hours}h {minutes % 60}m"
    elif minutes > 0:
        return f"{minutes}m {seconds % 60}s"
    else:
        return f"{seconds}s"


def _format_time_ago(dt: datetime, now: datetime) -> str:
    """Format datetime as relative time string."""
    if not dt:
        return "unknown"

    diff = now - dt
    seconds = int(diff.total_seconds())

    if seconds < 60:
        return f"{seconds} sec ago"
    elif seconds < 3600:
        minutes = seconds // 60
        return f"{minutes} min ago"
    elif seconds < 86400:
        hours = seconds // 3600
        return f"{hours}h ago"
    else:
        days = seconds // 86400
        return f"{days}d ago"
