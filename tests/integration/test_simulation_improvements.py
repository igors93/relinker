"""Tests for the improved RetrySimulation and RetrySimulationAttempt."""

from __future__ import annotations

import json

from retryflow import RetryPolicy, RetrySimulation, RetrySimulationAttempt


def test_simulation_attempt_count() -> None:
    policy = RetryPolicy().attempts(4).fixed_delay(1)
    sim = policy.simulate(attempts=4)
    assert sim.attempt_count == 4


def test_simulation_max_delay() -> None:
    policy = RetryPolicy().attempts(5).exponential_delay(base=1, factor=2, maximum=8)
    sim = policy.simulate(attempts=5)
    assert sim.max_delay == 8.0


def test_simulation_stops_early() -> None:
    policy = RetryPolicy().attempts(3).fixed_delay(1)
    sim = policy.simulate(attempts=10)  # stop at attempt 3
    assert sim.stops_early
    assert sim.attempt_count == 3


def test_simulation_no_early_stop() -> None:
    policy = RetryPolicy().attempts(5).fixed_delay(1)
    sim = policy.simulate(attempts=3)  # fewer than max attempts
    assert not sim.stops_early
    assert sim.attempt_count == 3


def test_simulation_cumulative_sleep() -> None:
    policy = RetryPolicy().attempts(5).fixed_delay(2)
    sim = policy.simulate(attempts=3)

    assert sim.attempts[0].cumulative_sleep == 2.0
    assert sim.attempts[1].cumulative_sleep == 4.0
    assert sim.attempts[2].cumulative_sleep == 6.0


def test_simulation_to_dict_has_new_fields() -> None:
    policy = RetryPolicy().attempts(3).fixed_delay(1)
    sim = policy.simulate(attempts=3)
    d = sim.to_dict()

    assert "attempt_count" in d
    assert "max_delay" in d
    assert "stops_early" in d
    assert d["attempt_count"] == 3

    for attempt in d["attempts"]:  # type: ignore[union-attr]
        assert "cumulative_sleep" in attempt


def test_simulation_to_json() -> None:
    policy = RetryPolicy().attempts(3).fixed_delay(1)
    sim = policy.simulate(attempts=3)
    text = sim.to_json()
    parsed = json.loads(text)

    assert "attempt_count" in parsed
    assert "total_sleep" in parsed


def test_simulation_to_json_with_indent() -> None:
    policy = RetryPolicy().attempts(2).fixed_delay(0.5)
    sim = policy.simulate(attempts=2)
    text = sim.to_json(indent=2)

    assert "\n" in text
    assert '"attempt_count"' in text


def test_simulation_describe_shows_cumulative() -> None:
    policy = RetryPolicy().attempts(3).fixed_delay(1)
    sim = policy.simulate(attempts=3)
    text = sim.describe()

    assert "cumulative" in text
    assert "Attempts simulated" in text
    assert "Max single delay" in text


def test_simulation_attempt_stop_marker_in_describe() -> None:
    policy = RetryPolicy().attempts(2).fixed_delay(1)
    sim = policy.simulate(attempts=5)
    text = sim.describe()

    assert "[stop]" in text


def test_simulation_attempt_dataclass_cumulative_sleep_default() -> None:
    attempt = RetrySimulationAttempt(
        attempt_number=1,
        delay_before_next_attempt=0.5,
        stops_after_attempt=False,
    )
    assert attempt.cumulative_sleep == 0.0


def test_simulation_total_sleep_unchanged() -> None:
    policy = RetryPolicy().attempts(3).fixed_delay(2)
    sim = policy.simulate(attempts=3)
    assert sim.total_sleep == 4.0  # last attempt has delay=0 (stop)


def test_simulation_is_dataclass() -> None:
    policy = RetryPolicy().attempts(2).fixed_delay(1)
    sim = policy.simulate()
    assert isinstance(sim, RetrySimulation)
