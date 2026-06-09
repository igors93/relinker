"""Integration tests for decorated functions and retry statistics."""

from __future__ import annotations

from typing import Any

import pytest

from relinker import RetryPolicy, RetryResult, retry


def _no_sleep(_: float) -> None:
    pass


async def _async_no_sleep(_: float) -> None:
    pass


def _without_sleep(policy: RetryPolicy[Any]) -> RetryPolicy[Any]:
    return policy.with_sleep(_no_sleep, _async_no_sleep)


def test_policy_decorator_preserves_function_name() -> None:
    def original() -> str:
        return "ok"

    wrapped = RetryPolicy()(original)
    assert wrapped.__name__ == "original"


def test_policy_decorator_preserves_function_docstring() -> None:
    def original() -> str:
        """documented operation"""
        return "ok"

    wrapped = RetryPolicy()(original)
    assert wrapped.__doc__ == "documented operation"


def test_decorated_function_exposes_original_policy() -> None:
    policy = RetryPolicy().named("decorated")
    wrapped = policy(lambda: "ok")
    assert wrapped.retry_policy is policy


def test_with_policy_creates_new_wrapper_without_mutating_original() -> None:
    calls = 0

    def operation() -> str:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise TimeoutError("temporary")
        return "ok"

    original_policy = _without_sleep(RetryPolicy().attempts(1).on(TimeoutError))
    wrapped = original_policy(operation)
    replacement = wrapped.with_policy(
        _without_sleep(RetryPolicy().attempts(2).on(TimeoutError))
    )

    assert replacement() == "ok"
    assert wrapped.retry_policy is original_policy
    assert replacement.retry_policy is not original_policy


def test_retry_stats_start_at_zero() -> None:
    wrapped = RetryPolicy()(lambda: "ok")
    snapshot = wrapped.retry_stats.snapshot()
    assert snapshot.calls == 0
    assert snapshot.successes == 0
    assert snapshot.failures == 0
    assert snapshot.exhausted == 0


def test_retry_stats_record_success_and_attempt_count() -> None:
    calls = 0

    def operation() -> str:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise TimeoutError("temporary")
        return "ok"

    wrapped = _without_sleep(RetryPolicy().attempts(2).on(TimeoutError))(operation)
    assert wrapped() == "ok"
    snapshot = wrapped.retry_stats.snapshot()
    assert snapshot.calls == 1
    assert snapshot.successes == 1
    assert snapshot.failures == 0
    assert snapshot.total_attempts == 2
    assert snapshot.average_attempts == 2.0


def test_retry_stats_record_exhausted_failure() -> None:
    wrapped = _without_sleep(
        RetryPolicy().attempts(2).on(TimeoutError).return_result()
    )(lambda: (_ for _ in ()).throw(TimeoutError("down")))

    result = wrapped()
    assert result.exhausted is True
    snapshot = wrapped.retry_stats.snapshot()
    assert snapshot.calls == 1
    assert snapshot.failures == 1
    assert snapshot.exhausted == 1
    assert snapshot.total_attempts == 2


def test_retry_stats_record_non_retryable_failure_before_reraising() -> None:
    wrapped = _without_sleep(RetryPolicy().attempts(3).on(TimeoutError))(
        lambda: (_ for _ in ()).throw(ValueError("permanent"))
    )

    with pytest.raises(ValueError, match="permanent"):
        wrapped()

    snapshot = wrapped.retry_stats.snapshot()
    assert snapshot.calls == 1
    assert snapshot.failures == 1
    assert snapshot.exhausted == 0
    assert snapshot.total_attempts == 1


def test_retry_stats_reset_clears_all_counters() -> None:
    wrapped = RetryPolicy()(lambda: "ok")
    assert wrapped() == "ok"
    wrapped.retry_stats.reset()
    assert wrapped.retry_stats.to_dict() == {
        "calls": 0,
        "successes": 0,
        "failures": 0,
        "exhausted": 0,
        "total_attempts": 0,
        "total_time": 0.0,
        "average_attempts": 0.0,
        "success_rate": 0.0,
        "failure_rate": 0.0,
    }


@pytest.mark.asyncio
async def test_async_decorator_records_statistics() -> None:
    calls = 0

    async def operation() -> str:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise TimeoutError("temporary")
        return "ok"

    wrapped = _without_sleep(RetryPolicy().attempts(2).on(TimeoutError))(operation)
    assert await wrapped() == "ok"
    snapshot = wrapped.retry_stats.snapshot()
    assert snapshot.calls == 1
    assert snapshot.successes == 1
    assert snapshot.total_attempts == 2


def test_bare_retry_decorator_uses_its_documented_default_attempts() -> None:
    calls = 0

    @retry
    def operation() -> str:
        nonlocal calls
        calls += 1
        if calls < 3:
            raise RuntimeError("temporary")
        return "ok"

    assert operation() == "ok"
    assert calls == 3


def test_retry_decorator_return_result_returns_retry_result() -> None:
    @retry(attempts=1, return_result=True)
    def operation() -> str:
        raise RuntimeError("down")

    result = operation()
    assert isinstance(result, RetryResult)
    assert result.exhausted is True
    assert isinstance(result.error, RuntimeError)


def test_separate_wrappers_have_independent_statistics() -> None:
    policy = RetryPolicy()
    first = policy(lambda: "first")
    second = policy(lambda: "second")

    assert first() == "first"
    assert first.retry_stats.snapshot().calls == 1
    assert second.retry_stats.snapshot().calls == 0


def test_stats_rates_reflect_mixed_success_and_failure_calls() -> None:
    outcomes = iter(["ok", RuntimeError("down")])

    def operation() -> str:
        outcome = next(outcomes)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    wrapped = RetryPolicy().attempts(1).return_result()(operation)
    assert wrapped().succeeded is True
    assert wrapped().failed is True
    snapshot = wrapped.retry_stats.snapshot()
    assert snapshot.calls == 2
    assert snapshot.success_rate == 0.5
    assert snapshot.failure_rate == 0.5
