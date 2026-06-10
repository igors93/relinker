"""Contracts for result predicates and result-driven retry edge cases."""

from __future__ import annotations

import pytest

from relinker import RetryExhaustedError, RetryPolicy
from relinker.result_conditions import (
    retry_if_empty,
    retry_if_false,
    retry_if_none,
    retry_if_value,
)

from ._support import policy_without_sleep


def test_retry_if_false_matches_false_but_not_zero() -> None:
    predicate = retry_if_false()
    assert predicate(False) is True
    assert predicate(0) is False


def test_retry_if_none_matches_only_none() -> None:
    predicate = retry_if_none()
    assert predicate(None) is True
    assert predicate(False) is False
    assert predicate("") is False


def test_retry_if_empty_matches_empty_sized_values() -> None:
    predicate = retry_if_empty()
    assert predicate([]) is True
    assert predicate(()) is True
    assert predicate("") is True
    assert predicate({}) is True


def test_retry_if_empty_accepts_non_sized_values() -> None:
    predicate = retry_if_empty()
    assert predicate(None) is False
    assert predicate(1) is False
    assert predicate(object()) is False


def test_retry_if_value_uses_equality_semantics() -> None:
    predicate = retry_if_value({"status": "pending"})
    assert predicate({"status": "pending"}) is True
    assert predicate({"status": "ready"}) is False


def test_custom_retry_if_receives_real_none_result() -> None:
    observed: list[tuple[BaseException | None, object]] = []

    def condition(error: BaseException | None, value: object) -> bool:
        observed.append((error, value))
        return False

    result = RetryPolicy().retry_if(condition).return_result().run(lambda: None)
    assert result.succeeded is True
    assert observed == [(None, None)]


def test_or_condition_can_retry_exception_then_rejected_result() -> None:
    calls = 0

    def operation() -> str:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise TimeoutError("temporary")
        if calls == 2:
            return "waiting"
        return "ready"

    policy = policy_without_sleep(
        RetryPolicy()
        .attempts(3)
        .retry_if_result(lambda value: value == "waiting")
        .or_on(TimeoutError)
    )
    assert policy.run(operation) == "ready"
    assert calls == 3


def test_rejected_result_exhaustion_returns_last_value_by_default() -> None:
    values = iter(["a", "b", "c"])
    policy = policy_without_sleep(RetryPolicy().attempts(3).retry_if_result(lambda _: True))
    assert policy.run(lambda: next(values)) == "c"


def test_rejected_result_exhaustion_error_contains_retry_result() -> None:
    policy = policy_without_sleep(
        RetryPolicy()
        .attempts(2)
        .retry_if_result(lambda value: value == "waiting")
        .raise_on_result_exhausted()
    )

    with pytest.raises(RetryExhaustedError) as caught:
        policy.run(lambda: "waiting")

    assert caught.value.result is not None
    assert caught.value.result.exhausted_by_result is True
    assert caught.value.result.attempt_count == 2


def test_return_result_exposes_result_exhaustion_flags() -> None:
    result = (
        policy_without_sleep(RetryPolicy().attempts(2).retry_if_result(lambda value: value < 10))
        .return_result()
        .run(lambda: 1)
    )
    assert result.exhausted is True
    assert result.exhausted_by_result is True
    assert result.exhausted_by_exception is False
    assert result.retry_cause == "result"


def test_rejected_results_count_as_successful_attempts() -> None:
    result = (
        policy_without_sleep(
            RetryPolicy().attempts(3).retry_if_result(lambda value: value != "ready")
        )
        .return_result()
        .run(lambda: "waiting")
    )
    assert result.attempt_count == 3
    assert result.failed_attempts == 0
    assert result.successful_attempts == 3


def test_result_history_preserves_each_rejected_value() -> None:
    values = iter(["one", "two", "three"])
    result = (
        policy_without_sleep(RetryPolicy().attempts(3).retry_if_result(lambda _: True))
        .return_result()
        .run(lambda: next(values))
    )
    assert [attempt.value for attempt in result.attempts] == ["one", "two", "three"]
    assert all(attempt.has_value for attempt in result.attempts)


@pytest.mark.asyncio
async def test_async_result_predicate_retries_until_accepted() -> None:
    values = iter([0, 0, 1])

    async def operation() -> int:
        return next(values)

    result = await (
        policy_without_sleep(RetryPolicy().attempts(3).retry_if_result(lambda value: value == 0))
        .return_result()
        .run_async(operation)
    )
    assert result.succeeded is True
    assert result.value == 1
    assert result.attempt_count == 3


def test_return_last_on_result_exhausted_restores_default_after_raise_mode() -> None:
    policy = policy_without_sleep(
        RetryPolicy()
        .attempts(2)
        .retry_if_result(lambda _: True)
        .raise_on_result_exhausted()
        .return_last_on_result_exhausted()
    )
    assert policy.run(lambda: "last") == "last"
