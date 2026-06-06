"""Contracts for bounded attempt history and aggregate counters."""

from __future__ import annotations

import pytest

from relinker import RetryPolicy

from ._support import policy_without_sleep


def test_bounded_history_keeps_totals_for_the_complete_sync_execution() -> None:
    calls = 0

    def operation() -> str:
        nonlocal calls
        calls += 1
        if calls < 4:
            raise TimeoutError(f"failure-{calls}")
        return "ok"

    result = (
        policy_without_sleep(RetryPolicy().attempts(4).on(TimeoutError).keep_history(2))
        .return_result()
        .run(operation)
    )

    assert result.attempt_count == 4
    assert result.retained_attempt_count == 2
    assert result.history_truncated is True
    assert result.failed_attempts == 3
    assert result.successful_attempts == 1
    assert [attempt.number for attempt in result.attempts] == [3, 4]
    assert isinstance(result.last_error, TimeoutError)
    assert str(result.last_error) == "failure-3"
    assert result.last_value == "ok"


@pytest.mark.asyncio
async def test_bounded_history_keeps_totals_for_the_complete_async_execution() -> None:
    calls = 0

    async def operation() -> str:
        nonlocal calls
        calls += 1
        if calls < 4:
            raise TimeoutError(f"failure-{calls}")
        return "ok"

    result = await (
        policy_without_sleep(RetryPolicy().attempts(4).on(TimeoutError).keep_history(2))
        .return_result()
        .run_async(operation)
    )

    assert result.attempt_count == 4
    assert result.retained_attempt_count == 2
    assert result.history_truncated is True
    assert result.failed_attempts == 3
    assert result.successful_attempts == 1
    assert [attempt.number for attempt in result.attempts] == [3, 4]


def test_unbounded_history_retains_every_attempt() -> None:
    calls = 0

    def operation() -> str:
        nonlocal calls
        calls += 1
        if calls < 4:
            raise TimeoutError("temporary")
        return "ok"

    result = (
        policy_without_sleep(RetryPolicy().attempts(4).on(TimeoutError).keep_history(None))
        .return_result()
        .run(operation)
    )

    assert result.attempt_count == 4
    assert result.retained_attempt_count == 4
    assert result.history_truncated is False
    assert [attempt.number for attempt in result.attempts] == [1, 2, 3, 4]


def test_context_manager_uses_the_same_bounded_history_contract() -> None:
    policy = policy_without_sleep(RetryPolicy().attempts(4).on(TimeoutError).keep_history(2))
    iterator = policy.iter(name="history-contract")

    for attempt in iterator:
        with attempt:
            if attempt.number < 4:
                raise TimeoutError(f"failure-{attempt.number}")

    assert iterator.result is not None
    assert iterator.result.attempt_count == 4
    assert iterator.result.retained_attempt_count == 2
    assert iterator.result.history_truncated is True
    assert iterator.result.failed_attempts == 3
    assert iterator.result.successful_attempts == 1
    assert [record.number for record in iterator.result.attempts] == [3, 4]


def test_none_value_remains_distinguishable_from_no_value() -> None:
    result = RetryPolicy().return_result().run(lambda: None)

    assert result.value is None
    assert result.has_last_value is True
    assert result.last_value is None
    assert result.attempts[-1].has_value is True
