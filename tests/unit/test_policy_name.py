from __future__ import annotations

import json
import logging

import pytest

from relinker import InvalidRetryConfigError, RetryPolicy
from relinker.event import RetryEvent


def test_named_returns_new_policy_and_preserves_value() -> None:
    policy = RetryPolicy()

    named = policy.named("payments-api")

    assert named is not policy
    assert policy.name is None
    assert named.name == "payments-api"


@pytest.mark.parametrize("name", ["", "   ", 123])
def test_named_rejects_invalid_values(name: object) -> None:
    with pytest.raises(InvalidRetryConfigError):
        RetryPolicy().named(name)  # type: ignore[arg-type]


def test_unnamed_policy_keeps_policy_name_none_in_events() -> None:
    events: list[RetryEvent] = []

    RetryPolicy().attempts(1).return_result().on_giveup(events.append).run(
        lambda: (_ for _ in ()).throw(TimeoutError("down"))
    )

    assert events[-1].policy_name is None
    assert events[-1].state is not None
    assert events[-1].state.policy_name is None


def test_policy_name_appears_in_sync_events_state_and_result() -> None:
    events: list[RetryEvent] = []
    policy = (
        RetryPolicy()
        .named("payments-api")
        .attempts(2)
        .on(TimeoutError)
        .fixed_delay(0)
        .return_result()
        .on_event("before_attempt", events.append)
        .on_event("after_failure", events.append)
        .on_event("before_sleep", events.append)
        .on_event("after_success", events.append)
    )
    calls = 0

    def operation() -> str:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise TimeoutError("temporary")
        return "ok"

    result = policy.run(operation)

    assert result.policy_name == "payments-api"
    assert {event.policy_name for event in events} == {"payments-api"}
    assert {event.state.policy_name for event in events if event.state is not None} == {
        "payments-api"
    }


@pytest.mark.asyncio
async def test_policy_name_appears_in_async_events() -> None:
    events: list[RetryEvent] = []
    policy = (
        RetryPolicy()
        .named("payments-api")
        .attempts(2)
        .on(TimeoutError)
        .fixed_delay(0)
        .on_event("before_sleep", events.append)
    )
    calls = 0

    async def operation() -> str:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise TimeoutError("temporary")
        return "ok"

    assert await policy.run_async(operation) == "ok"
    assert events[0].policy_name == "payments-api"
    assert events[0].state is not None
    assert events[0].state.policy_name == "payments-api"


def test_policy_name_appears_in_decorator_events() -> None:
    events: list[RetryEvent] = []

    @RetryPolicy().named("decorated-api").attempts(1).on_success(events.append)
    def operation() -> str:
        return "ok"

    assert operation() == "ok"
    assert events[0].policy_name == "decorated-api"


def test_decorator_without_policy_name_keeps_events_unnamed() -> None:
    events: list[RetryEvent] = []

    @RetryPolicy().attempts(1).on_success(events.append)
    def operation() -> str:
        return "ok"

    assert operation() == "ok"
    assert events[0].policy_name is None


def test_policy_name_appears_in_context_manager_events() -> None:
    events: list[RetryEvent] = []
    policy = RetryPolicy().named("block-api").attempts(1).on_success(events.append)

    for attempt in policy.iter(name="block"):
        with attempt:
            attempt.set_result("ok")

    assert events[0].policy_name == "block-api"
    assert events[0].state is not None
    assert events[0].state.policy_name == "block-api"


@pytest.mark.asyncio
async def test_policy_name_appears_in_async_context_manager_events() -> None:
    events: list[RetryEvent] = []
    policy = RetryPolicy().named("async-block-api").attempts(1).on_success(events.append)

    async for attempt in policy.async_iter(name="async-block"):
        async with attempt:
            attempt.set_result("ok")

    assert events[0].policy_name == "async-block-api"
    assert events[0].state is not None
    assert events[0].state.policy_name == "async-block-api"


def test_policy_name_appears_in_plain_logging(caplog: pytest.LogCaptureFixture) -> None:
    policy = (
        RetryPolicy()
        .named("payments-api")
        .attempts(2)
        .on(TimeoutError)
        .fixed_delay(0)
        .with_logging(level=logging.WARNING)
    )

    with caplog.at_level(logging.WARNING, logger="relinker"), pytest.raises(TimeoutError):
        policy.run(lambda: (_ for _ in ()).throw(TimeoutError("down")))

    assert any("policy=payments-api" in record.message for record in caplog.records)


def test_policy_name_appears_in_structured_logging(caplog: pytest.LogCaptureFixture) -> None:
    policy = (
        RetryPolicy()
        .named("payments-api")
        .attempts(2)
        .on(TimeoutError)
        .fixed_delay(0)
        .with_structured_logging()
    )

    with caplog.at_level(logging.INFO, logger="relinker"), pytest.raises(TimeoutError):
        policy.run(lambda: (_ for _ in ()).throw(TimeoutError("down")))

    payloads = [json.loads(record.message) for record in caplog.records]
    assert {payload["policy"] for payload in payloads} == {"payments-api"}


def test_policy_name_appears_in_explain() -> None:
    explanation = RetryPolicy().named("payments-api").explain()

    assert "payments-api" in explanation
