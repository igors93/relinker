"""Tests for the public relinker.testing helpers."""

from __future__ import annotations

import pytest

from relinker import InvalidRetryConfigError, RetryPolicy
from relinker.testing import fail_times, no_sleep, no_sleep_async
from relinker.testing.fake_task import FailingTask, FailTimesBuilder


def test_fail_times_fails_then_returns_value() -> None:
    task = fail_times(2, TimeoutError("slow")).then_return("ok")

    assert isinstance(task, FailingTask)
    for _ in range(2):
        with pytest.raises(TimeoutError, match="slow"):
            task()
    assert task() == "ok"
    assert task() == "ok"


def test_fail_times_zero_succeeds_immediately() -> None:
    assert fail_times(0).then_return(42)() == 42


def test_fail_times_default_error_is_runtime_error() -> None:
    builder = fail_times(1)

    assert isinstance(builder, FailTimesBuilder)
    assert isinstance(builder.error, RuntimeError)
    assert str(builder.error) == "planned failure"


@pytest.mark.parametrize("times", [-1, 1.5, "2", True, None])
def test_fail_times_rejects_invalid_times(times: object) -> None:
    with pytest.raises(InvalidRetryConfigError, match="times must be a non-negative integer"):
        fail_times(times)  # type: ignore[arg-type]


def test_fail_times_rejects_non_exception_error() -> None:
    with pytest.raises(InvalidRetryConfigError, match="error must be an exception instance"):
        fail_times(1, "boom")  # type: ignore[arg-type]


def test_fail_times_validation_error_is_still_a_value_error() -> None:
    # Backward compatibility: fail_times() raised ValueError before.
    with pytest.raises(ValueError):
        fail_times(-1)


def test_fail_times_works_with_a_retry_policy() -> None:
    task = fail_times(2, ConnectionError("down")).then_return("ok")
    policy = RetryPolicy().attempts(3).on(ConnectionError).fixed_delay(10)

    with no_sleep(policy) as fast_policy:
        assert fast_policy.run(task) == "ok"


def test_no_sleep_disables_sync_sleep() -> None:
    sleeps: list[float] = []
    policy = RetryPolicy().attempts(2).on(TimeoutError).fixed_delay(10).with_sleep(sleeps.append)
    task = fail_times(1, TimeoutError()).then_return("ok")

    with no_sleep(policy) as fast_policy:
        assert fast_policy.run(task) == "ok"

    assert sleeps == []
    # Other settings are preserved.
    assert fast_policy.stop_strategy == policy.stop_strategy
    assert fast_policy.delay_strategy == policy.delay_strategy


async def test_no_sleep_async_disables_both_sleepers() -> None:
    sync_sleeps: list[float] = []
    async_sleeps: list[float] = []

    async def record(seconds: float) -> None:
        async_sleeps.append(seconds)

    policy = (
        RetryPolicy()
        .attempts(2)
        .on(TimeoutError)
        .fixed_delay(10)
        .with_sleep(sync_sleeps.append, record)
    )
    fast_policy = no_sleep_async(policy)

    calls: list[int] = []

    async def flaky() -> str:
        calls.append(1)
        if len(calls) == 1:
            raise TimeoutError
        return "ok"

    assert await fast_policy.run_async(flaky) == "ok"
    assert fast_policy.run(fail_times(1, TimeoutError()).then_return("ok")) == "ok"
    assert sync_sleeps == []
    assert async_sleeps == []
