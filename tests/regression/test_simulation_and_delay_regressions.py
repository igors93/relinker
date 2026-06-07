"""Regression tests for verified simulation and delay failures."""

from __future__ import annotations

import inspect
from contextlib import suppress

import pytest

from relinker import InvalidRetryConfigError, RetryPolicy, RetryState
from relinker.delays.exponential import ExponentialDelay
from relinker.delays.fixed import FixedDelay
from relinker.delays.random_exponential import RandomExponentialDelay
from relinker.delays.stateful import StatefulCustomDelay


def test_simulation_does_not_report_sleep_beyond_max_time_budget() -> None:
    """Simulation must match the executor, which refuses a sleep exceeding max_time."""
    simulation = RetryPolicy().max_time(5).fixed_delay(10).simulate(attempts=5)

    assert simulation.total_sleep == 0.0
    assert simulation.attempt_count == 1
    assert simulation.stops_early is True
    assert simulation.attempts[0].stops_after_attempt is True
    assert simulation.attempts[0].delay_before_next_attempt == 0.0


def test_simulate_does_not_execute_custom_delay_callback() -> None:
    """Simulation is inspection and must not invoke application callbacks."""
    calls: list[int] = []

    def custom_delay(attempt_number: int) -> float:
        calls.append(attempt_number)
        return 1.0

    policy = RetryPolicy().attempts(3).custom_delay(custom_delay)

    # Explicitly refusing to simulate application callbacks is also a valid safe behavior.
    with suppress(InvalidRetryConfigError):
        policy.simulate(attempts=3)

    assert calls == []


def test_simulate_does_not_execute_stateful_delay_callback() -> None:
    """State-aware application callbacks must also remain untouched by simulation."""
    calls: list[RetryState] = []

    def stateful_delay(state: RetryState) -> float:
        calls.append(state)
        return 1.0

    policy = RetryPolicy().attempts(3).stateful_delay(stateful_delay)

    # Explicitly refusing to simulate application callbacks is also a valid safe behavior.
    with suppress(InvalidRetryConfigError):
        policy.simulate(attempts=3)

    assert calls == []


def test_simulate_rejects_stateful_delay_inside_additive_without_calling_callback() -> None:
    calls: list[RetryState] = []

    def stateful_delay(state: RetryState) -> float:
        calls.append(state)
        return 1.0

    policy = RetryPolicy().attempts(3).stateful_delay(stateful_delay).add_delay(FixedDelay(1.0))

    with pytest.raises(InvalidRetryConfigError):
        policy.simulate(attempts=3)

    assert calls == []


def test_simulate_docstring_does_not_claim_stateful_callbacks_are_executed() -> None:
    doc = inspect.getdoc(RetryPolicy.simulate)

    assert doc is not None
    assert "without executing user code" in doc
    assert "StatefulCustomDelay, it uses a minimal state" not in doc
    assert "StatefulCustomDelay" in doc
    assert "not supported" in doc


def test_stateful_delay_next_delay_docstring_does_not_claim_simulation_support() -> None:
    doc = inspect.getdoc(StatefulCustomDelay.next_delay)

    assert doc is not None
    assert "Simulation fallback" not in doc
    assert "When simulate() calls this method" not in doc
    assert "does not make" in doc
    assert "RetryPolicy.simulate() support stateful callbacks" in doc


def test_warnings_do_not_execute_custom_delay_callback() -> None:
    """Reading advisory warnings must never cause application side effects."""
    calls: list[int] = []

    def custom_delay(attempt_number: int) -> float:
        calls.append(attempt_number)
        return 1.0

    RetryPolicy().attempts(3).custom_delay(custom_delay).warnings()

    assert calls == []


def test_capped_exponential_delay_does_not_overflow() -> None:
    """A configured maximum must protect exponential calculation at large attempts."""
    delay = ExponentialDelay(base=1.0, factor=2.0, maximum=60.0)

    assert delay.next_delay(1025) == 60.0


def test_capped_random_exponential_delay_does_not_overflow() -> None:
    """Random exponential delay must apply its cap without overflowing first."""
    delay = RandomExponentialDelay(
        base=1.0,
        factor=2.0,
        minimum=0.0,
        maximum=60.0,
        seed=1,
    )

    value = delay.next_delay(1025)

    assert 0.0 <= value <= 60.0
