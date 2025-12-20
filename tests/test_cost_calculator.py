"""
Tests for cost calculation service.
"""
import pytest
from decimal import Decimal

from app.services.cost_calculator import (
    calculate_job_cost,
    calculate_workflow_cost,
    get_runner_price,
    estimate_monthly_cost,
    CostCalculationError,
    RUNNER_PRICING,
)


class TestCalculateJobCost:
    """Test cases for calculate_job_cost function."""

    def test_ubuntu_latest_basic(self):
        """Test basic Linux runner cost calculation."""
        # 1 minute exactly
        cost = calculate_job_cost("ubuntu-latest", 60000)
        assert cost == Decimal("0.0080")

        # 2 minutes exactly
        cost = calculate_job_cost("ubuntu-latest", 120000)
        assert cost == Decimal("0.0160")

    def test_round_up_to_nearest_minute(self):
        """Test that billing rounds up to nearest minute (GitHub behavior)."""
        # 30 seconds should round up to 1 minute
        cost = calculate_job_cost("ubuntu-latest", 30000)
        assert cost == Decimal("0.0080")

        # 1 second should round up to 1 minute
        cost = calculate_job_cost("ubuntu-latest", 1000)
        assert cost == Decimal("0.0080")

        # 61 seconds should round up to 2 minutes
        cost = calculate_job_cost("ubuntu-latest", 61000)
        assert cost == Decimal("0.0160")

        # 90 seconds should round up to 2 minutes
        cost = calculate_job_cost("ubuntu-latest", 90000)
        assert cost == Decimal("0.0160")

    def test_linux_16_core_runner(self):
        """Test Linux 16-core runner pricing."""
        # 1 minute
        cost = calculate_job_cost("ubuntu-latest-16-cores", 60000)
        assert cost == Decimal("0.0640")

        # 30 seconds rounds to 1 minute
        cost = calculate_job_cost("ubuntu-latest-16-cores", 30000)
        assert cost == Decimal("0.0640")

        # 90 seconds rounds to 2 minutes
        cost = calculate_job_cost("ubuntu-latest-16-cores", 90000)
        assert cost == Decimal("0.1280")

    def test_windows_runner(self):
        """Test Windows runner pricing (2x Linux)."""
        cost = calculate_job_cost("windows-latest", 60000)
        assert cost == Decimal("0.0160")

        cost = calculate_job_cost("windows-2022", 60000)
        assert cost == Decimal("0.0160")

    def test_macos_runner(self):
        """Test macOS runner pricing (10x Linux)."""
        # macOS M1 3-core
        cost = calculate_job_cost("macos-latest", 60000)
        assert cost == Decimal("0.0800")

        cost = calculate_job_cost("macos-14", 60000)
        assert cost == Decimal("0.0800")

    def test_macos_large_runner(self):
        """Test macOS large runner (12-core M1)."""
        cost = calculate_job_cost("macos-latest-large", 60000)
        assert cost == Decimal("0.1200")

        cost = calculate_job_cost("macos-latest-12-cores", 60000)
        assert cost == Decimal("0.1200")

    def test_linux_all_core_sizes(self):
        """Test all Linux core sizes match requirements."""
        test_cases = [
            ("ubuntu-latest-2-cores", Decimal("0.008")),
            ("ubuntu-latest-4-cores", Decimal("0.016")),
            ("ubuntu-latest-8-cores", Decimal("0.032")),
            ("ubuntu-latest-16-cores", Decimal("0.064")),
            ("ubuntu-latest-32-cores", Decimal("0.128")),
            ("ubuntu-latest-64-cores", Decimal("0.256")),
        ]

        for runner_type, expected_rate in test_cases:
            cost = calculate_job_cost(runner_type, 60000)
            expected_cost = expected_rate
            assert cost == expected_cost, f"{runner_type} should cost {expected_cost} per minute"

    def test_case_insensitive_runner_type(self):
        """Test that runner type matching is case-insensitive."""
        cost1 = calculate_job_cost("ubuntu-latest", 60000)
        cost2 = calculate_job_cost("Ubuntu-Latest", 60000)
        cost3 = calculate_job_cost("UBUNTU-LATEST", 60000)

        assert cost1 == cost2 == cost3 == Decimal("0.0080")

    def test_whitespace_handling(self):
        """Test that whitespace in runner type is handled."""
        cost = calculate_job_cost("  ubuntu-latest  ", 60000)
        assert cost == Decimal("0.0080")

    def test_unknown_runner_uses_default(self):
        """Test that unknown runner types use default pricing."""
        cost = calculate_job_cost("unknown-runner", 60000)
        assert cost == Decimal("0.0080")  # Default Linux 2-core pricing

    def test_zero_billable_time(self):
        """Test handling of zero billable time."""
        cost = calculate_job_cost("ubuntu-latest", 0)
        assert cost == Decimal("0.0000")

    def test_four_decimal_precision(self):
        """Test that all costs have exactly 4 decimal places."""
        cost = calculate_job_cost("ubuntu-latest", 60000)
        assert len(str(cost).split('.')[-1]) == 4

    def test_negative_billable_time_raises_error(self):
        """Test that negative billable time raises error."""
        with pytest.raises(CostCalculationError, match="cannot be negative"):
            calculate_job_cost("ubuntu-latest", -1000)

    def test_invalid_runner_type_raises_error(self):
        """Test that invalid runner type raises error."""
        with pytest.raises(CostCalculationError, match="non-empty string"):
            calculate_job_cost("", 60000)

        with pytest.raises(CostCalculationError, match="non-empty string"):
            calculate_job_cost("   ", 60000)

    def test_invalid_billable_ms_type_raises_error(self):
        """Test that non-integer billable_ms raises error."""
        with pytest.raises(CostCalculationError, match="must be an integer"):
            calculate_job_cost("ubuntu-latest", 60.5)

        with pytest.raises(CostCalculationError, match="must be an integer"):
            calculate_job_cost("ubuntu-latest", "60000")


class TestCalculateWorkflowCost:
    """Test cases for calculate_workflow_cost function."""

    def test_single_job_workflow(self):
        """Test workflow with single job."""
        jobs = [
            {"runner_type": "ubuntu-latest", "billable_ms": 60000},
        ]
        cost = calculate_workflow_cost(jobs)
        assert cost == Decimal("0.0080")

    def test_multiple_jobs_same_runner(self):
        """Test workflow with multiple jobs on same runner type."""
        jobs = [
            {"runner_type": "ubuntu-latest", "billable_ms": 60000},
            {"runner_type": "ubuntu-latest", "billable_ms": 60000},
            {"runner_type": "ubuntu-latest", "billable_ms": 60000},
        ]
        cost = calculate_workflow_cost(jobs)
        assert cost == Decimal("0.0240")  # 3 * $0.008

    def test_multiple_jobs_different_runners(self):
        """Test workflow with different runner types."""
        jobs = [
            {"runner_type": "ubuntu-latest", "billable_ms": 60000},      # $0.008
            {"runner_type": "windows-latest", "billable_ms": 60000},     # $0.016
            {"runner_type": "macos-latest", "billable_ms": 60000},       # $0.080
        ]
        cost = calculate_workflow_cost(jobs)
        assert cost == Decimal("0.1040")  # $0.008 + $0.016 + $0.080

    def test_mixed_durations_with_rounding(self):
        """Test workflow with different durations requiring rounding."""
        jobs = [
            {"runner_type": "ubuntu-latest", "billable_ms": 30000},      # 30s -> 1min -> $0.008
            {"runner_type": "ubuntu-latest-16-cores", "billable_ms": 90000},  # 90s -> 2min -> $0.128
        ]
        cost = calculate_workflow_cost(jobs)
        assert cost == Decimal("0.1360")  # $0.008 + $0.128

    def test_empty_jobs_list(self):
        """Test workflow with no jobs."""
        jobs = []
        cost = calculate_workflow_cost(jobs)
        assert cost == Decimal("0.0000")

    def test_jobs_with_defaults(self):
        """Test that missing keys use defaults."""
        jobs = [
            {},  # Should use defaults: ubuntu-latest, 0ms
            {"runner_type": "macos-latest"},  # Should use 0ms
            {"billable_ms": 60000},  # Should use ubuntu-latest
        ]
        cost = calculate_workflow_cost(jobs)
        assert cost == Decimal("0.0080")  # Only last job costs money

    def test_invalid_jobs_parameter_raises_error(self):
        """Test that non-list jobs parameter raises error."""
        with pytest.raises(CostCalculationError, match="must be a list"):
            calculate_workflow_cost("not a list")

        with pytest.raises(CostCalculationError, match="must be a list"):
            calculate_workflow_cost(None)

    def test_invalid_job_in_list_raises_error(self):
        """Test that non-dict job raises error."""
        jobs = [
            {"runner_type": "ubuntu-latest", "billable_ms": 60000},
            "invalid job",
        ]
        with pytest.raises(CostCalculationError, match="must be a dict"):
            calculate_workflow_cost(jobs)


class TestGetRunnerPrice:
    """Test cases for get_runner_price function."""

    def test_all_defined_runners_have_price(self):
        """Test that all defined runners return a price."""
        for runner_type in RUNNER_PRICING.keys():
            price = get_runner_price(runner_type)
            assert isinstance(price, Decimal)
            assert price > 0

    def test_ubuntu_latest_price(self):
        """Test specific runner price lookup."""
        price = get_runner_price("ubuntu-latest")
        assert price == Decimal("0.008")

    def test_macos_large_price(self):
        """Test macOS large runner price."""
        price = get_runner_price("macos-latest-large")
        assert price == Decimal("0.12")

    def test_case_insensitive_lookup(self):
        """Test case-insensitive price lookup."""
        price1 = get_runner_price("ubuntu-latest")
        price2 = get_runner_price("UBUNTU-LATEST")
        assert price1 == price2

    def test_unknown_runner_returns_default(self):
        """Test unknown runner returns default price."""
        price = get_runner_price("unknown-runner-99")
        assert price == Decimal("0.008")

    def test_invalid_runner_type_raises_error(self):
        """Test invalid runner type raises error."""
        with pytest.raises(CostCalculationError):
            get_runner_price("")

        with pytest.raises(CostCalculationError):
            get_runner_price(None)


class TestEstimateMonthlyCost:
    """Test cases for estimate_monthly_cost function."""

    def test_basic_monthly_estimate(self):
        """Test basic monthly cost estimation."""
        # 10 runs per day, 5 minutes each, 30 days
        cost = estimate_monthly_cost(
            daily_runs=10,
            avg_duration_ms=300000,  # 5 minutes
            runner_type="ubuntu-latest",
            days_per_month=30
        )
        # 10 * 5min * $0.008/min * 30 days = $12.00
        assert cost == Decimal("12.0000")

    def test_expensive_runner_monthly_cost(self):
        """Test monthly estimate with expensive runner."""
        # 5 runs per day, 10 minutes each, macOS
        cost = estimate_monthly_cost(
            daily_runs=5,
            avg_duration_ms=600000,  # 10 minutes
            runner_type="macos-latest",
            days_per_month=30
        )
        # 5 * 10min * $0.08/min * 30 days = $120.00
        assert cost == Decimal("120.0000")

    def test_with_rounding_up(self):
        """Test monthly estimate includes rounding up."""
        # 1 run per day, 30 seconds (rounds to 1 min)
        cost = estimate_monthly_cost(
            daily_runs=1,
            avg_duration_ms=30000,  # 30 seconds
            runner_type="ubuntu-latest",
            days_per_month=30
        )
        # 1 * 1min * $0.008/min * 30 days = $0.24
        assert cost == Decimal("0.2400")

    def test_zero_runs(self):
        """Test estimate with zero runs."""
        cost = estimate_monthly_cost(
            daily_runs=0,
            avg_duration_ms=60000,
            runner_type="ubuntu-latest",
        )
        assert cost == Decimal("0.0000")

    def test_negative_values_raise_error(self):
        """Test that negative values raise error."""
        with pytest.raises(CostCalculationError, match="non-negative"):
            estimate_monthly_cost(daily_runs=-1, avg_duration_ms=60000)

        with pytest.raises(CostCalculationError, match="non-negative"):
            estimate_monthly_cost(daily_runs=10, avg_duration_ms=-1000)

        with pytest.raises(CostCalculationError, match="non-negative"):
            estimate_monthly_cost(daily_runs=10, avg_duration_ms=60000, days_per_month=-1)


class TestRunnerPricingTable:
    """Test that pricing table matches requirements."""

    def test_linux_2core_pricing(self):
        """Test Linux 2-core runners cost $0.008/min."""
        assert RUNNER_PRICING["ubuntu-latest"] == Decimal("0.008")
        assert RUNNER_PRICING["ubuntu-22.04"] == Decimal("0.008")
        assert RUNNER_PRICING["ubuntu-20.04"] == Decimal("0.008")

    def test_linux_4core_pricing(self):
        """Test Linux 4-core runners cost $0.016/min."""
        assert RUNNER_PRICING["ubuntu-latest-4-cores"] == Decimal("0.016")

    def test_linux_8core_pricing(self):
        """Test Linux 8-core runners cost $0.032/min."""
        assert RUNNER_PRICING["ubuntu-latest-8-cores"] == Decimal("0.032")

    def test_linux_16core_pricing(self):
        """Test Linux 16-core runners cost $0.064/min."""
        assert RUNNER_PRICING["ubuntu-latest-16-cores"] == Decimal("0.064")

    def test_linux_32core_pricing(self):
        """Test Linux 32-core runners cost $0.128/min."""
        assert RUNNER_PRICING["ubuntu-latest-32-cores"] == Decimal("0.128")

    def test_linux_64core_pricing(self):
        """Test Linux 64-core runners cost $0.256/min."""
        assert RUNNER_PRICING["ubuntu-latest-64-cores"] == Decimal("0.256")

    def test_windows_pricing(self):
        """Test Windows runners cost $0.016/min (2x Linux)."""
        assert RUNNER_PRICING["windows-latest"] == Decimal("0.016")
        assert RUNNER_PRICING["windows-2022"] == Decimal("0.016")
        assert RUNNER_PRICING["windows-2019"] == Decimal("0.016")

    def test_macos_3core_pricing(self):
        """Test macOS 3-core (M1) runners cost $0.08/min."""
        assert RUNNER_PRICING["macos-latest"] == Decimal("0.08")
        assert RUNNER_PRICING["macos-14"] == Decimal("0.08")

    def test_macos_12core_pricing(self):
        """Test macOS 12-core (M1 Large) runners cost $0.12/min."""
        assert RUNNER_PRICING["macos-latest-large"] == Decimal("0.12")
        assert RUNNER_PRICING["macos-latest-12-cores"] == Decimal("0.12")

    def test_pricing_proportional_scaling(self):
        """Test that larger runners scale proportionally."""
        base_price = RUNNER_PRICING["ubuntu-latest-2-cores"]

        # Each doubling of cores should double the price
        assert RUNNER_PRICING["ubuntu-latest-4-cores"] == base_price * 2
        assert RUNNER_PRICING["ubuntu-latest-8-cores"] == base_price * 4
        assert RUNNER_PRICING["ubuntu-latest-16-cores"] == base_price * 8
        assert RUNNER_PRICING["ubuntu-latest-32-cores"] == base_price * 16
        assert RUNNER_PRICING["ubuntu-latest-64-cores"] == base_price * 32


class TestRealWorldScenarios:
    """Test realistic CI/CD scenarios."""

    def test_typical_startup_ci_pipeline(self):
        """Test cost for typical startup CI pipeline."""
        # Typical pipeline: test, lint, build
        jobs = [
            {"runner_type": "ubuntu-latest", "billable_ms": 180000},      # test: 3 min
            {"runner_type": "ubuntu-latest", "billable_ms": 45000},       # lint: 45s -> 1 min
            {"runner_type": "ubuntu-latest", "billable_ms": 120000},      # build: 2 min
        ]
        cost = calculate_workflow_cost(jobs)
        # 3 + 1 + 2 = 6 minutes * $0.008 = $0.048
        assert cost == Decimal("0.0480")

    def test_large_project_with_parallel_jobs(self):
        """Test cost for large project with parallel matrix builds."""
        # Test across multiple Node versions and OSes
        jobs = [
            # Linux tests
            {"runner_type": "ubuntu-latest", "billable_ms": 240000},      # 4 min
            {"runner_type": "ubuntu-latest", "billable_ms": 240000},      # 4 min
            {"runner_type": "ubuntu-latest", "billable_ms": 240000},      # 4 min
            # Windows test
            {"runner_type": "windows-latest", "billable_ms": 300000},     # 5 min
            # macOS test
            {"runner_type": "macos-latest", "billable_ms": 360000},       # 6 min
        ]
        cost = calculate_workflow_cost(jobs)
        # (3 * 4 * 0.008) + (5 * 0.016) + (6 * 0.08) = 0.096 + 0.08 + 0.48 = $0.656
        assert cost == Decimal("0.6560")

    def test_mobile_app_build_ios_android(self):
        """Test cost for mobile app builds."""
        jobs = [
            # iOS build on macOS large runner
            {"runner_type": "macos-latest-large", "billable_ms": 900000},  # 15 min
            # Android build on Linux 8-core
            {"runner_type": "ubuntu-latest-8-cores", "billable_ms": 600000},  # 10 min
        ]
        cost = calculate_workflow_cost(jobs)
        # (15 * 0.12) + (10 * 0.032) = 1.8 + 0.32 = $2.12
        assert cost == Decimal("2.1200")

    def test_heavy_compute_workload(self):
        """Test cost for heavy compute on large runners."""
        # Machine learning model training
        cost = calculate_job_cost("ubuntu-latest-64-cores", 1800000)  # 30 min
        # 30 * $0.256 = $7.68
        assert cost == Decimal("7.6800")
