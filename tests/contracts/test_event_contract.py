"""Contracts for event order and state contents."""

from __future__ import annotations

import pytest

from relinker import RetryPolicy
from relinker.event import RetryEvent

from ._support import collect_all_events, policy_without_sleep


def _assert_retry_then_success_events(events: list[RetryEvent]) -> None:
    assert [event.name for event in events] == [
        "before_attempt",
        "after_failure",
        "before_sleep",
        "before_attempt",
        "after_success",
    ]
    assert [event.attempt_number for event in events] == [1, 1, 1, 2, 2]

    failure = events[1]
    assert isinstance(failure.error, TimeoutError)
    assert failure.state is not None
    assert failure.state.retry_cause == "exception"
    assert failure.state.will_retry is True
    assert failure.state.will_stop is False

    sleep = events[2]
    assert sleep.delay == 0
    assert sleep.state is not None
    assert sleep.state.policy_delay == 0
    assert sleep.state.budget_delay == 0
    assert sleep.state.next_delay == 0

    success = events[-1]
    assert success.value == "ok"
    assert success.state is not None
    assert success.state.has_value is True


def test_sync_event_order_is_stable() -> None:
    events: list[RetryEvent] = []
    calls = 0

    def operation() -> str:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise TimeoutError("temporary")
        return "ok"

    policy = collect_all_events(
        policy_without_sleep(RetryPolicy().attempts(2).on(TimeoutError)),
        events,
    )

    assert policy.run(operation) == "ok"
    _assert_retry_then_success_events(events)


@pytest.mark.asyncio
async def test_async_event_order_matches_sync() -> None:
    events: list[RetryEvent] = []
    calls = 0

    async def operation() -> str:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise TimeoutError("temporary")
        return "ok"

    policy = collect_all_events(
        policy_without_sleep(RetryPolicy().attempts(2).on(TimeoutError)),
        events,
    )

    assert await policy.run_async(operation) == "ok"
    _assert_retry_then_success_events(events)


def test_context_manager_event_order_matches_direct_execution() -> None:
    events: list[RetryEvent] = []
    policy = collect_all_events(
        policy_without_sleep(RetryPolicy().attempts(2).on(TimeoutError)),
        events,
    )

    for attempt in policy.iter(name="event-contract"):
        with attempt:
            if attempt.number == 1:
                raise TimeoutError("temporary")
            attempt.set_result("ok")

    _assert_retry_then_success_events(events)


def test_exhaustion_emits_giveup_after_failure() -> None:
    events: list[RetryEvent] = []
    policy = collect_all_events(
        policy_without_sleep(RetryPolicy().attempts(1).on(TimeoutError).return_result()),
        events,
    )

    result = policy.run(lambda: (_ for _ in ()).throw(TimeoutError("down")))

    assert result.exhausted is True
    assert [event.name for event in events] == [
        "before_attempt",
        "after_failure",
        "after_giveup",
    ]
    assert events[-1].state is not None
    assert events[-1].state.will_stop is True
    assert events[-1].state.retry_cause == "exception"


def test_rejected_result_does_not_emit_after_failure() -> None:
    events: list[RetryEvent] = []
    values = iter(["waiting", "ready"])
    policy = collect_all_events(
        policy_without_sleep(
            RetryPolicy().attempts(2).retry_if_result(lambda value: value == "waiting")
        ),
        events,
    )

    assert policy.run(lambda: next(values)) == "ready"
    assert [event.name for event in events] == [
        "before_attempt",
        "before_sleep",
        "before_attempt",
        "after_success",
    ]
