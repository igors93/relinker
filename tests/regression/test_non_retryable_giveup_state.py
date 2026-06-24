"""Regression tests for non-retryable exception after_giveup event state."""

from __future__ import annotations

import pytest

from relinker import RetryPolicy
from relinker.event import RetryEvent


def test_sync_non_retryable_after_giveup_emits_state() -> None:
    events: list[RetryEvent] = []
    policy = RetryPolicy().attempts(3).on(TimeoutError).on_event("after_giveup", events.append)

    def fail():
        raise ValueError("non-retryable error")

    with pytest.raises(ValueError, match="non-retryable error") as exc_info:
        policy.run(fail)

    assert len(events) == 1
    event = events[0]
    assert event.name == "after_giveup"
    assert event.error is exc_info.value
    assert event.state is not None
    assert event.state.retry_cause == "exception"
    assert event.state.will_retry is False
    assert event.state.will_stop is False
    assert event.state.last_error is exc_info.value


def test_sync_non_retryable_after_giveup_returns_result() -> None:
    events: list[RetryEvent] = []
    policy = (
        RetryPolicy()
        .attempts(3)
        .on(TimeoutError)
        .return_result()
        .on_event("after_giveup", events.append)
    )

    def fail():
        raise ValueError("non-retryable error")

    result = policy.run(fail)
    assert result.exhausted is False
    assert isinstance(result.error, ValueError)

    assert len(events) == 1
    event = events[0]
    assert event.name == "after_giveup"
    assert event.state is not None
    assert event.state.retry_cause == "exception"
    assert event.state.will_retry is False
    assert event.state.will_stop is False


@pytest.mark.asyncio
async def test_async_non_retryable_after_giveup_emits_state() -> None:
    events: list[RetryEvent] = []
    policy = RetryPolicy().attempts(3).on(TimeoutError).on_event("after_giveup", events.append)

    async def fail():
        raise ValueError("non-retryable error")

    with pytest.raises(ValueError, match="non-retryable error") as exc_info:
        await policy.run_async(fail)

    assert len(events) == 1
    event = events[0]
    assert event.name == "after_giveup"
    assert event.error is exc_info.value
    assert event.state is not None
    assert event.state.retry_cause == "exception"
    assert event.state.will_retry is False
    assert event.state.will_stop is False
    assert event.state.last_error is exc_info.value


@pytest.mark.asyncio
async def test_async_non_retryable_after_giveup_returns_result() -> None:
    events: list[RetryEvent] = []
    policy = (
        RetryPolicy()
        .attempts(3)
        .on(TimeoutError)
        .return_result()
        .on_event("after_giveup", events.append)
    )

    async def fail():
        raise ValueError("non-retryable error")

    result = await policy.run_async(fail)
    assert result.exhausted is False
    assert isinstance(result.error, ValueError)

    assert len(events) == 1
    event = events[0]
    assert event.name == "after_giveup"
    assert event.state is not None
    assert event.state.retry_cause == "exception"
    assert event.state.will_retry is False
    assert event.state.will_stop is False
