"""Observable event and RetryState behavioral contracts."""

from __future__ import annotations

import pytest

from relinker import RetryPolicy
from relinker.event import RetryEvent

from ._support import collect_all_events, policy_without_sleep


def test_sync_non_retryable_failure_does_not_fire_stop_strategy() -> None:
    events: list[RetryEvent] = []
    calls = 0

    def operation() -> None:
        nonlocal calls
        calls += 1
        raise ValueError("permanent")

    policy = collect_all_events(
        policy_without_sleep(RetryPolicy().attempts(3).on(TimeoutError)),
        events,
    )

    with pytest.raises(ValueError, match="permanent"):
        policy.run(operation)

    assert calls == 1
    assert [event.name for event in events] == [
        "before_attempt",
        "after_failure",
        "after_giveup",
    ]
    failure = events[1]
    assert failure.state is not None
    assert failure.state.will_retry is False
    assert failure.state.will_stop is False


@pytest.mark.asyncio
async def test_async_non_retryable_failure_does_not_fire_stop_strategy() -> None:
    events: list[RetryEvent] = []
    calls = 0

    async def operation() -> None:
        nonlocal calls
        calls += 1
        raise ValueError("permanent")

    policy = collect_all_events(
        policy_without_sleep(RetryPolicy().attempts(3).on(TimeoutError)),
        events,
    )

    with pytest.raises(ValueError, match="permanent"):
        await policy.run_async(operation)

    assert calls == 1
    assert [event.name for event in events] == [
        "before_attempt",
        "after_failure",
        "after_giveup",
    ]
    failure = events[1]
    assert failure.state is not None
    assert failure.state.will_retry is False
    assert failure.state.will_stop is False


def test_block_non_retryable_failure_does_not_fire_stop_strategy() -> None:
    events: list[RetryEvent] = []
    policy = collect_all_events(
        policy_without_sleep(RetryPolicy().attempts(3).on(TimeoutError)),
        events,
    )

    with pytest.raises(ValueError, match="permanent"):
        for attempt in policy.iter(name="block-probe"):
            with attempt:
                raise ValueError("permanent")

    failure = next(event for event in events if event.name == "after_failure")
    assert failure.state is not None
    assert failure.state.will_retry is False
    assert failure.state.will_stop is False


def test_retryable_failure_reports_will_retry_before_sleep() -> None:
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

    failure = next(event for event in events if event.name == "after_failure")
    assert failure.state is not None
    assert failure.state.will_retry is True
    assert failure.state.will_stop is False


def test_exhausted_failure_reports_will_stop() -> None:
    events: list[RetryEvent] = []
    policy = collect_all_events(
        policy_without_sleep(RetryPolicy().attempts(1).on(TimeoutError).return_result()),
        events,
    )

    result = policy.run(lambda: (_ for _ in ()).throw(TimeoutError("down")))

    assert result.exhausted is True
    failure = next(event for event in events if event.name == "after_failure")
    assert failure.state is not None
    assert failure.state.will_retry is False
    assert failure.state.will_stop is True


def test_result_retry_does_not_emit_after_failure() -> None:
    events: list[RetryEvent] = []
    values = iter(["waiting", "ready"])
    policy = collect_all_events(
        policy_without_sleep(
            RetryPolicy().attempts(2).retry_if_result(lambda value: value == "waiting")
        ),
        events,
    )

    assert policy.run(lambda: next(values)) == "ready"
    assert "after_failure" not in [event.name for event in events]
    assert [event.name for event in events] == [
        "before_attempt",
        "before_sleep",
        "before_attempt",
        "after_success",
    ]


def test_accepted_result_emits_exactly_one_success_event() -> None:
    events: list[RetryEvent] = []
    policy = collect_all_events(RetryPolicy(), events)

    assert policy.run(lambda: "ok") == "ok"
    successes = [event for event in events if event.name == "after_success"]
    assert len(successes) == 1
    assert successes[0].value == "ok"


def test_before_sleep_contains_resolved_delay_breakdown() -> None:
    events: list[RetryEvent] = []
    calls = 0

    def operation() -> str:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise TimeoutError("temporary")
        return "ok"

    policy = collect_all_events(
        policy_without_sleep(RetryPolicy().attempts(2).on(TimeoutError).fixed_delay(2.5)),
        events,
    )
    assert policy.run(operation) == "ok"

    before_sleep = next(event for event in events if event.name == "before_sleep")
    assert before_sleep.delay == 2.5
    assert before_sleep.state is not None
    assert before_sleep.state.policy_delay == 2.5
    assert before_sleep.state.budget_delay == 0
    assert before_sleep.state.next_delay == 2.5


def test_policy_name_is_propagated_to_event_and_state() -> None:
    events: list[RetryEvent] = []
    policy = collect_all_events(RetryPolicy().named("payments"), events)

    assert policy.run(lambda: "ok") == "ok"
    assert events
    assert all(event.policy_name == "payments" for event in events)
    assert all(event.state is None or event.state.policy_name == "payments" for event in events)


def test_isolated_handler_failure_does_not_abort_execution() -> None:
    observed: list[str] = []

    def broken(_: RetryEvent) -> None:
        raise RuntimeError("observer failed")

    policy = (
        RetryPolicy()
        .on_event("before_attempt", broken, failure_mode="isolate")
        .on_success(lambda _: observed.append("success"))
    )

    assert policy.run(lambda: "ok") == "ok"
    assert observed == ["success"]


def test_propagating_handler_failure_aborts_before_user_call() -> None:
    calls = 0

    def broken(_: RetryEvent) -> None:
        raise RuntimeError("critical hook failed")

    def operation() -> str:
        nonlocal calls
        calls += 1
        return "ok"

    policy = RetryPolicy().on_event("before_attempt", broken)

    with pytest.raises(RuntimeError, match="critical hook failed"):
        policy.run(operation)
    assert calls == 0


def test_handlers_for_the_same_event_run_in_registration_order() -> None:
    order: list[str] = []
    policy = (
        RetryPolicy()
        .on_success(lambda _: order.append("first"))
        .on_success(lambda _: order.append("second"))
        .on_success(lambda _: order.append("third"))
    )

    assert policy.run(lambda: "ok") == "ok"
    assert order == ["first", "second", "third"]
