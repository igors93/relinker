"""Regression contracts for TryAgain final-error resolution."""

from __future__ import annotations

import pytest

from relinker import RetryPolicy, TryAgain, retry
from relinker.result import RetryResult


def _raise_try_again_from_explicit_cause() -> None:
    original_error = ValueError("original")
    raise TryAgain("retry requested") from original_error


def _raise_try_again_from_implicit_context() -> None:
    try:
        raise ValueError("original")
    except ValueError:
        raise TryAgain("retry requested")  # noqa: B904


def _raise_try_again_without_cause() -> None:
    raise TryAgain("retry requested")


async def _async_raise_try_again_from_explicit_cause() -> None:
    _raise_try_again_from_explicit_cause()


async def _async_raise_try_again_from_implicit_context() -> None:
    _raise_try_again_from_implicit_context()


async def _async_raise_try_again_without_cause() -> None:
    _raise_try_again_without_cause()


def _assert_try_again_history_preserved(result: RetryResult[object]) -> None:
    assert result.attempts
    assert isinstance(result.attempts[-1].error, TryAgain)


def test_sync_raise_last_uses_explicit_cause_as_final_error() -> None:
    policy = RetryPolicy().attempts(1).no_delay()

    with pytest.raises(ValueError, match="original"):
        policy.run(_raise_try_again_from_explicit_cause)


def test_sync_raise_last_uses_implicit_context_as_final_error() -> None:
    policy = RetryPolicy().attempts(1).no_delay()

    with pytest.raises(ValueError, match="original"):
        policy.run(_raise_try_again_from_implicit_context)


def test_sync_raise_last_keeps_try_again_without_cause_as_final_error() -> None:
    policy = RetryPolicy().attempts(1).no_delay()

    with pytest.raises(TryAgain, match="retry requested"):
        policy.run(_raise_try_again_without_cause)


def test_return_result_uses_cause_as_final_error_and_preserves_history() -> None:
    policy = RetryPolicy().attempts(1).no_delay().return_result()

    explicit = policy.run(_raise_try_again_from_explicit_cause)
    implicit = policy.run(_raise_try_again_from_implicit_context)
    plain = policy.run(_raise_try_again_without_cause)

    assert isinstance(explicit.error, ValueError)
    assert isinstance(implicit.error, ValueError)
    assert isinstance(plain.error, TryAgain)
    _assert_try_again_history_preserved(explicit)
    _assert_try_again_history_preserved(implicit)
    _assert_try_again_history_preserved(plain)


@pytest.mark.asyncio
async def test_async_raise_last_uses_try_again_cause_as_final_error() -> None:
    policy = RetryPolicy().attempts(1).no_delay()

    with pytest.raises(ValueError, match="original"):
        await policy.run_async(_async_raise_try_again_from_explicit_cause)
    with pytest.raises(ValueError, match="original"):
        await policy.run_async(_async_raise_try_again_from_implicit_context)
    with pytest.raises(TryAgain, match="retry requested"):
        await policy.run_async(_async_raise_try_again_without_cause)


def test_decorator_uses_try_again_cause_as_final_error() -> None:
    @retry(attempts=1, delay=0)
    def operation() -> None:
        _raise_try_again_from_implicit_context()

    with pytest.raises(ValueError, match="original"):
        operation()


def test_sync_context_manager_uses_try_again_cause_as_final_error() -> None:
    policy = RetryPolicy().attempts(1).no_delay()
    iterator = policy.iter()

    with pytest.raises(ValueError, match="original"):
        for attempt in iterator:
            with attempt:
                _raise_try_again_from_implicit_context()

    assert iterator.result is not None
    assert isinstance(iterator.result.error, ValueError)
    _assert_try_again_history_preserved(iterator.result)


@pytest.mark.asyncio
async def test_async_context_manager_uses_try_again_cause_as_final_error() -> None:
    policy = RetryPolicy().attempts(1).no_delay()
    iterator = policy.async_iter()

    with pytest.raises(ValueError, match="original"):
        async for attempt in iterator:
            async with attempt:
                _raise_try_again_from_explicit_cause()

    assert iterator.result is not None
    assert isinstance(iterator.result.error, ValueError)
    _assert_try_again_history_preserved(iterator.result)
