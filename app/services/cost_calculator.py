"""
Cost calculation service.

Reference: spec-cost-calculation.md § 2.1
"""
from decimal import Decimal
from typing import Optional

# GitHub Actions runner pricing (per minute)
# Reference: spec-cost-calculation.md § 2.1
RUNNER_PRICING = {
    # Linux runners
    "ubuntu-latest": Decimal("0.008"),
    "ubuntu-22.04": Decimal("0.008"),
    "ubuntu-20.04": Decimal("0.008"),

    # Linux larger runners
    "ubuntu-latest-4-cores": Decimal("0.016"),
    "ubuntu-latest-8-cores": Decimal("0.032"),
    "ubuntu-latest-16-cores": Decimal("0.064"),
    "ubuntu-latest-32-cores": Decimal("0.128"),
    "ubuntu-latest-64-cores": Decimal("0.256"),

    # Windows runners (2x Linux)
    "windows-latest": Decimal("0.016"),
    "windows-2022": Decimal("0.016"),
    "windows-2019": Decimal("0.016"),

    # Windows larger runners
    "windows-latest-4-cores": Decimal("0.032"),
    "windows-latest-8-cores": Decimal("0.064"),

    # macOS runners (10x Linux)
    "macos-latest": Decimal("0.08"),
    "macos-14": Decimal("0.08"),
    "macos-13": Decimal("0.08"),
    "macos-12": Decimal("0.08"),

    # macOS larger runners
    "macos-latest-large": Decimal("0.12"),
    "macos-latest-xlarge": Decimal("0.16"),

    # ARM runners (Linux)
    "ubuntu-latest-arm": Decimal("0.005"),
    "ubuntu-22.04-arm": Decimal("0.005"),
}

# Default pricing if runner type unknown
DEFAULT_PRICE_PER_MINUTE = Decimal("0.008")


def calculate_job_cost(
    runner_type: str,
    billable_ms: int,
) -> Decimal:
    """
    Calculate cost for a single job.

    Args:
        runner_type: GitHub runner label (e.g., "ubuntu-latest")
        billable_ms: Billable time in milliseconds

    Returns:
        Cost in USD with 4 decimal precision
    """
    # Get price per minute
    price_per_minute = RUNNER_PRICING.get(
        runner_type.lower(),
        DEFAULT_PRICE_PER_MINUTE,
    )

    # Convert ms to minutes (round up)
    billable_minutes = Decimal(billable_ms) / Decimal(60000)

    # Calculate cost
    cost = billable_minutes * price_per_minute

    # Round to 4 decimal places
    return cost.quantize(Decimal("0.0001"))


def calculate_workflow_cost(jobs: list[dict]) -> Decimal:
    """
    Calculate total cost for a workflow run.

    Args:
        jobs: List of job dicts with runner_type and billable_ms

    Returns:
        Total cost in USD
    """
    total = Decimal("0")

    for job in jobs:
        cost = calculate_job_cost(
            runner_type=job.get("runner_type", "ubuntu-latest"),
            billable_ms=job.get("billable_ms", 0),
        )
        total += cost

    return total.quantize(Decimal("0.0001"))


def get_runner_price(runner_type: str) -> Decimal:
    """Get price per minute for a runner type."""
    return RUNNER_PRICING.get(
        runner_type.lower(),
        DEFAULT_PRICE_PER_MINUTE,
    )
