"""Regression tests for custom callbacks hidden inside composed delays."""

from __future__ import annotations

from contextlib import suppress

from relinker import InvalidRetryConfigError, RetryPolicy


def test_simulate_does_not_execute_custom_callback_inside_additive_delay() -> None:
    """Simulation must not execute a custom delay nested inside jitter composition."""
    calls: list[int] = []

    def custom_delay(attempt_number: int) -> float:
        calls.append(attempt_number)
        return 1.0

    policy = RetryPolicy().attempts(3).custom_delay(custom_delay).jitter(maximum=0.0)

    # Rejecting simulation is acceptable; executing application code is not.
    with suppress(InvalidRetryConfigError):
        policy.simulate(attempts=3)

    assert calls == []


def test_warnings_do_not_execute_custom_callback_inside_additive_delay() -> None:
    """Reading warnings must remain free of application callback side effects."""
    calls: list[int] = []

    def custom_delay(attempt_number: int) -> float:
        calls.append(attempt_number)
        return 1.0

    policy = RetryPolicy().attempts(3).custom_delay(custom_delay).jitter(maximum=0.0)

    policy.warnings()

    assert calls == []
