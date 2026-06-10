"""Contracts for give-up state emitted by retry context managers."""

from __future__ import annotations

import pytest

from relinker import RetryPolicy
from relinker.event import RetryEvent

from ._support import collect_all_events, policy_without_sleep


def test_block_non_retryable_giveup_does_not_report_stop_strategy_fired() -> None:
    events: list[RetryEvent] = []
    policy = collect_all_events(
        policy_without_sleep(RetryPolicy().attempts(3).on(TimeoutError)),
        events,
    )

    with pytest.raises(ValueError, match="permanent"):
        for attempt in policy.iter(name="block-non-retryable"):
            with attempt:
                raise ValueError("permanent")

    giveup = next(event for event in events if event.name == "after_giveup")
    assert giveup.state is not None
    assert giveup.state.retry_cause == "exception"
    assert giveup.state.will_retry is False
    assert giveup.state.will_stop is False


@pytest.mark.asyncio
async def test_async_block_non_retryable_giveup_does_not_report_stop_strategy_fired() -> None:
    events: list[RetryEvent] = []
    policy = collect_all_events(
        policy_without_sleep(RetryPolicy().attempts(3).on(TimeoutError)),
        events,
    )

    with pytest.raises(ValueError, match="permanent"):
        async for attempt in policy.async_iter(name="async-block-non-retryable"):
            async with attempt:
                raise ValueError("permanent")

    giveup = next(event for event in events if event.name == "after_giveup")
    assert giveup.state is not None
    assert giveup.state.retry_cause == "exception"
    assert giveup.state.will_retry is False
    assert giveup.state.will_stop is False


def test_block_retryable_exhaustion_reports_stop_strategy_fired() -> None:
    events: list[RetryEvent] = []
    policy = collect_all_events(
        policy_without_sleep(RetryPolicy().attempts(1).on(TimeoutError).return_result()),
        events,
    )

    iterator = policy.iter(name="block-exhausted")
    for attempt in iterator:
        with attempt:
            raise TimeoutError("down")

    giveup = next(event for event in events if event.name == "after_giveup")
    assert giveup.state is not None
    assert giveup.state.retry_cause == "exception"
    assert giveup.state.will_retry is False
    assert giveup.state.will_stop is True


@pytest.mark.asyncio
async def test_async_block_retryable_exhaustion_reports_stop_strategy_fired() -> None:
    events: list[RetryEvent] = []
    policy = collect_all_events(
        policy_without_sleep(RetryPolicy().attempts(1).on(TimeoutError).return_result()),
        events,
    )

    iterator = policy.async_iter(name="async-block-exhausted")
    async for attempt in iterator:
        async with attempt:
            raise TimeoutError("down")

    giveup = next(event for event in events if event.name == "after_giveup")
    assert giveup.state is not None
    assert giveup.state.retry_cause == "exception"
    assert giveup.state.will_retry is False
    assert giveup.state.will_stop is True
