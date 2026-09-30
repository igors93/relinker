"""Regression tests: a saturated retry budget exhausts instead of leaking.

Before the fix, when the shared budget could only schedule a retry more than
MAX_SLEEP_SECONDS away, planning raised InvalidRetryConfigError *after*
reserving a slot. Every execution leaked one queued reservation, pushing the
next available slot further away, and callers saw a configuration error for
a valid configuration.

Now the reservation is released and the execution gives up as exhausted.
"""

from __future__ import annotations

from typing import Any

import pytest

from relinker import RetryBudget, RetryPolicy, RetryResult
from relinker.event import RetryEvent


def _fail() -> None:
    raise TimeoutError("down")


async def _fail_async() -> None:
    raise TimeoutError("down")


async def _no_sleep_async(_: float) -> None:
    return None


def _saturating_policy(budget: RetryBudget, events: list[RetryEvent]) -> RetryPolicy[Any]:
    # One retry per 100_000s: the second retry can only be scheduled beyond
    # MAX_SLEEP_SECONDS (86_400s).
    return (
        RetryPolicy()
        .attempts(5)
        .on(TimeoutError)
        .no_delay()
        .with_retry_budget(budget, key="api")
        .with_sleep(lambda _: None, _no_sleep_async)
        .on_giveup(events.append)
    )


def _reservation_count(budget: RetryBudget) -> int:
    return len(budget._reservations.get("api", ()))


def test_sync_saturated_budget_exhausts_without_leaking_reservations() -> None:
    budget = RetryBudget(1, per=100_000)
    events: list[RetryEvent] = []
    policy = _saturating_policy(budget, events)

    for _ in range(3):
        with pytest.raises(TimeoutError, match="down"):
            policy.run(_fail)

    # Only the retry that actually ran holds capacity; nothing is queued.
    assert _reservation_count(budget) == 1
    assert budget.snapshot("api").queued == 0
    assert [event.name for event in events] == ["after_giveup"] * 3
    assert all(event.state is not None and event.state.will_stop for event in events)


def test_saturated_budget_reports_exhausted_result() -> None:
    budget = RetryBudget(1, per=100_000)
    policy = _saturating_policy(budget, []).return_result()

    first = policy.run(_fail)
    second = policy.run(_fail)

    assert isinstance(first, RetryResult)
    assert isinstance(second, RetryResult)
    assert first.exhausted_by_exception
    assert first.attempt_count == 2
    assert second.exhausted_by_exception
    assert second.attempt_count == 1
    assert isinstance(second.error, TimeoutError)


async def test_async_saturated_budget_exhausts_without_leaking_reservations() -> None:
    budget = RetryBudget(1, per=100_000)
    policy = _saturating_policy(budget, [])

    for _ in range(3):
        with pytest.raises(TimeoutError, match="down"):
            await policy.run_async(_fail_async)

    assert _reservation_count(budget) == 1
    assert budget.snapshot("api").queued == 0


def test_context_manager_saturated_budget_exhausts_without_leaking_reservations() -> None:
    budget = RetryBudget(1, per=100_000)
    policy = _saturating_policy(budget, [])

    for _ in range(3):
        with pytest.raises(TimeoutError, match="down"):
            for attempt in policy.iter(name="block"):
                with attempt:
                    _fail()

    assert _reservation_count(budget) == 1
    assert budget.snapshot("api").queued == 0


async def test_async_context_manager_saturated_budget_exhausts_without_leaking() -> None:
    budget = RetryBudget(1, per=100_000)
    policy = _saturating_policy(budget, [])

    for _ in range(3):
        with pytest.raises(TimeoutError, match="down"):
            async for attempt in policy.async_iter(name="block"):
                async with attempt:
                    await _fail_async()

    assert _reservation_count(budget) == 1


def test_policy_delay_plus_budget_delay_above_ceiling_releases_reservation() -> None:
    # Each part is valid on its own, but the combined wait exceeds the ceiling.
    budget = RetryBudget(1, per=10)
    policy = (
        RetryPolicy()
        .attempts(3)
        .on(TimeoutError)
        .fixed_delay(86_400)
        .with_retry_budget(budget, key="api")
        .with_sleep(lambda _: None)
        .return_result()
    )

    result = policy.run(_fail)

    assert isinstance(result, RetryResult)
    assert result.exhausted_by_exception
    assert result.attempt_count == 2
    assert _reservation_count(budget) == 1


def test_planning_failure_after_reservation_releases_it(monkeypatch: pytest.MonkeyPatch) -> None:
    import relinker.internal.retry_wait as retry_wait

    calls = {"count": 0}
    original = retry_wait.ensure_resolved_delay

    def fail_after_reservation(value: object) -> float:
        calls["count"] += 1
        if calls["count"] > 1:  # the first call validates the policy delay
            raise RuntimeError("planning failed")
        return original(value)

    monkeypatch.setattr(retry_wait, "ensure_resolved_delay", fail_after_reservation)
    budget = RetryBudget(3, per=60)
    policy = (
        RetryPolicy()
        .attempts(3)
        .on(TimeoutError)
        .no_delay()
        .with_retry_budget(budget, key="api")
        .with_sleep(lambda _: None)
    )

    with pytest.raises(RuntimeError, match="planning failed"):
        policy.run(_fail)

    assert _reservation_count(budget) == 0
