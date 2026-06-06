"""
Regression tests for Idea 2: before_sleep handler time counts against max_time().

Contract: after a before_sleep event handler runs without raising, the executor
must recheck whether elapsed + delay still fits within max_time().  If the
handler consumed the remaining budget, the sleep must not execute, the unused
budget reservation must be released, and exhaustion must follow the policy.

The tests use an on_retry (before_sleep) handler that advances a FakeClock as a
side effect.  The handler does not raise.

With the bug:  handler advances clock to 4.5, but the executor sleeps anyway
               (because it only rechecked before the emit, not after).
With the fix:  handler advances clock to 4.5 → 4.5 + 1.0 = 5.5 ≥ 5.0 → no sleep.

All four execution paths are covered for the exception-retry path.
The result-retry path is also covered where the same logic applies.
"""

from __future__ import annotations

import contextlib

import pytest

from relinker import RetryBudget, RetryPolicy
from relinker.event import RetryEvent
from tests.contracts._support import (
    FakeClock,
    patch_async_clock,
    patch_context_clock,
    patch_sync_clock,
)

_MAX_TIME = 5.0
_DELAY = 1.0
_ADVANCED_CLOCK = 4.5


def _make_clock_advancer(clock: FakeClock):
    """Return a before_sleep (on_retry) handler that advances the clock without raising."""

    def advance(event: object) -> None:  # noqa: ARG001
        clock.value = _ADVANCED_CLOCK

    return advance


# ──────────────────────────────────────────────────────────────────────────────
# Exception-retry path
# ──────────────────────────────────────────────────────────────────────────────


def test_sync_executor_before_sleep_handler_time_counts_against_max_time(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sync executor: handler that advances clock must prevent oversleeping."""
    clock = FakeClock()
    patch_sync_clock(monkeypatch, clock)

    sleeps: list[float] = []
    before_sleep_calls: list[str] = []
    after_giveup_calls: list[str] = []
    calls = 0

    def sleep(s: float) -> None:
        sleeps.append(s)
        clock.sleep(s)

    def track_events(event: RetryEvent) -> None:
        before_sleep_calls.append("x") if event.name == "before_sleep" else None
        after_giveup_calls.append("x") if event.name == "after_giveup" else None

    def failing_op() -> str:
        nonlocal calls
        calls += 1
        raise TimeoutError("fail")

    policy = (
        RetryPolicy()
        .attempts(3)
        .max_time(_MAX_TIME)
        .on(TimeoutError)
        .fixed_delay(_DELAY)
        .on_retry(_make_clock_advancer(clock))
        .on_event("before_sleep", track_events)
        .on_event("after_giveup", track_events)
        .with_sleep(sleep)
        .return_result()
    )

    result = policy.run(failing_op)

    assert result.exhausted
    assert sleeps == [], (
        f"Handler elapsed ({_ADVANCED_CLOCK}) + delay ({_DELAY}) = "
        f"{_ADVANCED_CLOCK + _DELAY} exceeds max_time ({_MAX_TIME}). "
        f"Sleep must not run. Got: {sleeps}."
    )
    assert calls == 1
    assert len(before_sleep_calls) == 1, "before_sleep must be emitted once"
    assert len(after_giveup_calls) == 1, "after_giveup must fire after handler exhausts budget"


@pytest.mark.asyncio
async def test_async_executor_before_sleep_handler_time_counts_against_max_time(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = FakeClock()
    patch_async_clock(monkeypatch, clock)

    sleeps: list[float] = []
    calls = 0

    async def async_sleep(s: float) -> None:
        sleeps.append(s)
        clock.value += s

    async def failing_op() -> str:
        nonlocal calls
        calls += 1
        raise TimeoutError("fail")

    policy = (
        RetryPolicy()
        .attempts(3)
        .max_time(_MAX_TIME)
        .on(TimeoutError)
        .fixed_delay(_DELAY)
        .on_retry(_make_clock_advancer(clock))
        .with_sleep(clock.sleep, async_sleep)
        .return_result()
    )

    result = await policy.run_async(failing_op)

    assert result.exhausted
    assert sleeps == [], f"Sleep must not run when handler consumed time. Got: {sleeps}."
    assert calls == 1


def test_sync_context_manager_before_sleep_handler_time_counts_against_max_time(
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
        .on(TimeoutError)
        .fixed_delay(_DELAY)
        .on_retry(_make_clock_advancer(clock))
        .with_sleep(sleep)
    )

    with contextlib.suppress(TimeoutError):
        for attempt in policy.iter():
            with attempt:
                calls += 1
                raise TimeoutError("fail")

    assert sleeps == [], f"Sleep must not run when handler consumed time. Got: {sleeps}."
    assert calls == 1


@pytest.mark.asyncio
async def test_async_context_manager_before_sleep_handler_time_counts_against_max_time(
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
        .on(TimeoutError)
        .fixed_delay(_DELAY)
        .on_retry(_make_clock_advancer(clock))
        .with_sleep(clock.sleep, async_sleep)
    )

    with contextlib.suppress(TimeoutError):
        async for attempt in policy.async_iter():
            async with attempt:
                calls += 1
                raise TimeoutError("fail")

    assert sleeps == [], f"Sleep must not run when handler consumed time. Got: {sleeps}."
    assert calls == 1


# ──────────────────────────────────────────────────────────────────────────────
# Result-retry path
# ──────────────────────────────────────────────────────────────────────────────


def test_sync_executor_result_before_sleep_handler_time_counts_against_max_time(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Result path: same contract when before_sleep handler consumes remaining time."""
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
        return "retry-me"

    policy = (
        RetryPolicy()
        .attempts(3)
        .max_time(_MAX_TIME)
        .retry_if_result(lambda v: v == "retry-me")
        .fixed_delay(_DELAY)
        .on_retry(_make_clock_advancer(clock))
        .with_sleep(sleep)
        .return_result()
    )

    result = policy.run(returning_op)

    assert result.exhausted
    assert sleeps == [], f"Sleep must not run in result path. Got: {sleeps}."
    assert calls == 1


@pytest.mark.asyncio
async def test_async_executor_result_before_sleep_handler_time_counts_against_max_time(
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
        return "retry-me"

    policy = (
        RetryPolicy()
        .attempts(3)
        .max_time(_MAX_TIME)
        .retry_if_result(lambda v: v == "retry-me")
        .fixed_delay(_DELAY)
        .on_retry(_make_clock_advancer(clock))
        .with_sleep(clock.sleep, async_sleep)
        .return_result()
    )

    result = await policy.run_async(returning_op)

    assert result.exhausted
    assert sleeps == [], f"Sleep must not run in result path. Got: {sleeps}."
    assert calls == 1


# ──────────────────────────────────────────────────────────────────────────────
# Budget reservation is released in the new exhaustion path
# ──────────────────────────────────────────────────────────────────────────────


def test_sync_executor_before_sleep_handler_exhaustion_releases_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When the before_sleep handler consumes max_time, the budget reservation is released."""
    clock = FakeClock()
    patch_sync_clock(monkeypatch, clock)

    budget = RetryBudget(max_retries=1, per=10)
    calls = 0

    def failing_op() -> str:
        nonlocal calls
        calls += 1
        raise TimeoutError("fail")

    broken_policy = (
        RetryPolicy()
        .attempts(3)
        .max_time(_MAX_TIME)
        .on(TimeoutError)
        .fixed_delay(_DELAY)
        .on_retry(_make_clock_advancer(clock))
        .with_retry_budget(budget, key="api")
        .with_sleep(clock.sleep)
        .return_result()
    )

    result = broken_policy.run(failing_op)
    assert result.exhausted

    # Follow-up execution on the same budget must not inherit a phantom delay.
    # A leaked reservation would force a 10-second wait.
    clock.value = 0.0
    sleeps: list[float] = []

    def sleep(s: float) -> None:
        sleeps.append(s)
        clock.sleep(s)

    follow_calls = 0

    def retry_once() -> str:
        nonlocal follow_calls
        follow_calls += 1
        if follow_calls == 1:
            raise TimeoutError("temporary")
        return "ok"

    follow_policy = (
        RetryPolicy()
        .attempts(2)
        .on(TimeoutError)
        .with_retry_budget(budget, key="api")
        .with_sleep(sleep)
    )

    assert follow_policy.run(retry_once) == "ok"
    assert sleeps == [0.0], (
        f"Expected [0.0] — no phantom budget delay. Got {sleeps}. "
        "A leaked reservation would produce [10.0]."
    )
