"""Regression tests for verified simulation and delay failures."""

from __future__ import annotations

from contextlib import suppress

from relinker import InvalidRetryConfigError, RetryPolicy, RetryState
from relinker.delays.exponential import ExponentialDelay
from relinker.delays.random_exponential import RandomExponentialDelay


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
