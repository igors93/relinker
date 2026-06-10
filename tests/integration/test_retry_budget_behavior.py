"""Integration tests for Retry Budget behavior through the public API."""

from __future__ import annotations

import asyncio

import pytest

from relinker import InvalidRetryConfigError, RetryBudget, RetryPolicy
from relinker.event import RetryEvent


def _no_sleep(_: float) -> None:
    pass


async def _async_no_sleep(_: float) -> None:
    pass


def test_retry_budget_initial_snapshot_is_empty_and_available() -> None:
    snapshot = RetryBudget(max_retries=2, per=60).snapshot("api")
    assert snapshot.active == 0
    assert snapshot.queued == 0
    assert snapshot.available == 2
    assert snapshot.next_available_in == 0


def test_successful_original_call_does_not_consume_retry_budget() -> None:
    budget = RetryBudget(max_retries=1, per=60)
    policy = RetryPolicy().with_retry_budget(budget, key="api")
    assert policy.run(lambda: "ok") == "ok"
    assert budget.snapshot("api").available == 1


def test_one_additional_attempt_consumes_public_budget_capacity() -> None:
    budget = RetryBudget(max_retries=1, per=60)
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
        .with_retry_budget(budget, key="api")
        .with_sleep(_no_sleep)
    )
    assert policy.run(operation) == "ok"
    snapshot = budget.snapshot("api")
    assert snapshot.available == 0
    assert snapshot.active + snapshot.queued == 1


def test_non_retryable_error_does_not_consume_retry_budget() -> None:
    budget = RetryBudget(max_retries=1, per=60)
    policy = (
        RetryPolicy()
        .attempts(3)
        .on(TimeoutError)
        .with_retry_budget(budget, key="api")
        .with_sleep(_no_sleep)
    )
    with pytest.raises(ValueError):
        policy.run(lambda: (_ for _ in ()).throw(ValueError("permanent")))
    assert budget.snapshot("api").available == 1


def test_same_budget_key_adds_wait_after_capacity_is_reserved() -> None:
    budget = RetryBudget(max_retries=1, per=60)

    def run_once(events: list[RetryEvent]) -> None:
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
            .with_retry_budget(budget, key="shared")
            .with_sleep(_no_sleep)
            .on_retry(events.append)
        )
        assert policy.run(operation) == "ok"

    first_events: list[RetryEvent] = []
    second_events: list[RetryEvent] = []
    run_once(first_events)
    run_once(second_events)
    assert first_events[0].state is not None
    assert first_events[0].state.budget_delay == 0
    assert second_events[0].state is not None
    assert second_events[0].state.budget_delay > 0


def test_different_budget_keys_keep_capacity_independent() -> None:
    budget = RetryBudget(max_retries=1, per=60)

    def consume(key: str) -> float:
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
            .with_retry_budget(budget, key=key)
            .with_sleep(_no_sleep)
            .on_retry(events.append)
        )
        assert policy.run(operation) == "ok"
        assert events[0].state is not None
        return events[0].state.budget_delay or 0

    assert consume("a") == 0
    assert consume("b") == 0


@pytest.mark.asyncio
async def test_cancelled_async_sleep_releases_unused_budget_reservation() -> None:
    budget = RetryBudget(max_retries=1, per=60)

    async def cancel_sleep(_: float) -> None:
        raise asyncio.CancelledError

    async def operation() -> None:
        raise TimeoutError("down")

    policy = (
        RetryPolicy()
        .attempts(2)
        .on(TimeoutError)
        .with_retry_budget(budget, key="api")
        .with_sleep(_no_sleep, cancel_sleep)
    )
    with pytest.raises(asyncio.CancelledError):
        await policy.run_async(operation)
    assert budget.snapshot("api").available == 1


def test_sync_sleep_failure_releases_unused_budget_reservation() -> None:
    budget = RetryBudget(max_retries=1, per=60)

    def broken_sleep(_: float) -> None:
        raise RuntimeError("sleep failed")

    policy = (
        RetryPolicy()
        .attempts(2)
        .on(TimeoutError)
        .with_retry_budget(budget, key="api")
        .with_sleep(broken_sleep, _async_no_sleep)
    )
    with pytest.raises(RuntimeError, match="sleep failed"):
        policy.run(lambda: (_ for _ in ()).throw(TimeoutError("down")))
    assert budget.snapshot("api").available == 1


def test_immediate_time_stop_does_not_reserve_budget_capacity() -> None:
    budget = RetryBudget(max_retries=1, per=60)
    policy = (
        RetryPolicy()
        .attempts(3)
        .max_time(0)
        .on(TimeoutError)
        .with_retry_budget(budget, key="api")
        .with_sleep(_no_sleep)
        .return_result()
    )
    result = policy.run(lambda: (_ for _ in ()).throw(TimeoutError("down")))
    assert result.exhausted is True
    assert budget.snapshot("api").available == 1


def test_retry_budget_rejects_blank_public_keys() -> None:
    budget = RetryBudget(max_retries=1, per=60)
    with pytest.raises(InvalidRetryConfigError):
        RetryPolicy().with_retry_budget(budget, key="   ")
    with pytest.raises(InvalidRetryConfigError):
        budget.snapshot("")
