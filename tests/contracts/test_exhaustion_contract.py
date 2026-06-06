"""Contracts for mutually exclusive exhaustion behavior."""

from __future__ import annotations

import pytest

from relinker import RetryPolicy, RetryResult

from ._support import policy_without_sleep


def always_fails() -> None:
    """Raise the deterministic original exception used by contract tests."""

    raise RuntimeError("original")


def test_raise_last_configured_after_fallback_rethrows_original_error() -> None:
    policy = policy_without_sleep(RetryPolicy().attempts(1).fallback_value("safe").raise_last())

    with pytest.raises(RuntimeError, match="original"):
        policy.run(always_fails)


def test_raise_last_configured_after_custom_exception_rethrows_original_error() -> None:
    policy = policy_without_sleep(
        RetryPolicy().attempts(1).on_exhausted_raise(ValueError("custom")).raise_last()
    )

    with pytest.raises(RuntimeError, match="original"):
        policy.run(always_fails)


def test_fallback_configured_last_returns_its_value() -> None:
    policy = policy_without_sleep(RetryPolicy().attempts(1).raise_last().fallback_value("safe"))

    assert policy.run(always_fails) == "safe"


def test_custom_exception_configured_last_replaces_fallback() -> None:
    policy = policy_without_sleep(
        RetryPolicy().attempts(1).fallback_value("safe").on_exhausted_raise(ValueError("custom"))
    )

    with pytest.raises(ValueError, match="custom"):
        policy.run(always_fails)


def test_return_result_configured_last_replaces_fallback_output() -> None:
    policy = policy_without_sleep(RetryPolicy().attempts(1).fallback_value("safe").return_result())

    result = policy.run(always_fails)

    assert isinstance(result, RetryResult)
    assert result.exhausted is True
    assert isinstance(result.error, RuntimeError)


def test_fallback_configured_last_replaces_return_result() -> None:
    policy = policy_without_sleep(RetryPolicy().attempts(1).return_result().fallback_value("safe"))

    assert policy.run(always_fails) == "safe"


@pytest.mark.asyncio
async def test_async_execution_uses_the_same_exhaustion_precedence() -> None:
    async def operation() -> None:
        raise RuntimeError("original")

    policy = policy_without_sleep(RetryPolicy().attempts(1).fallback_value("safe").raise_last())

    with pytest.raises(RuntimeError, match="original"):
        await policy.run_async(operation)


def test_context_manager_applies_fallback_and_exposes_outcome() -> None:
    policy = policy_without_sleep(RetryPolicy().attempts(1).fallback_value("safe"))
    iterator = policy.iter(name="fallback-contract")

    for attempt in iterator:
        with attempt:
            raise RuntimeError("original")

    assert iterator.result is not None
    assert iterator.result.exhausted is True
    assert iterator.has_outcome is True
    assert iterator.outcome == "safe"


@pytest.mark.asyncio
async def test_async_context_manager_applies_fallback_and_exposes_outcome() -> None:
    policy = policy_without_sleep(RetryPolicy().attempts(1).fallback_value("safe"))
    iterator = policy.async_iter(name="async-fallback-contract")

    async for attempt in iterator:
        async with attempt:
            raise RuntimeError("original")

    assert iterator.result is not None
    assert iterator.result.exhausted is True
    assert iterator.has_outcome is True
    assert iterator.outcome == "safe"
