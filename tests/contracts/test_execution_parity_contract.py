"""Contracts that keep direct, decorated, and block execution paths equivalent."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from relinker import RetryPolicy, RetryResult

from ._support import policy_without_sleep


def _normalized(result: RetryResult[Any]) -> tuple[Any, int, int, int, bool]:
    return (
        result.value,
        result.attempt_count,
        result.failed_attempts,
        result.successful_attempts,
        result.exhausted,
    )


def _sync_operation_factory() -> Callable[[], str]:
    calls = 0

    def operation() -> str:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise TimeoutError("temporary")
        return "ok"

    return operation


def test_sync_direct_decorator_and_context_have_the_same_result_contract() -> None:
    policy = policy_without_sleep(RetryPolicy().attempts(2).on(TimeoutError).return_result())

    direct = policy.run(_sync_operation_factory())

    decorated = policy(_sync_operation_factory())
    decorated_result = decorated()

    context_operation = _sync_operation_factory()
    iterator = policy.iter(name="sync-parity")
    for attempt in iterator:
        with attempt:
            attempt.set_result(context_operation())

    assert iterator.result is not None
    assert _normalized(direct) == _normalized(decorated_result)
    assert _normalized(direct) == _normalized(iterator.result)
    assert decorated.retry_stats.snapshot().calls == 1


@pytest.mark.asyncio
async def test_async_direct_decorator_and_context_have_the_same_result_contract() -> None:
    policy = policy_without_sleep(RetryPolicy().attempts(2).on(TimeoutError).return_result())

    def async_operation_factory() -> Callable[[], Any]:
        calls = 0

        async def operation() -> str:
            nonlocal calls
            calls += 1
            if calls == 1:
                raise TimeoutError("temporary")
            return "ok"

        return operation

    direct = await policy.run_async(async_operation_factory())

    decorated = policy(async_operation_factory())
    decorated_result = await decorated()

    context_operation = async_operation_factory()
    iterator = policy.async_iter(name="async-parity")
    async for attempt in iterator:
        async with attempt:
            attempt.set_result(await context_operation())

    assert iterator.result is not None
    assert _normalized(direct) == _normalized(decorated_result)
    assert _normalized(direct) == _normalized(iterator.result)
    assert decorated.retry_stats.snapshot().calls == 1


def test_sync_context_and_direct_execution_propagate_non_retryable_errors() -> None:
    policy = policy_without_sleep(RetryPolicy().attempts(3).on(TimeoutError))

    with pytest.raises(ValueError, match="invalid"):
        policy.run(lambda: (_ for _ in ()).throw(ValueError("invalid")))

    with pytest.raises(ValueError, match="invalid"):
        for attempt in policy.iter(name="non-retryable-parity"):
            with attempt:
                raise ValueError("invalid")
