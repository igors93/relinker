from __future__ import annotations

import asyncio
from dataclasses import dataclass

import pytest

from relinker import RetryBudget, RetryPolicy, TryAgain
from relinker.event import RetryEvent


@dataclass
class FakeClock:
    value: float = 0.0

    def now(self) -> float:
        return self.value

    def sleep(self, seconds: float) -> None:
        self.value += seconds

    async def async_sleep(self, seconds: float) -> None:
        self.value += seconds


def patch_sync_clock(monkeypatch: pytest.MonkeyPatch, clock: FakeClock) -> None:
    monkeypatch.setattr("relinker.executors.sync.now", clock.now)
    monkeypatch.setattr("relinker.internal.executor_helpers.now", clock.now)
    monkeypatch.setattr("relinker.internal.retry_wait.now", clock.now)


def patch_async_clock(monkeypatch: pytest.MonkeyPatch, clock: FakeClock) -> None:
    monkeypatch.setattr("relinker.executors.async_.now", clock.now)
    monkeypatch.setattr("relinker.internal.executor_helpers.now", clock.now)
    monkeypatch.setattr("relinker.internal.retry_wait.now", clock.now)


def test_first_attempt_does_not_consume_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    clock = FakeClock()
    patch_sync_clock(monkeypatch, clock)
    budget = RetryBudget(max_retries=1, per=10)
    policy = RetryPolicy().with_retry_budget(budget, key="api")

    assert policy.run(lambda: "ok") == "ok"
    assert budget._reservations == {}


def test_sync_exception_budget_extends_wait_and_exposes_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = FakeClock()
    patch_sync_clock(monkeypatch, clock)
    budget = RetryBudget(max_retries=1, per=10)
    sleeps: list[float] = []
    events: list[RetryEvent] = []
    calls = 0

    def sleep(seconds: float) -> None:
        sleeps.append(seconds)
        clock.sleep(seconds)

    def task() -> str:
        nonlocal calls
        calls += 1
        if calls < 4:
            raise TimeoutError("temporary")
        return "ok"

    policy = (
        RetryPolicy()
        .attempts(4)
        .on(TimeoutError)
        .fixed_delay(2)
        .with_retry_budget(budget, key="api")
        .with_sleep(sleep)
        .on_retry(events.append)
    )

    assert policy.run(task) == "ok"
    assert sleeps == [2.0, 10.0, 10.0]
    assert [event.delay for event in events] == sleeps
    assert events[0].state is not None
    assert events[0].state.policy_delay == 2.0
    assert events[0].state.budget_delay == 0.0
    assert events[0].state.next_delay == 2.0
    assert events[1].state is not None
    assert events[1].state.policy_delay == 2.0
    assert events[1].state.budget_delay == 8.0
    assert events[1].state.next_delay == 10.0


def test_try_again_and_result_retry_consume_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    clock = FakeClock()
    patch_sync_clock(monkeypatch, clock)
    budget = RetryBudget(max_retries=1, per=5)
    sleeps: list[float] = []

    def sleep(seconds: float) -> None:
        sleeps.append(seconds)
        clock.sleep(seconds)

    calls = 0

    def explicit() -> str:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise TryAgain("again")
        return "ok"

    policy = RetryPolicy().attempts(2).with_retry_budget(budget, key="shared").with_sleep(sleep)
    assert policy.run(explicit) == "ok"

    values = iter([False, True])
    result_policy = (
        RetryPolicy()
        .attempts(2)
        .retry_if_result(lambda value: value is False)
        .with_retry_budget(budget, key="shared")
        .with_sleep(sleep)
    )
    assert result_policy.run(lambda: next(values)) is True
    assert sleeps == [0.0, 5.0]


def test_max_time_releases_rejected_reservation(monkeypatch: pytest.MonkeyPatch) -> None:
    clock = FakeClock()
    patch_sync_clock(monkeypatch, clock)
    budget = RetryBudget(max_retries=1, per=10)
    original = budget._reserve("api", current_time=0, not_before=0)
    policy = (
        RetryPolicy()
        .attempts(3)
        .max_time(5)
        .on(TimeoutError)
        .with_retry_budget(budget, key="api")
        .return_result()
        .with_sleep(clock.sleep)
    )

    result = policy.run(lambda: (_ for _ in ()).throw(TimeoutError("down")))

    assert result.exhausted is True
    assert clock.value == 0
    assert [item.token for item in budget._reservations["api"]] == [original.token]
    follow_up = budget._reserve("api", current_time=0, not_before=0)
    assert follow_up.scheduled_at == 10


def test_interrupted_sync_sleep_releases_reservation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = FakeClock()
    patch_sync_clock(monkeypatch, clock)
    budget = RetryBudget(max_retries=1, per=10)

    def interrupt(_: float) -> None:
        raise KeyboardInterrupt

    policy = (
        RetryPolicy()
        .attempts(2)
        .on(TimeoutError)
        .with_retry_budget(budget, key="api")
        .with_sleep(interrupt)
    )

    with pytest.raises(KeyboardInterrupt):
        policy.run(lambda: (_ for _ in ()).throw(TimeoutError("down")))
    assert budget._reservations == {}


@pytest.mark.asyncio
async def test_async_budget_and_cancellation_release(monkeypatch: pytest.MonkeyPatch) -> None:
    clock = FakeClock()
    patch_async_clock(monkeypatch, clock)
    budget = RetryBudget(max_retries=1, per=10)
    calls = 0

    async def task() -> str:
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
        .with_sleep(clock.sleep, clock.async_sleep)
    )
    assert await policy.run_async(task) == "ok"

    canceled_budget = RetryBudget(max_retries=1, per=10)

    async def cancel_sleep(_: float) -> None:
        raise asyncio.CancelledError

    canceled_policy = (
        RetryPolicy()
        .attempts(2)
        .on(TimeoutError)
        .with_retry_budget(canceled_budget, key="api")
        .with_sleep(clock.sleep, cancel_sleep)
    )
    with pytest.raises(asyncio.CancelledError):
        await canceled_policy.run_async(task_that_fails)
    assert canceled_budget._reservations == {}


async def task_that_fails() -> None:
    raise TimeoutError("down")


def test_sync_context_manager_uses_same_budget_wait(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = FakeClock()
    monkeypatch.setattr("relinker.context.now", clock.now)
    monkeypatch.setattr("relinker.internal.executor_helpers.now", clock.now)
    monkeypatch.setattr("relinker.internal.retry_wait.now", clock.now)
    budget = RetryBudget(max_retries=1, per=10)
    sleeps: list[float] = []

    def sleep(seconds: float) -> None:
        sleeps.append(seconds)
        clock.sleep(seconds)

    policy = (
        RetryPolicy()
        .attempts(3)
        .on(TimeoutError)
        .with_retry_budget(budget, key="api")
        .with_sleep(sleep)
    )
    iterator = policy.iter()
    for attempt in iterator:
        with attempt:
            if attempt.number < 3:
                raise TimeoutError("temporary")

    assert sleeps == [0.0, 10.0]
    assert iterator.result is not None
    assert iterator.result.succeeded is True


@pytest.mark.asyncio
async def test_async_context_manager_uses_same_budget_wait(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = FakeClock()
    monkeypatch.setattr("relinker.context.now", clock.now)
    monkeypatch.setattr("relinker.internal.executor_helpers.now", clock.now)
    monkeypatch.setattr("relinker.internal.retry_wait.now", clock.now)
    budget = RetryBudget(max_retries=1, per=10)
    sleeps: list[float] = []

    async def sleep(seconds: float) -> None:
        sleeps.append(seconds)
        clock.value += seconds

    policy = (
        RetryPolicy()
        .attempts(3)
        .on(TimeoutError)
        .with_retry_budget(budget, key="api")
        .with_sleep(clock.sleep, sleep)
    )
    iterator = policy.async_iter()
    async for attempt in iterator:
        async with attempt:
            if attempt.number < 3:
                raise TimeoutError("temporary")

    assert sleeps == [0.0, 10.0]
    assert iterator.result is not None
    assert iterator.result.succeeded is True


def test_no_budget_keeps_delay_behavior_and_exposes_zero_budget_delay(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = FakeClock()
    patch_sync_clock(monkeypatch, clock)
    events: list[RetryEvent] = []
    calls = 0

    def task() -> str:
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
        .with_sleep(clock.sleep)
        .on_retry(events.append)
    )
    assert policy.run(task) == "ok"
    assert clock.value == 3
    assert events[0].delay == 3
    assert events[0].state is not None
    assert events[0].state.policy_delay == 3
    assert events[0].state.budget_delay == 0
    assert events[0].state.next_delay == 3


def test_sync_context_interrupted_sleep_releases_reservation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = FakeClock()
    monkeypatch.setattr("relinker.context.now", clock.now)
    monkeypatch.setattr("relinker.internal.executor_helpers.now", clock.now)
    monkeypatch.setattr("relinker.internal.retry_wait.now", clock.now)
    budget = RetryBudget(max_retries=1, per=10)

    def interrupt(_: float) -> None:
        raise KeyboardInterrupt

    policy = (
        RetryPolicy()
        .attempts(2)
        .on(TimeoutError)
        .with_retry_budget(budget, key="api")
        .with_sleep(interrupt)
    )

    with pytest.raises(KeyboardInterrupt):
        for attempt in policy:
            with attempt:
                raise TimeoutError("down")
    assert budget._reservations == {}


@pytest.mark.asyncio
async def test_async_context_canceled_sleep_releases_reservation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = FakeClock()
    monkeypatch.setattr("relinker.context.now", clock.now)
    monkeypatch.setattr("relinker.internal.executor_helpers.now", clock.now)
    monkeypatch.setattr("relinker.internal.retry_wait.now", clock.now)
    budget = RetryBudget(max_retries=1, per=10)

    async def cancel(_: float) -> None:
        raise asyncio.CancelledError

    policy = (
        RetryPolicy()
        .attempts(2)
        .on(TimeoutError)
        .with_retry_budget(budget, key="api")
        .with_sleep(clock.sleep, cancel)
    )

    with pytest.raises(asyncio.CancelledError):
        async for attempt in policy:
            async with attempt:
                raise TimeoutError("down")
    assert budget._reservations == {}


@pytest.mark.asyncio
async def test_concurrent_async_plans_receive_non_overlapping_capacity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = FakeClock()
    patch_async_clock(monkeypatch, clock)
    budget = RetryBudget(max_retries=2, per=10)
    sleeps: list[float] = []

    async def sleep(seconds: float) -> None:
        sleeps.append(seconds)

    async def task() -> None:
        raise TimeoutError("down")

    policy = (
        RetryPolicy()
        .attempts(2)
        .on(TimeoutError)
        .with_retry_budget(budget, key="api")
        .with_sleep(clock.sleep, sleep)
        .return_result()
    )
    await asyncio.gather(*(policy.run_async(task) for _ in range(6)))
    assert sorted(sleeps) == [0.0, 0.0, 10.0, 10.0, 20.0, 20.0]
