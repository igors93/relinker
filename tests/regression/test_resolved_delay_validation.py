from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Any

import pytest

from relinker import InvalidRetryConfigError, RetryBudget, RetryPolicy
from relinker.event import RetryEvent


@dataclass(frozen=True)
class StaticDelay:
    value: object

    def next_delay(self, attempt_number: int) -> float:
        del attempt_number
        return self.value  # type: ignore[return-value]


INVALID_DELAYS = (
    pytest.param(float("inf"), id="inf"),
    pytest.param(float("nan"), id="nan"),
    pytest.param(-0.5, id="negative"),
    pytest.param(True, id="bool"),
    pytest.param("bad", id="invalid-type"),
)


def _always_fails(calls: list[str]) -> None:
    calls.append("call")
    raise ValueError("retry")


@pytest.mark.parametrize("delay", INVALID_DELAYS)
def test_sync_resolved_delay_is_validated_before_budget_events_sleep_and_retry(
    delay: object,
) -> None:
    calls: list[str] = []
    sleeps: list[Any] = []
    events: list[RetryEvent] = []
    budget = RetryBudget(max_retries=1, per=10)
    policy = (
        RetryPolicy(delay_strategy=StaticDelay(delay))
        .attempts(2)
        .on(ValueError)
        .with_retry_budget(budget, key="api")
        .with_sleep(sleeps.append)
        .on_retry(events.append)
    )

    with pytest.raises(
        InvalidRetryConfigError,
        match="resolved delay must be a finite non-negative number",
    ):
        policy.run(lambda: _always_fails(calls))

    snapshot = budget.snapshot("api")
    assert calls == ["call"]
    assert sleeps == []
    assert events == []
    assert snapshot.active == 0
    assert snapshot.queued == 0
    assert snapshot.available == snapshot.capacity


@pytest.mark.parametrize("delay", INVALID_DELAYS)
async def test_async_resolved_delay_is_validated_before_sleep_and_retry(delay: object) -> None:
    calls: list[str] = []
    sleeps: list[Any] = []

    async def sleep(seconds: float) -> None:
        sleeps.append(seconds)

    async def task() -> None:
        _always_fails(calls)

    policy = (
        RetryPolicy(delay_strategy=StaticDelay(delay))
        .attempts(2)
        .on(ValueError)
        .with_sleep(lambda seconds: None, sleep)
    )

    with pytest.raises(
        InvalidRetryConfigError,
        match="resolved delay must be a finite non-negative number",
    ):
        await policy.run_async(task)

    assert calls == ["call"]
    assert sleeps == []


def test_exponential_overflow_saturates_instead_of_raising() -> None:
    # Fix 4: overflow now saturates at _SAFE_DELAY_CAP rather than producing inf
    # and raising InvalidRetryConfigError.  All attempts still complete.
    from relinker.delays.exponential import _SAFE_DELAY_CAP

    calls: list[str] = []
    sleeps: list[float] = []
    policy = (
        RetryPolicy()
        .attempts(3)
        .on(ValueError)
        .exponential_delay(base=sys.float_info.max, factor=sys.float_info.max)
        .with_sleep(sleeps.append)
    )

    with pytest.raises(ValueError):
        policy.run(lambda: _always_fails(calls))

    assert calls == ["call", "call", "call"]
    assert len(sleeps) == 2
    # Both attempts saturate: base itself exceeds _SAFE_DELAY_CAP so is capped immediately.
    assert sleeps[0] == _SAFE_DELAY_CAP
    assert sleeps[1] == _SAFE_DELAY_CAP


def test_additive_delay_above_ceiling_is_rejected_before_sleep() -> None:
    # Values above MAX_SLEEP_SECONDS are now rejected at construction time.
    # The sleeper is never called and the function under test is not even invoked.
    import math

    from relinker.internal.validation import MAX_SLEEP_SECONDS

    above = math.nextafter(MAX_SLEEP_SECONDS, math.inf)
    with pytest.raises(InvalidRetryConfigError):
        RetryPolicy().fixed_delay(above)


def test_sync_context_manager_validates_resolved_delay_before_sleep() -> None:
    sleeps: list[Any] = []
    policy = (
        RetryPolicy(delay_strategy=StaticDelay(float("inf")))
        .attempts(2)
        .on(ValueError)
        .with_sleep(sleeps.append)
    )

    with pytest.raises(
        InvalidRetryConfigError,
        match="resolved delay must be a finite non-negative number",
    ):
        for attempt in policy:
            with attempt:
                raise ValueError("retry")

    assert sleeps == []


async def test_async_context_manager_validates_resolved_delay_before_sleep() -> None:
    sleeps: list[Any] = []

    async def sleep(seconds: float) -> None:
        sleeps.append(seconds)

    policy = (
        RetryPolicy(delay_strategy=StaticDelay(float("inf")))
        .attempts(2)
        .on(ValueError)
        .with_sleep(lambda seconds: None, sleep)
    )

    with pytest.raises(
        InvalidRetryConfigError,
        match="resolved delay must be a finite non-negative number",
    ):
        async for attempt in policy:
            async with attempt:
                raise ValueError("retry")

    assert sleeps == []
