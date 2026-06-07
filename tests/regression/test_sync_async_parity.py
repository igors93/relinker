"""Regression contracts for sync, async, and block execution parity."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from relinker import RetryPolicy
from relinker.event import RetryEvent

Trace = list[tuple[str, int]]


def _record_trace(trace: Trace) -> Callable[[RetryEvent], None]:
    def record(event: RetryEvent) -> None:
        trace.append((event.name, event.attempt_number))

    return record


def _trace_policy(trace: Trace) -> RetryPolicy[str]:
    policy: RetryPolicy[str] = RetryPolicy[str]().attempts(3).on(TimeoutError).no_delay()
    for name in (
        "before_attempt",
        "after_failure",
        "before_sleep",
        "after_success",
        "after_giveup",
    ):
        policy = policy.on_event(name, _record_trace(trace))
    return policy


@pytest.mark.asyncio
async def test_sync_and_async_success_after_two_failures_have_same_event_trace() -> None:
    sync_trace: Trace = []
    async_trace: Trace = []
    sync_calls = 0
    async_calls = 0

    def sync_operation() -> str:
        nonlocal sync_calls
        sync_calls += 1
        if sync_calls < 3:
            raise TimeoutError("temporary")
        return "ok"

    async def async_operation() -> str:
        nonlocal async_calls
        async_calls += 1
        if async_calls < 3:
            raise TimeoutError("temporary")
        return "ok"

    assert _trace_policy(sync_trace).run(sync_operation) == "ok"
    assert await _trace_policy(async_trace).run_async(async_operation) == "ok"
    assert sync_calls == async_calls == 3
    assert sync_trace == async_trace
    assert sync_trace == [
        ("before_attempt", 1),
        ("after_failure", 1),
        ("before_sleep", 1),
        ("before_attempt", 2),
        ("after_failure", 2),
        ("before_sleep", 2),
        ("before_attempt", 3),
        ("after_success", 3),
    ]


@pytest.mark.asyncio
async def test_sync_and_async_blocks_success_after_two_failures_have_same_event_trace() -> None:
    sync_trace: Trace = []
    async_trace: Trace = []
    sync_calls = 0
    async_calls = 0

    sync_iterator = _trace_policy(sync_trace).iter(name="sync-block-parity")
    for attempt in sync_iterator:
        with attempt:
            sync_calls += 1
            if sync_calls < 3:
                raise TimeoutError("temporary")
            attempt.set_result("ok")

    async_iterator = _trace_policy(async_trace).async_iter(name="async-block-parity")
    async for attempt in async_iterator:
        async with attempt:
            async_calls += 1
            if async_calls < 3:
                raise TimeoutError("temporary")
            attempt.set_result("ok")

    assert sync_iterator.result is not None
    assert async_iterator.result is not None
    assert sync_iterator.result.value == async_iterator.result.value == "ok"
    assert sync_calls == async_calls == 3
    assert sync_trace == async_trace
