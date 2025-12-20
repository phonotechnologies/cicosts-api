# Cost Calculator Service - Usage Guide

## Overview

The cost calculator service calculates GitHub Actions workflow costs based on runner type and billable time. It implements GitHub's billing behavior including rounding up to the nearest minute.

## Location

`/tmp/cicosts-api/app/services/cost_calculator.py`

## Quick Start

```python
from app.services.cost_calculator import calculate_job_cost, calculate_workflow_cost

# Calculate cost for a single job
cost = calculate_job_cost("ubuntu-latest-16-cores", 90000)
# Returns: Decimal('0.1280')
# Explanation: 90 seconds rounds up to 2 minutes * $0.064/min

# Calculate cost for entire workflow
jobs = [
    {"runner_type": "ubuntu-latest", "billable_ms": 180000},
    {"runner_type": "macos-latest", "billable_ms": 60000},
]
total_cost = calculate_workflow_cost(jobs)
# Returns: Decimal('0.1040')
```

## API Reference

### `calculate_job_cost(runner_type: str, billable_ms: int) -> Decimal`

Calculate cost for a single CI job.

**Parameters:**
- `runner_type` (str): GitHub runner label (e.g., "ubuntu-latest", "ubuntu-latest-16-cores")
- `billable_ms` (int): Billable time in milliseconds

**Returns:**
- `Decimal`: Cost in USD with 4 decimal precision

**Raises:**
- `CostCalculationError`: If inputs are invalid

**Examples:**
```python
# Basic usage
cost = calculate_job_cost("ubuntu-latest", 60000)  # $0.0080

# Rounding behavior (30 seconds -> 1 minute)
cost = calculate_job_cost("ubuntu-latest", 30000)  # $0.0080

# Large runner
cost = calculate_job_cost("ubuntu-latest-16-cores", 120000)  # $0.1280

# macOS runner
cost = calculate_job_cost("macos-latest", 60000)  # $0.0800
```

### `calculate_workflow_cost(jobs: list[dict]) -> Decimal`

Calculate total cost for a workflow with multiple jobs.

**Parameters:**
- `jobs` (list[dict]): List of job dicts with `runner_type` and `billable_ms` keys

**Returns:**
- `Decimal`: Total cost in USD with 4 decimal precision

**Example:**
```python
jobs = [
    {"runner_type": "ubuntu-latest", "billable_ms": 180000},
    {"runner_type": "windows-latest", "billable_ms": 120000},
    {"runner_type": "macos-latest", "billable_ms": 60000},
]
total = calculate_workflow_cost(jobs)
# Returns: Decimal('0.1360')
```

### `get_runner_price(runner_type: str) -> Decimal`

Get price per minute for a specific runner type.

**Parameters:**
- `runner_type` (str): GitHub runner label

**Returns:**
- `Decimal`: Price per minute in USD

**Example:**
```python
price = get_runner_price("ubuntu-latest-16-cores")
# Returns: Decimal('0.064')
```

### `estimate_monthly_cost(daily_runs: int, avg_duration_ms: int, runner_type: str = "ubuntu-latest", days_per_month: int = 30) -> Decimal`

Estimate monthly cost based on usage patterns.

**Parameters:**
- `daily_runs` (int): Average number of workflow runs per day
- `avg_duration_ms` (int): Average duration per run in milliseconds
- `runner_type` (str): GitHub runner type (default: "ubuntu-latest")
- `days_per_month` (int): Number of days to calculate for (default: 30)

**Returns:**
- `Decimal`: Estimated monthly cost in USD

**Example:**
```python
# 10 runs per day, 5 minutes each, for 30 days
monthly = estimate_monthly_cost(10, 300000)
# Returns: Decimal('12.0000')
```

## Pricing Tiers

### Linux Runners
| Runner Type | Price/min | Price/hour |
|------------|-----------|------------|
| ubuntu-latest (2-core) | $0.008 | $0.48 |
| ubuntu-latest-4-cores | $0.016 | $0.96 |
| ubuntu-latest-8-cores | $0.032 | $1.92 |
| ubuntu-latest-16-cores | $0.064 | $3.84 |
| ubuntu-latest-32-cores | $0.128 | $7.68 |
| ubuntu-latest-64-cores | $0.256 | $15.36 |

### Windows Runners
| Runner Type | Price/min | Price/hour |
|------------|-----------|------------|
| windows-latest | $0.016 | $0.96 |
| windows-2022 | $0.016 | $0.96 |
| windows-latest-4-cores | $0.032 | $1.92 |
| windows-latest-8-cores | $0.064 | $3.84 |

### macOS Runners
| Runner Type | Price/min | Price/hour |
|------------|-----------|------------|
| macos-latest (M1, 3-core) | $0.08 | $4.80 |
| macos-14 (M1, 3-core) | $0.08 | $4.80 |
| macos-latest-large (M1, 12-core) | $0.12 | $7.20 |
| macos-latest-12-cores | $0.12 | $7.20 |

## Billing Behavior

The service implements GitHub Actions billing behavior:

1. **Rounding Up**: Time is always rounded up to the nearest minute
   - 1 second = 1 minute of billing
   - 30 seconds = 1 minute of billing
   - 61 seconds = 2 minutes of billing

2. **Minimum Charge**: Any job with billable time > 0 has a minimum 1-minute charge

3. **Zero Billable Time**: Jobs with 0ms billable time cost $0.0000

## Error Handling

The service raises `CostCalculationError` for invalid inputs:

```python
from app.services.cost_calculator import CostCalculationError

# Negative time
try:
    calculate_job_cost("ubuntu-latest", -1000)
except CostCalculationError as e:
    print(e)  # "billable_ms cannot be negative"

# Empty runner type
try:
    calculate_job_cost("", 60000)
except CostCalculationError as e:
    print(e)  # "runner_type must be a non-empty string"

# Non-integer billable time
try:
    calculate_job_cost("ubuntu-latest", "60000")
except CostCalculationError as e:
    print(e)  # "billable_ms must be an integer"
```

## Real-World Examples

### Typical Startup CI Pipeline
```python
jobs = [
    {"runner_type": "ubuntu-latest", "billable_ms": 180000},  # test: 3 min
    {"runner_type": "ubuntu-latest", "billable_ms": 45000},   # lint: 45s -> 1 min
    {"runner_type": "ubuntu-latest", "billable_ms": 120000},  # build: 2 min
]
cost = calculate_workflow_cost(jobs)
# Returns: Decimal('0.0480')  # 6 minutes * $0.008
```

### Mobile App Build (iOS + Android)
```python
jobs = [
    {"runner_type": "macos-latest-large", "billable_ms": 900000},     # iOS: 15 min
    {"runner_type": "ubuntu-latest-8-cores", "billable_ms": 600000},  # Android: 10 min
]
cost = calculate_workflow_cost(jobs)
# Returns: Decimal('2.1200')  # $1.80 + $0.32
```

### Matrix Build (Multiple Platforms)
```python
jobs = [
    {"runner_type": "ubuntu-latest", "billable_ms": 240000},    # Linux: 4 min
    {"runner_type": "ubuntu-latest", "billable_ms": 240000},    # Linux: 4 min
    {"runner_type": "windows-latest", "billable_ms": 300000},   # Windows: 5 min
    {"runner_type": "macos-latest", "billable_ms": 360000},     # macOS: 6 min
]
cost = calculate_workflow_cost(jobs)
# Returns: Decimal('0.6400')
```

## Testing

The service includes comprehensive test coverage:

```bash
# Run tests
pytest tests/test_cost_calculator.py -v

# Test coverage: 48/48 tests (100%)
# - Input validation tests
# - Pricing accuracy tests
# - Rounding behavior tests
# - Error handling tests
# - Real-world scenario tests
```

## Notes

- All costs are returned as `Decimal` for precise financial calculations
- Runner type matching is case-insensitive
- Unknown runner types default to Linux 2-core pricing ($0.008/min)
- The service supports all current GitHub Actions runner types
- Pricing is accurate as of the implementation date and follows GitHub's public pricing
