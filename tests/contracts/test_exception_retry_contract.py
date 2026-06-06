"""Contracts for exception-driven retry behavior."""

from __future__ import annotations

import pytest

from relinker import RetryPolicy, TryAgain

from ._support import policy_without_sleep


def test_sync_run_retries_configured_exception_until_success() -> None:
    calls = 0

    def operation() -> str:
        nonlocal calls
        calls += 1
        if calls < 3:
            raise TimeoutError("temporary")
        return "ok"

    result = (
        policy_without_sleep(RetryPolicy().attempts(5).on(TimeoutError))
        .return_result()
        .run(operation)
    )

    assert result.succeeded is True
    assert result.value == "ok"
    assert result.attempt_count == 3
    assert result.failed_attempts == 2
    assert result.successful_attempts == 1


@pytest.mark.asyncio
async def test_async_run_retries_configured_exception_until_success() -> None:
    calls = 0

    async def operation() -> str:
        nonlocal calls
        calls += 1
        if calls < 3:
            raise TimeoutError("temporary")
        return "ok"

    result = await (
        policy_without_sleep(RetryPolicy().attempts(5).on(TimeoutError))
        .return_result()
        .run_async(operation)
    )

    assert result.succeeded is True
    assert result.value == "ok"
    assert result.attempt_count == 3
    assert result.failed_attempts == 2
    assert result.successful_attempts == 1


def test_unconfigured_exception_is_not_retried() -> None:
    calls = 0

    def operation() -> None:
        nonlocal calls
        calls += 1
        raise ValueError("invalid input")

    policy = policy_without_sleep(RetryPolicy().attempts(5).on(TimeoutError))

    with pytest.raises(ValueError, match="invalid input"):
        policy.run(operation)

    assert calls == 1


@pytest.mark.asyncio
async def test_unconfigured_exception_is_not_retried_async() -> None:
    calls = 0

    async def operation() -> None:
        nonlocal calls
        calls += 1
        raise ValueError("invalid input")

    policy = policy_without_sleep(RetryPolicy().attempts(5).on(TimeoutError))

    with pytest.raises(ValueError, match="invalid input"):
        await policy.run_async(operation)

    assert calls == 1


def test_try_again_bypasses_the_configured_exception_filter() -> None:
    calls = 0

    def operation() -> str:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise TryAgain("explicit retry")
        return "ok"

    result = (
        policy_without_sleep(RetryPolicy().attempts(2).on(ValueError))
        .return_result()
        .run(operation)
    )

    assert result.succeeded is True
    assert result.value == "ok"
    assert result.attempt_count == 2


@pytest.mark.parametrize("error", [KeyboardInterrupt(), SystemExit(2)])
def test_base_exceptions_are_never_swallowed(error: BaseException) -> None:
    def operation() -> None:
        raise error

    with pytest.raises(type(error)):
        RetryPolicy().attempts(3).run(operation)
