"""
Regression tests for two behavioral contracts:

1. A reservation created by plan_retry_wait must be released if the
   before_sleep event handler raises an exception, regardless of which
   execution path (sync, async, sync context manager, async context manager).

2. The should_stop_before_sleep decision must use the current elapsed time,
   not a value captured before event handlers ran, so that time consumed by
   handlers between the attempt end and the sleep authorization is correctly
   counted against max_time().

Both tests observe only public API: sleep delays, result outcomes, and the
exception that propagates from a failing handler.  No private budget state
is accessed.
"""

from __future__ import annotations

import contextlib

import pytest

from relinker import RetryBudget, RetryPolicy
from tests.contracts._support import (
    FakeClock,
    patch_async_clock,
    patch_context_clock,
    patch_sync_clock,
)

# -----------------------------------------------------------------------
# helpers
# -----------------------------------------------------------------------


class _HandlerError(Exception):
    """Distinct exception raised by the before_sleep handler under test."""


def _before_sleep_raiser(event: object) -> None:  # noqa: ARG001
    raise _HandlerError("before_sleep-handler-fail")


# -----------------------------------------------------------------------
# Defect 1 – before_sleep handler exception must not leak a budget
# reservation.
#
# Contract: every reservation created for a retry that ultimately does not
# execute must be released.  The observable consequence is that a second
# execution sharing the same budget and key must not inherit a phantom
# delay from the abandoned reservation.
#
# Each test:
#   1. Runs a policy whose before_sleep handler raises.
#   2. Catches the handler exception.
#   3. Immediately runs a second policy on the same budget and key.
#   4. Asserts the second execution's sleep == 0 (no phantom delay).
#
# If the reservation leaked, the second sleep would be 10 (the full budget
# window) instead of 0.
# -----------------------------------------------------------------------


def test_sync_executor_before_sleep_exception_releases_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = FakeClock()
    patch_sync_clock(monkeypatch, clock)
    budget = RetryBudget(max_retries=1, per=10)

    def always_fails() -> str:
        raise TimeoutError("down")

    broken_policy = (
        RetryPolicy()
        .attempts(2)
        .on(TimeoutError)
        .with_retry_budget(budget, key="api")
        .with_sleep(clock.sleep)
        .on_retry(_before_sleep_raiser)
    )

    with pytest.raises(_HandlerError):
        broken_policy.run(always_fails)

    # Second execution must not receive a delay from the abandoned reservation.
    sleeps: list[float] = []

    def sleep(seconds: float) -> None:
        sleeps.append(seconds)
        clock.sleep(seconds)

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


@pytest.mark.asyncio
async def test_async_executor_before_sleep_exception_releases_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = FakeClock()
    patch_async_clock(monkeypatch, clock)
    budget = RetryBudget(max_retries=1, per=10)

    async def always_fails() -> str:
        raise TimeoutError("down")

    broken_policy = (
        RetryPolicy()
        .attempts(2)
        .on(TimeoutError)
        .with_retry_budget(budget, key="api")
        .with_sleep(clock.sleep, clock.async_sleep)
        .on_retry(_before_sleep_raiser)
    )

    with pytest.raises(_HandlerError):
        await broken_policy.run_async(always_fails)

    sleeps: list[float] = []

    async def async_sleep(seconds: float) -> None:
        sleeps.append(seconds)
        clock.value += seconds

    follow_calls = 0

    async def retry_once() -> str:
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
        .with_sleep(clock.sleep, async_sleep)
    )

    assert await follow_policy.run_async(retry_once) == "ok"
    assert sleeps == [0.0], (
        f"Expected [0.0] — no phantom budget delay. Got {sleeps}. "
        "A leaked reservation would produce [10.0]."
    )


def test_sync_context_manager_before_sleep_exception_releases_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = FakeClock()
    patch_context_clock(monkeypatch, clock)
    budget = RetryBudget(max_retries=1, per=10)

    broken_policy = (
        RetryPolicy()
        .attempts(2)
        .on(TimeoutError)
        .with_retry_budget(budget, key="api")
        .with_sleep(clock.sleep)
        .on_retry(_before_sleep_raiser)
    )

    with pytest.raises(_HandlerError):
        for attempt in broken_policy.iter():
            with attempt:
                raise TimeoutError("down")

    sleeps: list[float] = []

    def sleep(seconds: float) -> None:
        sleeps.append(seconds)
        clock.sleep(seconds)

    follow_policy = (
        RetryPolicy()
        .attempts(2)
        .on(TimeoutError)
        .with_retry_budget(budget, key="api")
        .with_sleep(sleep)
    )

    follow_calls = 0
    for attempt in follow_policy.iter():
        with attempt:
            follow_calls += 1
            if follow_calls > 1:
                attempt.set_result("ok")
            else:
                raise TimeoutError("temporary")

    assert sleeps == [0.0], (
        f"Expected [0.0] — no phantom budget delay. Got {sleeps}. "
        "A leaked reservation would produce [10.0]."
    )


@pytest.mark.asyncio
async def test_async_context_manager_before_sleep_exception_releases_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = FakeClock()
    patch_context_clock(monkeypatch, clock)
    budget = RetryBudget(max_retries=1, per=10)

    broken_policy = (
        RetryPolicy()
        .attempts(2)
        .on(TimeoutError)
        .with_retry_budget(budget, key="api")
        .with_sleep(clock.sleep, clock.async_sleep)
        .on_retry(_before_sleep_raiser)
    )

    with pytest.raises(_HandlerError):
        async for attempt in broken_policy.async_iter():
            async with attempt:
                raise TimeoutError("down")

    sleeps: list[float] = []

    async def async_sleep(seconds: float) -> None:
        sleeps.append(seconds)
        clock.value += seconds

    follow_policy = (
        RetryPolicy()
        .attempts(2)
        .on(TimeoutError)
        .with_retry_budget(budget, key="api")
        .with_sleep(clock.sleep, async_sleep)
    )

    follow_calls = 0
    async for attempt in follow_policy.async_iter():
        async with attempt:
            follow_calls += 1
            if follow_calls > 1:
                attempt.set_result("ok")
            else:
                raise TimeoutError("temporary")

    assert sleeps == [0.0], (
        f"Expected [0.0] — no phantom budget delay. Got {sleeps}. "
        "A leaked reservation would produce [10.0]."
    )


# -----------------------------------------------------------------------
# Defect 2 – should_stop_before_sleep must use current elapsed, not the
# value captured immediately after the attempt ended.
#
# Contract: time consumed by event handlers between the attempt end and
# the sleep-authorization check must be counted against max_time().
#
# Scenario (exception-retry path, all four execution shapes):
#   - max_time = 5 s
#   - fixed delay = 1 s
#   - FakeClock starts at 0; attempt does not advance clock
#   - after_failure handler advances clock to 4.5 s
#   - Stale elapsed = 0: 0+1=1 < 5 → sleep permitted  (BUG)
#   - Fresh elapsed = 4.5: 4.5+1=5.5 ≥ 5 → stop before sleep (CORRECT)
#
# Observable: sleeps list is empty and only one attempt is made.
#
# Note: the result-retry path is not covered here because no event is
# emitted between elapsed capture and should_stop_before_sleep in that
# branch, so a deterministic handler-based clock advance is not possible.
# -----------------------------------------------------------------------

_MAX_TIME = 5.0
_DELAY = 1.0
_HANDLER_CLOCK_VALUE = 4.5  # After handler: elapsed=4.5, delay=1 → 5.5 > max_time=5


def _make_clock_advancer(clock: FakeClock) -> object:
    """Return an after_failure handler that advances the fake clock."""

    def advance(event: object) -> None:  # noqa: ARG001
        clock.value = _HANDLER_CLOCK_VALUE

    return advance


def test_stale_elapsed_sync_executor_exception_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """max_time() must stop when handler time makes elapsed + delay exceed the budget."""
    clock = FakeClock()
    patch_sync_clock(monkeypatch, clock)

    sleeps: list[float] = []
    calls = 0

    def sleep(seconds: float) -> None:
        sleeps.append(seconds)
        clock.sleep(seconds)

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
        .on_failure(_make_clock_advancer(clock))
        .with_sleep(sleep)
        .return_result()
    )

    result = policy.run(failing_op)

    assert result.exhausted
    assert sleeps == [], (
        f"No sleep expected: handler elapsed ({_HANDLER_CLOCK_VALUE}) + "
        f"delay ({_DELAY}) = {_HANDLER_CLOCK_VALUE + _DELAY} exceeds "
        f"max_time ({_MAX_TIME}). Got sleeps: {sleeps}. "
        "Stale elapsed would incorrectly allow sleep."
    )
    assert calls == 1, f"Expected exactly one attempt, got {calls}"


@pytest.mark.asyncio
async def test_stale_elapsed_async_executor_exception_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Async executor: max_time() must stop when handler time exceeds budget."""
    clock = FakeClock()
    patch_async_clock(monkeypatch, clock)

    sleeps: list[float] = []
    calls = 0

    async def async_sleep(seconds: float) -> None:
        sleeps.append(seconds)
        clock.value += seconds

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
        .on_failure(_make_clock_advancer(clock))
        .with_sleep(clock.sleep, async_sleep)
        .return_result()
    )

    result = await policy.run_async(failing_op)

    assert result.exhausted
    assert sleeps == [], (
        f"No sleep expected: handler elapsed ({_HANDLER_CLOCK_VALUE}) + "
        f"delay ({_DELAY}) exceeds max_time ({_MAX_TIME}). Got: {sleeps}."
    )
    assert calls == 1


def test_stale_elapsed_sync_context_manager_exception_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sync context manager: max_time() must stop when handler time exceeds budget."""
    clock = FakeClock()
    patch_context_clock(monkeypatch, clock)

    sleeps: list[float] = []
    calls = 0

    def sleep(seconds: float) -> None:
        sleeps.append(seconds)
        clock.sleep(seconds)

    policy = (
        RetryPolicy()
        .attempts(3)
        .max_time(_MAX_TIME)
        .on(TimeoutError)
        .fixed_delay(_DELAY)
        .on_failure(_make_clock_advancer(clock))
        .with_sleep(sleep)
    )

    with contextlib.suppress(TimeoutError):
        for attempt in policy.iter():
            with attempt:
                calls += 1
                raise TimeoutError("fail")

    assert sleeps == [], (
        f"No sleep expected: handler elapsed ({_HANDLER_CLOCK_VALUE}) + "
        f"delay ({_DELAY}) exceeds max_time ({_MAX_TIME}). Got: {sleeps}."
    )
    assert calls == 1, f"Expected exactly one attempt, got {calls}"


@pytest.mark.asyncio
async def test_stale_elapsed_async_context_manager_exception_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Async context manager: max_time() must stop when handler time exceeds budget."""
    clock = FakeClock()
    patch_context_clock(monkeypatch, clock)

    sleeps: list[float] = []
    calls = 0

    async def async_sleep(seconds: float) -> None:
        sleeps.append(seconds)
        clock.value += seconds

    policy = (
        RetryPolicy()
        .attempts(3)
        .max_time(_MAX_TIME)
        .on(TimeoutError)
        .fixed_delay(_DELAY)
        .on_failure(_make_clock_advancer(clock))
        .with_sleep(clock.sleep, async_sleep)
    )

    with contextlib.suppress(TimeoutError):
        async for attempt in policy.async_iter():
            async with attempt:
                calls += 1
                raise TimeoutError("fail")

    assert sleeps == [], (
        f"No sleep expected: handler elapsed ({_HANDLER_CLOCK_VALUE}) + "
        f"delay ({_DELAY}) exceeds max_time ({_MAX_TIME}). Got: {sleeps}."
    )
    assert calls == 1, f"Expected exactly one attempt, got {calls}"
