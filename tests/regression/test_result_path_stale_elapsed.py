"""
Regression tests for Idea 1: stale elapsed in the result-retry path.

When a function returns a retryable value, elapsed is captured right after
the attempt ends (attempt_ended_at - started_at).  The plan_retry_wait call
that follows can take time (delay strategy, budget lock).  If that time is
not reflected in the should_stop_before_sleep check, a sleep may be allowed
even though elapsed + delay >= max_time().

Each test uses a stateful_delay callback that advances the FakeClock as a
side effect, creating a controlled staleness window without touching private
state.

With the bug:   elapsed=0, delay=1.0 → 0+1=1.0 < 5.0 → sleep (wrong)
With the fix:   now()-started_at=4.5, delay=1.0 → 5.5 >= 5.0 → exhaust (correct)

The tests cover all four execution paths.
"""

from __future__ import annotations

import contextlib

import pytest

from relinker import RetryPolicy
from relinker.state import RetryState
from tests.contracts._support import (
    FakeClock,
    patch_async_clock,
    patch_context_clock,
    patch_sync_clock,
)

_MAX_TIME = 5.0
_ADVANCED_CLOCK = 4.5
_DELAY = 1.0
_RETRYABLE = "retry-me"
_RETRY_PRED = lambda v: v == _RETRYABLE  # noqa: E731


def _make_delay_that_advances(clock: FakeClock):
    """Return a stateful_delay callback that advances the clock and returns _DELAY."""

    def delay_callback(state: RetryState) -> float:
        clock.value = _ADVANCED_CLOCK
        return _DELAY

    return delay_callback


def test_sync_executor_result_path_uses_fresh_elapsed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """should_stop_before_sleep must use current elapsed, not the stale value."""
    clock = FakeClock()
    patch_sync_clock(monkeypatch, clock)

    sleeps: list[float] = []
    calls = 0

    def sleep(s: float) -> None:
        sleeps.append(s)
        clock.sleep(s)

    def returning_op() -> str:
        nonlocal calls
        calls += 1
        return _RETRYABLE

    policy = (
        RetryPolicy()
        .attempts(3)
        .max_time(_MAX_TIME)
        .retry_if_result(_RETRY_PRED)
        .stateful_delay(_make_delay_that_advances(clock))
        .with_sleep(sleep)
        .return_result()
    )

    result = policy.run(returning_op)

    assert result.exhausted, "policy must exhaust"
    assert sleeps == [], (
        f"No sleep expected: delay callback elapsed ({_ADVANCED_CLOCK}) + "
        f"delay ({_DELAY}) = {_ADVANCED_CLOCK + _DELAY} exceeds max_time ({_MAX_TIME}). "
        f"Got: {sleeps}. Stale elapsed=0 would allow sleep."
    )
    assert calls == 1, f"Expected exactly one attempt, got {calls}"


@pytest.mark.asyncio
async def test_async_executor_result_path_uses_fresh_elapsed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = FakeClock()
    patch_async_clock(monkeypatch, clock)

    sleeps: list[float] = []
    calls = 0

    async def async_sleep(s: float) -> None:
        sleeps.append(s)
        clock.value += s

    async def returning_op() -> str:
        nonlocal calls
        calls += 1
        return _RETRYABLE

    policy = (
        RetryPolicy()
        .attempts(3)
        .max_time(_MAX_TIME)
        .retry_if_result(_RETRY_PRED)
        .stateful_delay(_make_delay_that_advances(clock))
        .with_sleep(clock.sleep, async_sleep)
        .return_result()
    )

    result = await policy.run_async(returning_op)

    assert result.exhausted
    assert sleeps == [], (
        f"No sleep expected after delay callback advanced clock. Got: {sleeps}."
    )
    assert calls == 1


def test_sync_context_manager_result_path_uses_fresh_elapsed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = FakeClock()
    patch_context_clock(monkeypatch, clock)

    sleeps: list[float] = []
    calls = 0

    def sleep(s: float) -> None:
        sleeps.append(s)
        clock.sleep(s)

    policy = (
        RetryPolicy()
        .attempts(3)
        .max_time(_MAX_TIME)
        .retry_if_result(_RETRY_PRED)
        .stateful_delay(_make_delay_that_advances(clock))
        .with_sleep(sleep)
    )

    iterator = policy.iter()
    with contextlib.suppress(Exception):
        for attempt in iterator:
            with attempt:
                calls += 1
                attempt.set_result(_RETRYABLE)

    assert sleeps == [], (
        f"No sleep expected after delay callback advanced clock. Got: {sleeps}."
    )
    assert calls == 1, f"Expected exactly one attempt, got {calls}"


@pytest.mark.asyncio
async def test_async_context_manager_result_path_uses_fresh_elapsed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = FakeClock()
    patch_context_clock(monkeypatch, clock)

    sleeps: list[float] = []
    calls = 0

    async def async_sleep(s: float) -> None:
        sleeps.append(s)
        clock.value += s

    policy = (
        RetryPolicy()
        .attempts(3)
        .max_time(_MAX_TIME)
        .retry_if_result(_RETRY_PRED)
        .stateful_delay(_make_delay_that_advances(clock))
        .with_sleep(clock.sleep, async_sleep)
    )

    iterator = policy.async_iter()
    with contextlib.suppress(Exception):
        async for attempt in iterator:
            async with attempt:
                calls += 1
                attempt.set_result(_RETRYABLE)

    assert sleeps == [], (
        f"No sleep expected after delay callback advanced clock. Got: {sleeps}."
    )
    assert calls == 1, f"Expected exactly one attempt, got {calls}"
