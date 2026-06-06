"""Contracts for result-driven retry behavior."""

from __future__ import annotations

import pytest

from relinker import RetryExhaustedError, RetryPolicy

from ._support import policy_without_sleep


def test_sync_run_retries_rejected_results_until_accepted() -> None:
    values = iter([None, None, "ready"])

    result = (
        policy_without_sleep(RetryPolicy().attempts(5).retry_if_result(lambda value: value is None))
        .return_result()
        .run(lambda: next(values))
    )

    assert result.succeeded is True
    assert result.value == "ready"
    assert result.attempt_count == 3
    assert result.failed_attempts == 0
    assert result.successful_attempts == 3


@pytest.mark.asyncio
async def test_async_run_retries_rejected_results_until_accepted() -> None:
    values = iter([False, False, True])

    async def operation() -> bool:
        return next(values)

    result = await (
        policy_without_sleep(
            RetryPolicy().attempts(5).retry_if_result(lambda value: value is False)
        )
        .return_result()
        .run_async(operation)
    )

    assert result.succeeded is True
    assert result.value is True
    assert result.attempt_count == 3
    assert result.failed_attempts == 0
    assert result.successful_attempts == 3


def test_accepted_none_is_a_real_returned_value() -> None:
    result = RetryPolicy().attempts(3).return_result().run(lambda: None)

    assert result.succeeded is True
    assert result.value is None
    assert result.has_last_value is True
    assert result.last_value is None
    assert result.attempts[-1].has_value is True


def test_result_exhaustion_returns_the_last_value_by_default() -> None:
    policy = policy_without_sleep(
        RetryPolicy().attempts(2).retry_if_result(lambda value: value == "retry")
    )

    assert policy.run(lambda: "retry") == "retry"


def test_result_exhaustion_can_be_made_explicit() -> None:
    policy = policy_without_sleep(
        RetryPolicy()
        .attempts(2)
        .retry_if_result(lambda value: value == "retry")
        .raise_on_result_exhausted()
    )

    with pytest.raises(RetryExhaustedError):
        policy.run(lambda: "retry")


def test_sync_context_manager_retries_a_rejected_result() -> None:
    values = iter(["waiting", "ready"])
    policy = policy_without_sleep(
        RetryPolicy().attempts(3).retry_if_result(lambda value: value == "waiting")
    )
    iterator = policy.iter(name="result-contract")

    for attempt in iterator:
        with attempt:
            attempt.set_result(next(values))

    assert iterator.result is not None
    assert iterator.result.succeeded is True
    assert iterator.result.value == "ready"
    assert iterator.result.attempt_count == 2


@pytest.mark.asyncio
async def test_async_context_manager_retries_a_rejected_result() -> None:
    values = iter(["waiting", "ready"])
    policy = policy_without_sleep(
        RetryPolicy().attempts(3).retry_if_result(lambda value: value == "waiting")
    )
    iterator = policy.async_iter(name="async-result-contract")

    async for attempt in iterator:
        async with attempt:
            attempt.set_result(next(values))

    assert iterator.result is not None
    assert iterator.result.succeeded is True
    assert iterator.result.value == "ready"
    assert iterator.result.attempt_count == 2
