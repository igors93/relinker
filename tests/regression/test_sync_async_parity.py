"""Regression contracts for sync, async, and block execution parity."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from relinker import RetryPolicy, RetryResult, TryAgain
from relinker.event import RetryEvent

Trace = list[tuple[str, int]]
ResultSummary = tuple[object, int, int, int, bool, str | None]


def _record_trace(trace: Trace) -> Callable[[RetryEvent], None]:
    def record(event: RetryEvent) -> None:
        trace.append((event.name, event.attempt_number))

    return record


def _trace_policy(trace: Trace) -> RetryPolicy[str]:
    policy: RetryPolicy[str] = RetryPolicy().attempts(3).on(TimeoutError).no_delay()
    for name in (
        "before_attempt",
        "after_failure",
        "before_sleep",
        "after_success",
        "after_giveup",
    ):
        policy = policy.on_event(name, _record_trace(trace))
    return policy


def _with_trace(policy: RetryPolicy[object], trace: Trace) -> RetryPolicy[object]:
    configured = policy
    for name in (
        "before_attempt",
        "after_failure",
        "before_sleep",
        "after_success",
        "after_giveup",
    ):
        configured = configured.on_event(name, _record_trace(trace))
    return configured


def _summary(result: RetryResult[object]) -> ResultSummary:
    return (
        result.value,
        result.total_attempts,
        result.total_failed_attempts,
        result.total_successful_attempts,
        result.exhausted,
        result.retry_cause,
    )


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


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "scenario",
    [
        "success_first_try",
        "exception_exhaustion",
        "result_exhaustion",
        "try_again_success",
        "none_success",
    ],
)
async def test_sync_and_async_direct_result_contracts_match(scenario: str) -> None:
    sync_trace: Trace = []
    async_trace: Trace = []

    if scenario == "success_first_try":
        policy = RetryPolicy().attempts(3).on(TimeoutError).no_delay().return_result()

        def sync_operation() -> str:
            return "ok"

        async def async_operation() -> str:
            return "ok"

    elif scenario == "exception_exhaustion":
        policy = RetryPolicy().attempts(2).on(TimeoutError).no_delay().return_result()

        def sync_operation() -> str:
            raise TimeoutError("temporary")

        async def async_operation() -> str:
            raise TimeoutError("temporary")

    elif scenario == "result_exhaustion":
        policy = (
            RetryPolicy()
            .attempts(2)
            .retry_if_result(lambda value: value == "retry")
            .no_delay()
            .return_result()
        )

        def sync_operation() -> str:
            return "retry"

        async def async_operation() -> str:
            return "retry"

    elif scenario == "try_again_success":
        policy = RetryPolicy().attempts(3).on(ValueError).no_delay().return_result()
        sync_calls = 0
        async_calls = 0

        def sync_operation() -> str:
            nonlocal sync_calls
            sync_calls += 1
            if sync_calls == 1:
                raise TryAgain("not ready")
            return "ok"

        async def async_operation() -> str:
            nonlocal async_calls
            async_calls += 1
            if async_calls == 1:
                raise TryAgain("not ready")
            return "ok"

    else:
        policy = RetryPolicy().attempts(3).on(TimeoutError).no_delay().return_result()

        def sync_operation() -> None:
            return None

        async def async_operation() -> None:
            return None

    sync_result = _with_trace(policy, sync_trace).run(sync_operation)
    async_result = await _with_trace(policy, async_trace).run_async(async_operation)

    assert isinstance(sync_result, RetryResult)
    assert isinstance(async_result, RetryResult)
    assert _summary(sync_result) == _summary(async_result)
    assert sync_trace == async_trace


@pytest.mark.asyncio
async def test_sync_and_async_non_retryable_exception_contracts_match() -> None:
    sync_trace: Trace = []
    async_trace: Trace = []
    policy = RetryPolicy().attempts(3).on(TimeoutError).no_delay()

    def sync_operation() -> None:
        raise ValueError("invalid")

    async def async_operation() -> None:
        raise ValueError("invalid")

    with pytest.raises(ValueError, match="invalid"):
        _with_trace(policy, sync_trace).run(sync_operation)
    with pytest.raises(ValueError, match="invalid"):
        await _with_trace(policy, async_trace).run_async(async_operation)

    assert sync_trace == async_trace
    assert sync_trace == [
        ("before_attempt", 1),
        ("after_failure", 1),
        ("after_giveup", 1),
    ]


@pytest.mark.asyncio
async def test_sync_and_async_exhaustion_customization_contracts_match() -> None:
    fallback_policy = RetryPolicy().attempts(1).on(TimeoutError).fallback_value("safe")
    custom_error_policy = (
        RetryPolicy().attempts(1).on(TimeoutError).on_exhausted_raise(RuntimeError("custom"))
    )

    def sync_fail() -> None:
        raise TimeoutError("temporary")

    async def async_fail() -> None:
        raise TimeoutError("temporary")

    assert fallback_policy.run(sync_fail) == "safe"
    assert await fallback_policy.run_async(async_fail) == "safe"

    with pytest.raises(RuntimeError, match="custom"):
        custom_error_policy.run(sync_fail)
    with pytest.raises(RuntimeError, match="custom"):
        await custom_error_policy.run_async(async_fail)
