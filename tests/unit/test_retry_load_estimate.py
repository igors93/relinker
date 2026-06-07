from __future__ import annotations

import dataclasses

import pytest

from relinker import InvalidRetryConfigError, RetryBudget, RetryLoadEstimate, RetryPolicy


def test_estimate_load_for_single_attempt_has_no_additional_retries() -> None:
    estimate = RetryPolicy().attempts(1).estimate_load(concurrent_executions=100)

    assert isinstance(estimate, RetryLoadEstimate)
    assert estimate.concurrent_executions == 100
    assert estimate.maximum_attempts_per_execution == 1
    assert estimate.original_calls == 100
    assert estimate.maximum_additional_retries == 0
    assert estimate.maximum_total_calls == 100
    assert estimate.unbounded is False
    assert estimate.partial is False


def test_estimate_load_for_multiple_attempts_uses_worst_case_math() -> None:
    estimate = RetryPolicy().attempts(4).estimate_load(concurrent_executions=25)

    assert estimate.maximum_attempts_per_execution == 4
    assert estimate.maximum_additional_retries == 75
    assert estimate.maximum_total_calls == 100


def test_estimate_load_for_forever_retry_is_unbounded() -> None:
    estimate = RetryPolicy().forever().estimate_load(concurrent_executions=10)

    assert estimate.maximum_attempts_per_execution is None
    assert estimate.maximum_additional_retries is None
    assert estimate.maximum_total_calls is None
    assert estimate.unbounded is True
    assert estimate.partial is False


def test_estimate_load_for_known_composed_stop() -> None:
    estimate = (
        RetryPolicy().attempts(10).or_stop_after_attempts(3).estimate_load(concurrent_executions=5)
    )

    assert estimate.maximum_attempts_per_execution == 3
    assert estimate.maximum_additional_retries == 10
    assert estimate.maximum_total_calls == 15
    assert estimate.partial is False


def test_estimate_load_for_unestimable_composed_stop_is_partial() -> None:
    estimate = (
        RetryPolicy().attempts(3).and_stop_after_time(60).estimate_load(concurrent_executions=5)
    )

    assert estimate.maximum_attempts_per_execution is None
    assert estimate.maximum_additional_retries is None
    assert estimate.maximum_total_calls is None
    assert estimate.unbounded is False
    assert estimate.partial is True


def test_estimate_load_reports_retry_budget_without_subtracting_total_retries() -> None:
    policy = (
        RetryPolicy()
        .attempts(4)
        .with_retry_budget(
            RetryBudget(max_retries=100, per=60),
            key="api",
        )
    )

    estimate = policy.estimate_load(concurrent_executions=1000)

    assert estimate.maximum_additional_retries == 3000
    assert estimate.retry_budget_configured is True
    assert estimate.retry_budget_capacity == 100
    assert estimate.retry_budget_period == 60.0


def test_estimate_load_handles_large_values() -> None:
    estimate = RetryPolicy().attempts(1_000_001).estimate_load(concurrent_executions=1_000_000)

    assert estimate.maximum_additional_retries == 1_000_000_000_000
    assert estimate.maximum_total_calls == 1_000_001_000_000


@pytest.mark.parametrize("value", [0, -1, True, 1.5, "10"])
def test_estimate_load_rejects_invalid_concurrency(value: object) -> None:
    with pytest.raises(InvalidRetryConfigError):
        RetryPolicy().estimate_load(concurrent_executions=value)  # type: ignore[arg-type]


def test_estimate_load_is_immutable_and_text_mentions_worst_case() -> None:
    estimate = RetryPolicy().attempts(3).estimate_load(concurrent_executions=2)

    with pytest.raises(dataclasses.FrozenInstanceError):
        estimate.concurrent_executions = 99  # type: ignore[misc]
    assert "worst-case estimate" in estimate.describe()
    assert "Maximum total calls: 6" in estimate.describe()


def test_preview_can_include_load_estimate() -> None:
    preview = RetryPolicy().attempts(3).preview(attempts=3, concurrent_executions=2)

    assert "Load worst-case estimate" in preview
    assert "Maximum total calls: 6" in preview
