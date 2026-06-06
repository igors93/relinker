"""Public behavioral contracts for shared retry budgets."""

from __future__ import annotations

import asyncio

import pytest

from relinker import RetryBudget, RetryPolicy
from relinker.event import RetryEvent

from ._support import FakeClock, patch_async_clock, patch_sync_clock


def test_original_successful_call_does_not_consume_shared_capacity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = FakeClock()
    patch_sync_clock(monkeypatch, clock)
    budget = RetryBudget(max_retries=1, per=10)

    successful = RetryPolicy().with_retry_budget(budget, key="api").with_sleep(clock.sleep)
    assert successful.run(lambda: "ok") == "ok"

    sleeps: list[float] = []

    def sleep(seconds: float) -> None:
        sleeps.append(seconds)
        clock.sleep(seconds)

    calls = 0

    def retry_once() -> str:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise TimeoutError("temporary")
        return "ok"

    policy = (
        RetryPolicy()
        .attempts(2)
        .on(TimeoutError)
        .with_retry_budget(budget, key="api")
        .with_sleep(sleep)
    )

    assert policy.run(retry_once) == "ok"
    assert sleeps == [0.0]


def test_same_key_shares_capacity_and_different_keys_are_isolated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = FakeClock()
    patch_sync_clock(monkeypatch, clock)
    budget = RetryBudget(max_retries=1, per=10)
    sleeps: list[float] = []

    def sleep(seconds: float) -> None:
        sleeps.append(seconds)
        clock.sleep(seconds)

    def run_one_retry(key: str) -> None:
        calls = 0

        def operation() -> str:
            nonlocal calls
            calls += 1
            if calls == 1:
                raise TimeoutError("temporary")
            return "ok"

        policy = (
            RetryPolicy()
            .attempts(2)
            .on(TimeoutError)
            .with_retry_budget(budget, key=key)
            .with_sleep(sleep)
        )
        assert policy.run(operation) == "ok"

    run_one_retry("shared")
    run_one_retry("shared")
    run_one_retry("independent")

    assert sleeps == [0.0, 10.0, 0.0]


def test_budget_never_shortens_the_policy_delay(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = FakeClock()
    patch_sync_clock(monkeypatch, clock)
    budget = RetryBudget(max_retries=1, per=10)
    events: list[RetryEvent] = []
    calls = 0

    def operation() -> str:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise TimeoutError("temporary")
        return "ok"

    policy = (
        RetryPolicy()
        .attempts(2)
        .on(TimeoutError)
        .fixed_delay(3)
        .with_retry_budget(budget, key="api")
        .with_sleep(clock.sleep)
        .on_retry(events.append)
    )

    assert policy.run(operation) == "ok"
    assert clock.value == 3
    assert events[0].delay == 3
    assert events[0].state is not None
    assert events[0].state.policy_delay == 3
    assert events[0].state.budget_delay == 0
    assert events[0].state.next_delay == 3


def test_max_time_rejects_budget_wait_without_consuming_the_new_reservation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = FakeClock()
    patch_sync_clock(monkeypatch, clock)
    budget = RetryBudget(max_retries=1, per=10)

    def one_retry() -> str:
        calls = getattr(one_retry, "calls", 0) + 1
        one_retry.calls = calls  # type: ignore[attr-defined]
        if calls == 1:
            raise TimeoutError("temporary")
        return "ok"

    first_policy = (
        RetryPolicy()
        .attempts(2)
        .on(TimeoutError)
        .with_retry_budget(budget, key="api")
        .with_sleep(clock.sleep)
    )
    assert first_policy.run(one_retry) == "ok"

    limited = (
        RetryPolicy()
        .attempts(2)
        .max_time(5)
        .on(TimeoutError)
        .with_retry_budget(budget, key="api")
        .with_sleep(clock.sleep)
        .return_result()
    )
    result = limited.run(lambda: (_ for _ in ()).throw(TimeoutError("down")))

    assert result.exhausted is True
    assert clock.value == 0

    follow_up_calls = 0
    sleeps: list[float] = []

    def sleep(seconds: float) -> None:
        sleeps.append(seconds)
        clock.sleep(seconds)

    def follow_up() -> str:
        nonlocal follow_up_calls
        follow_up_calls += 1
        if follow_up_calls == 1:
            raise TimeoutError("temporary")
        return "ok"

    follow_up_policy = (
        RetryPolicy()
        .attempts(2)
        .on(TimeoutError)
        .with_retry_budget(budget, key="api")
        .with_sleep(sleep)
    )
    assert follow_up_policy.run(follow_up) == "ok"
    assert sleeps == [10.0]


@pytest.mark.asyncio
async def test_canceled_async_wait_releases_unused_capacity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = FakeClock()
    patch_async_clock(monkeypatch, clock)
    budget = RetryBudget(max_retries=1, per=10)

    async def cancel_sleep(_: float) -> None:
        raise asyncio.CancelledError

    async def always_fails() -> None:
        raise TimeoutError("down")

    canceled_policy = (
        RetryPolicy()
        .attempts(2)
        .on(TimeoutError)
        .with_retry_budget(budget, key="api")
        .with_sleep(clock.sleep, cancel_sleep)
    )

    with pytest.raises(asyncio.CancelledError):
        await canceled_policy.run_async(always_fails)

    calls = 0
    sleeps: list[float] = []

    async def sleep(seconds: float) -> None:
        sleeps.append(seconds)
        clock.value += seconds

    async def retry_once() -> str:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise TimeoutError("temporary")
        return "ok"

    follow_up = (
        RetryPolicy()
        .attempts(2)
        .on(TimeoutError)
        .with_retry_budget(budget, key="api")
        .with_sleep(clock.sleep, sleep)
    )

    assert await follow_up.run_async(retry_once) == "ok"
    assert sleeps == [0.0]
