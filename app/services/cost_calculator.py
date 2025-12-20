"""
Cost calculation service.

Reference: spec-cost-calculation.md § 2.1
"""
import math
from decimal import Decimal, ROUND_UP
from typing import Optional


# GitHub Actions runner pricing (per minute)
# Reference: https://docs.github.com/en/billing/managing-billing-for-github-actions/about-billing-for-github-actions
RUNNER_PRICING = {
    # Linux runners (2-core default)
    "ubuntu-latest": Decimal("0.008"),
    "ubuntu-22.04": Decimal("0.008"),
    "ubuntu-20.04": Decimal("0.008"),
    "ubuntu-18.04": Decimal("0.008"),

    # Linux larger runners - explicit core counts
    "ubuntu-latest-2-cores": Decimal("0.008"),
    "ubuntu-latest-4-cores": Decimal("0.016"),
    "ubuntu-latest-8-cores": Decimal("0.032"),
    "ubuntu-latest-16-cores": Decimal("0.064"),
    "ubuntu-latest-32-cores": Decimal("0.128"),
    "ubuntu-latest-64-cores": Decimal("0.256"),

    # Linux versioned larger runners
    "ubuntu-22.04-2-cores": Decimal("0.008"),
    "ubuntu-22.04-4-cores": Decimal("0.016"),
    "ubuntu-22.04-8-cores": Decimal("0.032"),
    "ubuntu-22.04-16-cores": Decimal("0.064"),
    "ubuntu-22.04-32-cores": Decimal("0.128"),
    "ubuntu-22.04-64-cores": Decimal("0.256"),

    # Windows runners (2x Linux pricing)
    "windows-latest": Decimal("0.016"),
    "windows-2022": Decimal("0.016"),
    "windows-2019": Decimal("0.016"),

    # Windows larger runners
    "windows-latest-4-cores": Decimal("0.032"),
    "windows-latest-8-cores": Decimal("0.064"),
    "windows-latest-16-cores": Decimal("0.128"),
    "windows-2022-4-cores": Decimal("0.032"),
    "windows-2022-8-cores": Decimal("0.064"),
    "windows-2022-16-cores": Decimal("0.128"),

    # macOS runners (10x Linux pricing)
    "macos-latest": Decimal("0.08"),
    "macos-14": Decimal("0.08"),  # M1, 3-core
    "macos-13": Decimal("0.08"),  # Intel
    "macos-12": Decimal("0.08"),  # Intel
    "macos-11": Decimal("0.08"),  # Intel

    # macOS M1 runners with explicit core counts
    "macos-latest-3-cores": Decimal("0.08"),   # M1 standard
    "macos-14-3-cores": Decimal("0.08"),       # M1 standard

    # macOS larger runners
    "macos-latest-large": Decimal("0.12"),      # M1, 12-core
    "macos-latest-12-cores": Decimal("0.12"),   # M1 large
    "macos-14-large": Decimal("0.12"),          # M1 large
    "macos-14-12-cores": Decimal("0.12"),       # M1 large
    "macos-latest-xlarge": Decimal("0.16"),     # M1, xlarge

    # ARM runners (Linux on ARM)
    "ubuntu-latest-arm": Decimal("0.005"),
    "ubuntu-22.04-arm": Decimal("0.005"),
}

# Default pricing if runner type unknown (use Linux 2-core as fallback)
DEFAULT_PRICE_PER_MINUTE = Decimal("0.008")


class CostCalculationError(Exception):
    """Raised when cost calculation fails."""
    pass


def calculate_job_cost(
    runner_type: str,
    billable_ms: int,
) -> Decimal:
    """
    Calculate cost for a single job.

    GitHub Actions billing behavior:
    - Rounds up to the nearest minute
    - Charges per minute based on runner type

    Args:
        runner_type: GitHub runner label (e.g., "ubuntu-latest", "ubuntu-latest-16-cores")
        billable_ms: Billable time in milliseconds

    Returns:
        Cost in USD with 4 decimal precision

    Raises:
        CostCalculationError: If inputs are invalid

    Examples:
        >>> calculate_job_cost("ubuntu-latest", 30000)  # 30 seconds
        Decimal('0.0080')  # Rounded up to 1 minute

        >>> calculate_job_cost("ubuntu-latest-16-cores", 90000)  # 90 seconds
        Decimal('0.1280')  # Rounded up to 2 minutes * $0.064/min

        >>> calculate_job_cost("macos-latest", 1000)  # 1 second
        Decimal('0.0800')  # Rounded up to 1 minute
    """
    # Input validation
    if not isinstance(runner_type, str) or not runner_type.strip():
        raise CostCalculationError("runner_type must be a non-empty string")

    if not isinstance(billable_ms, int):
        raise CostCalculationError("billable_ms must be an integer")

    if billable_ms < 0:
        raise CostCalculationError("billable_ms cannot be negative")

    # Handle zero billable time
    if billable_ms == 0:
        return Decimal("0.0000")

    # Normalize runner type to lowercase for lookup
    runner_key = runner_type.lower().strip()

    # Get price per minute for this runner type
    price_per_minute = RUNNER_PRICING.get(
        runner_key,
        DEFAULT_PRICE_PER_MINUTE,
    )

    # Convert milliseconds to minutes, rounding UP to nearest minute
    # This matches GitHub's billing behavior
    billable_minutes = math.ceil(billable_ms / 60000)

    # Calculate total cost
    cost = Decimal(billable_minutes) * price_per_minute

    # Return with 4 decimal places precision
    return cost.quantize(Decimal("0.0001"), rounding=ROUND_UP)


def calculate_workflow_cost(jobs: list[dict]) -> Decimal:
    """
    Calculate total cost for a workflow run.

    Args:
        jobs: List of job dicts with runner_type and billable_ms keys

    Returns:
        Total cost in USD with 4 decimal precision

    Raises:
        CostCalculationError: If job data is invalid

    Examples:
        >>> jobs = [
        ...     {"runner_type": "ubuntu-latest", "billable_ms": 30000},
        ...     {"runner_type": "macos-latest", "billable_ms": 45000},
        ... ]
        >>> calculate_workflow_cost(jobs)
        Decimal('0.0880')  # $0.008 + $0.080
    """
    if not isinstance(jobs, list):
        raise CostCalculationError("jobs must be a list")

    total = Decimal("0")

    for idx, job in enumerate(jobs):
        if not isinstance(job, dict):
            raise CostCalculationError(f"Job at index {idx} must be a dict")

        try:
            runner_type = job.get("runner_type", "ubuntu-latest")
            billable_ms = job.get("billable_ms", 0)

            cost = calculate_job_cost(
                runner_type=runner_type,
                billable_ms=billable_ms,
            )
            total += cost

        except (KeyError, TypeError, ValueError) as e:
            raise CostCalculationError(
                f"Invalid job data at index {idx}: {str(e)}"
            ) from e

    return total.quantize(Decimal("0.0001"), rounding=ROUND_UP)


def get_runner_price(runner_type: str) -> Decimal:
    """
    Get price per minute for a runner type.

    Args:
        runner_type: GitHub runner label

    Returns:
        Price per minute in USD

    Raises:
        CostCalculationError: If runner_type is invalid

    Examples:
        >>> get_runner_price("ubuntu-latest")
        Decimal('0.008')

        >>> get_runner_price("macos-latest-large")
        Decimal('0.12')
    """
    if not isinstance(runner_type, str) or not runner_type.strip():
        raise CostCalculationError("runner_type must be a non-empty string")

    return RUNNER_PRICING.get(
        runner_type.lower().strip(),
        DEFAULT_PRICE_PER_MINUTE,
    )


def estimate_monthly_cost(
    daily_runs: int,
    avg_duration_ms: int,
    runner_type: str = "ubuntu-latest",
    days_per_month: int = 30,
) -> Decimal:
    """
    Estimate monthly cost based on usage patterns.

    Args:
        daily_runs: Average number of workflow runs per day
        avg_duration_ms: Average duration per run in milliseconds
        runner_type: GitHub runner type
        days_per_month: Number of days to calculate for

    Returns:
        Estimated monthly cost in USD

    Raises:
        CostCalculationError: If inputs are invalid
    """
    if daily_runs < 0 or avg_duration_ms < 0 or days_per_month < 0:
        raise CostCalculationError("All parameters must be non-negative")

    # Calculate cost per run
    cost_per_run = calculate_job_cost(runner_type, avg_duration_ms)

    # Calculate total monthly cost
    monthly_cost = cost_per_run * Decimal(daily_runs) * Decimal(days_per_month)

    return monthly_cost.quantize(Decimal("0.0001"), rounding=ROUND_UP)
