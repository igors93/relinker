"""Regression contracts for control-flow exceptions and retry-budget cleanup."""

from __future__ import annotations

import asyncio

import pytest

from relinker import RetryBudget, RetryPolicy
from relinker.event import RetryEvent


def test_keyboard_interrupt_and_system_exit_are_not_retried_or_wrapped() -> None:
    for error in (KeyboardInterrupt(), SystemExit(2)):
        calls = 0
        events: list[tuple[str, int]] = []

        def record(
            event: RetryEvent,
            events: list[tuple[str, int]] = events,
        ) -> None:
            events.append((event.name, event.attempt_number))

        def operation(error: BaseException = error) -> None:
            nonlocal calls
            calls += 1
            raise error

        policy = (
            RetryPolicy()
            .attempts(3)
            .return_result()
            .on_before_attempt(record)
            .on_failure(record)
            .on_giveup(record)
        )

        with pytest.raises(type(error)):
            policy.run(operation)

        assert calls == 1
        assert events == [("before_attempt", 1)]


@pytest.mark.asyncio
async def test_async_cancelled_error_is_not_retried_or_wrapped() -> None:
    calls = 0
    events: list[tuple[str, int]] = []

    def record(event: RetryEvent) -> None:
        events.append((event.name, event.attempt_number))

    async def operation() -> None:
        nonlocal calls
        calls += 1
        raise asyncio.CancelledError

    policy = (
        RetryPolicy()
        .attempts(3)
        .return_result()
        .on_before_attempt(record)
        .on_failure(record)
        .on_giveup(record)
    )

    with pytest.raises(asyncio.CancelledError):
        await policy.run_async(operation)

    assert calls == 1
    assert events == [("before_attempt", 1)]


@pytest.mark.asyncio
async def test_async_cancelled_sleep_releases_retry_budget_reservation() -> None:
    budget = RetryBudget(max_retries=1, per=10)
    calls = 0

    async def operation() -> None:
        nonlocal calls
        calls += 1
        raise TimeoutError("temporary")

    async def cancel_sleep(_: float) -> None:
        raise asyncio.CancelledError

    policy = (
        RetryPolicy()
        .attempts(2)
        .on(TimeoutError)
        .with_retry_budget(budget, key="api")
        .with_sleep(lambda _: None, cancel_sleep)
    )

    with pytest.raises(asyncio.CancelledError):
        await policy.run_async(operation)

    assert calls == 1
    assert budget._reservations == {}


def test_before_sleep_handler_error_releases_retry_budget_reservation() -> None:
    budget = RetryBudget(max_retries=1, per=10)
    calls = 0

    def operation() -> None:
        nonlocal calls
        calls += 1
        raise TimeoutError("temporary")

    def handler(_: RetryEvent) -> None:
        raise RuntimeError("handler failed")

    policy = (
        RetryPolicy()
        .attempts(2)
        .on(TimeoutError)
        .with_retry_budget(budget, key="api")
        .on_retry(handler)
    )

    with pytest.raises(RuntimeError, match="handler failed"):
        policy.run(operation)

    assert calls == 1
    assert budget._reservations == {}
