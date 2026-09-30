"""Regression tests: derived delays saturate at the operational ceiling.

Before the fix, ``forever().exponential_delay(...).jitter(...)`` raised
InvalidRetryConfigError on attempt 18: the exponential part saturated at
MAX_SLEEP_SECONDS and the jitter was added on top of it, so the final delay
exceeded the ceiling mid-execution. LinearDelay had no ceiling at all.

Derived values (sums, linear growth) now saturate at the ceiling, while
invalid component values (negative, NaN, infinite, or an explicit user
callback above the ceiling) are still rejected.
"""

from __future__ import annotations

import math
from collections.abc import Callable

import pytest

from relinker import InvalidRetryConfigError, RetryPolicy
from relinker.delays.composite import AdditiveDelay
from relinker.delays.fixed import FixedDelay
from relinker.delays.linear import LinearDelay
from relinker.internal.validation import MAX_SLEEP_SECONDS

ATTEMPTS = 25  # exponential base=1 reaches the ceiling at attempt 18


def _failing_until(succeed_on: int) -> tuple[list[int], Callable[[], str]]:
    calls: list[int] = []

    def task() -> str:
        calls.append(1)
        if len(calls) < succeed_on:
            raise TimeoutError("down")
        return "ok"

    return calls, task


def _backoff_with_jitter(maximum: float | None = None) -> RetryPolicy[str]:
    return (
        RetryPolicy[str]()
        .forever()
        .on(TimeoutError)
        .exponential_delay(base=1, maximum=maximum)
        .jitter(maximum=0.5, seed=7)
    )


@pytest.mark.parametrize("maximum", [None, MAX_SLEEP_SECONDS])
def test_sync_backoff_with_jitter_survives_past_the_ceiling(maximum: float | None) -> None:
    sleeps: list[float] = []
    calls, task = _failing_until(ATTEMPTS)
    policy = _backoff_with_jitter(maximum).with_sleep(sleeps.append)

    assert policy.run(task) == "ok"
    assert len(calls) == ATTEMPTS
    assert max(sleeps) == MAX_SLEEP_SECONDS
    assert all(0.0 <= delay <= MAX_SLEEP_SECONDS for delay in sleeps)


async def test_async_backoff_with_jitter_survives_past_the_ceiling() -> None:
    sleeps: list[float] = []
    calls: list[int] = []

    async def task() -> str:
        calls.append(1)
        if len(calls) < ATTEMPTS:
            raise TimeoutError("down")
        return "ok"

    async def record(seconds: float) -> None:
        sleeps.append(seconds)

    policy = _backoff_with_jitter().with_sleep(lambda _: None, record)

    assert await policy.run_async(task) == "ok"
    assert max(sleeps) == MAX_SLEEP_SECONDS


def test_context_manager_backoff_with_jitter_survives_past_the_ceiling() -> None:
    sleeps: list[float] = []
    policy = _backoff_with_jitter().with_sleep(sleeps.append)
    iterator = policy.iter(name="block")

    for attempt in iterator:
        with attempt:
            if attempt.number < ATTEMPTS:
                raise TimeoutError("down")
            attempt.set_result("ok")

    assert iterator.result is not None
    assert iterator.result.value == "ok"
    assert max(sleeps) == MAX_SLEEP_SECONDS


def test_simulation_of_backoff_with_jitter_does_not_raise() -> None:
    simulation = _backoff_with_jitter().simulate(attempts=ATTEMPTS)

    delays = [item.delay_before_next_attempt for item in simulation.attempts]
    assert delays[-1] == MAX_SLEEP_SECONDS
    assert all(delay <= MAX_SLEEP_SECONDS for delay in delays)


def test_linear_delay_without_maximum_saturates_at_ceiling() -> None:
    delay = LinearDelay(start=0.0, step=50_000.0)

    assert delay.next_delay(2) == 50_000.0
    assert delay.next_delay(3) == MAX_SLEEP_SECONDS
    assert delay.next_delay(10_000) == MAX_SLEEP_SECONDS


def test_linear_delay_explicit_maximum_still_wins() -> None:
    assert LinearDelay(start=0.0, step=50_000.0, maximum=60.0).next_delay(3) == 60.0


def test_linear_policy_with_large_step_keeps_running() -> None:
    sleeps: list[float] = []
    calls, task = _failing_until(5)
    policy = (
        RetryPolicy[str]()
        .forever()
        .on(TimeoutError)
        .linear_delay(start=0.0, step=50_000.0)
        .with_sleep(sleeps.append)
    )

    assert policy.run(task) == "ok"
    assert sleeps == [0.0, 50_000.0, MAX_SLEEP_SECONDS, MAX_SLEEP_SECONDS]


def test_nested_additive_delay_saturates_at_every_level() -> None:
    near_ceiling = FixedDelay(MAX_SLEEP_SECONDS)
    nested = AdditiveDelay((AdditiveDelay((near_ceiling, near_ceiling)), near_ceiling))

    assert nested.next_delay(1) == MAX_SLEEP_SECONDS


class _StaticDelay:
    def __init__(self, value: float) -> None:
        self.value = value

    def next_delay(self, attempt_number: int) -> float:
        return self.value


@pytest.mark.parametrize(
    "invalid",
    [
        pytest.param(-1.0, id="negative"),
        pytest.param(math.inf, id="inf"),
        pytest.param(math.nan, id="nan"),
        pytest.param(MAX_SLEEP_SECONDS + 1.0, id="above-ceiling"),
    ],
)
def test_additive_delay_rejects_invalid_component_instead_of_hiding_it(invalid: float) -> None:
    delay = AdditiveDelay((FixedDelay(1.0), _StaticDelay(invalid)))

    with pytest.raises(InvalidRetryConfigError):
        delay.next_delay(1)


def test_stateful_component_above_ceiling_is_still_rejected() -> None:
    sleeps: list[float] = []
    policy = (
        RetryPolicy()
        .attempts(2)
        .on(TimeoutError)
        .stateful_delay(lambda state: MAX_SLEEP_SECONDS + 1.0)
        .jitter(maximum=0.0)
        .with_sleep(sleeps.append)
    )

    def task() -> None:
        raise TimeoutError("down")

    with pytest.raises(InvalidRetryConfigError):
        policy.run(task)
    assert sleeps == []
