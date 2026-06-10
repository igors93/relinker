"""Unit tests for policy simulation and worst-case load estimates."""

from __future__ import annotations

import pytest

from relinker import InvalidRetryConfigError, RetryPolicy


def test_simulation_rejects_custom_delay_without_executing_callback() -> None:
    called = False

    def delay(_: int) -> float:
        nonlocal called
        called = True
        return 1

    with pytest.raises(InvalidRetryConfigError, match="Simulation"):
        RetryPolicy().custom_delay(delay).simulate(3)
    assert called is False


def test_bounded_load_estimate_matches_attempt_limit() -> None:
    estimate = RetryPolicy().attempts(4).estimate_load(concurrent_executions=10)
    assert estimate.original_calls == 10
    assert estimate.maximum_attempts_per_execution == 4
    assert estimate.maximum_additional_retries == 30
    assert estimate.maximum_total_calls == 40
    assert estimate.unbounded is False


def test_forever_load_estimate_is_unbounded() -> None:
    estimate = RetryPolicy().forever().estimate_load(concurrent_executions=2)
    assert estimate.unbounded is True
    assert estimate.maximum_total_calls is None
