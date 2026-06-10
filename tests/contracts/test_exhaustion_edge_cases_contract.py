"""Contracts for exhaustion behavior and precedence edge cases."""

from __future__ import annotations

import pytest

from relinker import InvalidRetryConfigError, RetryPolicy, RetryResult

from ._support import policy_without_sleep


def test_fallback_is_not_applied_to_non_retryable_exception() -> None:
    policy = policy_without_sleep(RetryPolicy().attempts(3).on(TimeoutError).fallback_value("safe"))

    with pytest.raises(ValueError, match="permanent"):
        policy.run(lambda: (_ for _ in ()).throw(ValueError("permanent")))


def test_fallback_callback_receives_complete_retry_result() -> None:
    received: list[RetryResult[object]] = []

    def fallback(result: RetryResult[object]) -> str:
        received.append(result)
        return "safe"

    policy = policy_without_sleep(RetryPolicy().attempts(2).on(TimeoutError).fallback(fallback))
    assert policy.run(lambda: (_ for _ in ()).throw(TimeoutError("down"))) == "safe"
    assert len(received) == 1
    assert received[0].exhausted_by_exception is True
    assert received[0].attempt_count == 2
    assert received[0].failed_attempts == 2


def test_fallback_value_can_explicitly_be_none() -> None:
    policy = policy_without_sleep(RetryPolicy().attempts(1).on(TimeoutError).fallback_value(None))
    assert policy.run(lambda: (_ for _ in ()).throw(TimeoutError("down"))) is None


def test_custom_exception_class_creates_fresh_instances() -> None:
    policy = policy_without_sleep(
        RetryPolicy().attempts(1).on(TimeoutError).on_exhausted_raise(ValueError)
    )
    caught: list[ValueError] = []
    for _ in range(2):
        with pytest.raises(ValueError) as error:
            policy.run(lambda: (_ for _ in ()).throw(TimeoutError("down")))
        caught.append(error.value)
    assert caught[0] is not caught[1]


def test_custom_exception_instance_is_copied_per_exhaustion() -> None:
    configured = ValueError("translated")
    policy = policy_without_sleep(
        RetryPolicy().attempts(1).on(TimeoutError).on_exhausted_raise(configured)
    )
    caught: list[ValueError] = []
    for _ in range(2):
        with pytest.raises(ValueError, match="translated") as error:
            policy.run(lambda: (_ for _ in ()).throw(TimeoutError("down")))
        caught.append(error.value)
    assert all(error is not configured for error in caught)
    assert caught[0] is not caught[1]


def test_custom_exception_factory_receives_exhausted_result() -> None:
    observed: list[RetryResult[object]] = []

    def factory(result: RetryResult[object]) -> BaseException:
        observed.append(result)
        return LookupError(f"attempts={result.attempt_count}")

    policy = policy_without_sleep(
        RetryPolicy().attempts(2).on(TimeoutError).on_exhausted_raise(factory)
    )
    with pytest.raises(LookupError, match="attempts=2"):
        policy.run(lambda: (_ for _ in ()).throw(TimeoutError("down")))
    assert observed[0].exhausted is True


def test_invalid_exception_factory_result_is_rejected() -> None:
    policy = policy_without_sleep(
        RetryPolicy().attempts(1).on(TimeoutError).on_exhausted_raise(lambda _: "not an exception")  # type: ignore[arg-type]
    )
    with pytest.raises(InvalidRetryConfigError, match="BaseException"):
        policy.run(lambda: (_ for _ in ()).throw(TimeoutError("down")))


def test_raise_last_preserves_final_exception_object() -> None:
    error = TimeoutError("same object")
    policy = policy_without_sleep(RetryPolicy().attempts(1).on(TimeoutError).raise_last())

    with pytest.raises(TimeoutError) as caught:
        policy.run(lambda: (_ for _ in ()).throw(error))
    assert caught.value is error


@pytest.mark.asyncio
async def test_async_fallback_receives_exhausted_result() -> None:
    received: list[RetryResult[object]] = []

    def fallback(result: RetryResult[object]) -> str:
        received.append(result)
        return "safe"

    async def operation() -> None:
        raise TimeoutError("down")

    policy = policy_without_sleep(RetryPolicy().attempts(2).on(TimeoutError).fallback(fallback))
    assert await policy.run_async(operation) == "safe"
    assert received[0].attempt_count == 2


def test_fallback_applies_to_result_based_exhaustion() -> None:
    policy = policy_without_sleep(
        RetryPolicy()
        .attempts(2)
        .retry_if_result(lambda value: value == "waiting")
        .fallback_value("fallback")
    )
    assert policy.run(lambda: "waiting") == "fallback"


def test_custom_exception_applies_to_result_based_exhaustion() -> None:
    policy = policy_without_sleep(
        RetryPolicy()
        .attempts(2)
        .retry_if_result(lambda value: value == "waiting")
        .on_exhausted_raise(RuntimeError("not ready"))
    )
    with pytest.raises(RuntimeError, match="not ready"):
        policy.run(lambda: "waiting")


def test_return_result_overrides_result_raise_mode_when_configured_last() -> None:
    policy = policy_without_sleep(
        RetryPolicy()
        .attempts(1)
        .retry_if_result(lambda _: True)
        .raise_on_result_exhausted()
        .return_result()
    )
    result = policy.run(lambda: "waiting")
    assert isinstance(result, RetryResult)
    assert result.exhausted_by_result is True


def test_fallback_configured_last_overrides_custom_exception() -> None:
    policy = policy_without_sleep(
        RetryPolicy()
        .attempts(1)
        .on(TimeoutError)
        .on_exhausted_raise(ValueError("custom"))
        .fallback_value("safe")
    )
    assert policy.run(lambda: (_ for _ in ()).throw(TimeoutError("down"))) == "safe"


def test_raise_last_configured_last_overrides_fallback_callback() -> None:
    called = False

    def fallback(_: RetryResult[object]) -> str:
        nonlocal called
        called = True
        return "safe"

    policy = policy_without_sleep(
        RetryPolicy().attempts(1).on(TimeoutError).fallback(fallback).raise_last()
    )
    with pytest.raises(TimeoutError, match="down"):
        policy.run(lambda: (_ for _ in ()).throw(TimeoutError("down")))
    assert called is False
