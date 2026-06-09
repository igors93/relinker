"""Regression probes for non-retryable exceptions in decorated functions."""

from __future__ import annotations

from typing import Any

import pytest

from relinker import RetryPolicy, RetryResult


def _no_sleep(_: float) -> None:
    pass


async def _async_no_sleep(_: float) -> None:
    pass


def _without_sleep(policy: RetryPolicy[Any]) -> RetryPolicy[Any]:
    return policy.with_sleep(_no_sleep, _async_no_sleep)


def test_decorated_fallback_policy_propagates_non_retryable_exception() -> None:
    fallback_calls = 0

    def fallback(result: RetryResult[Any]) -> str:
        nonlocal fallback_calls
        fallback_calls += 1
        return "safe"

    policy = _without_sleep(RetryPolicy().attempts(3).on(TimeoutError).fallback(fallback))

    @policy
    def operation() -> str:
        raise ValueError("permanent")

    with pytest.raises(ValueError, match="permanent"):
        operation()

    assert fallback_calls == 0

    snapshot = operation.retry_stats.snapshot()
    assert snapshot.calls == 1
    assert snapshot.failures == 1
    assert snapshot.exhausted == 0
    assert snapshot.total_attempts == 1


@pytest.mark.asyncio
async def test_async_decorated_fallback_policy_propagates_non_retryable_exception() -> None:
    fallback_calls = 0

    def fallback(result: RetryResult[Any]) -> str:
        nonlocal fallback_calls
        fallback_calls += 1
        return "safe"

    policy = _without_sleep(RetryPolicy().attempts(3).on(TimeoutError).fallback(fallback))

    @policy
    async def operation() -> str:
        raise ValueError("permanent")

    with pytest.raises(ValueError, match="permanent"):
        await operation()

    assert fallback_calls == 0

    snapshot = operation.retry_stats.snapshot()
    assert snapshot.calls == 1
    assert snapshot.failures == 1
    assert snapshot.exhausted == 0
    assert snapshot.total_attempts == 1


def test_decorated_custom_exhaustion_error_does_not_replace_non_retryable_error() -> None:
    policy = _without_sleep(
        RetryPolicy().attempts(3).on(TimeoutError).on_exhausted_raise(RuntimeError("exhausted"))
    )

    @policy
    def operation() -> str:
        raise ValueError("permanent")

    with pytest.raises(ValueError, match="permanent"):
        operation()


@pytest.mark.asyncio
async def test_async_decorated_custom_exhaustion_error_does_not_replace_non_retryable_error() -> (
    None
):
    policy = _without_sleep(
        RetryPolicy().attempts(3).on(TimeoutError).on_exhausted_raise(RuntimeError("exhausted"))
    )

    @policy
    async def operation() -> str:
        raise ValueError("permanent")

    with pytest.raises(ValueError, match="permanent"):
        await operation()
