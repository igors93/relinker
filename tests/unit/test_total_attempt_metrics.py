"""
Regression tests for C2: total_failed_attempts / total_successful_attempts on RetryResult.

These counters must be truthful even when history_limit bounds the retained attempts list,
and must be populated through all three execution paths: sync executor, async executor,
and context manager.
"""

from __future__ import annotations

import pytest

from relinker import RetryPolicy

# ---------------------------------------------------------------------------
# Sync executor
# ---------------------------------------------------------------------------


class TestSyncExecutorMetrics:
    def test_all_failed_single_error(self) -> None:
        calls = [0]

        def always_fail() -> None:
            calls[0] += 1
            raise ValueError("boom")

        policy = RetryPolicy().attempts(3).no_delay()
        with pytest.raises(ValueError):
            policy.run(always_fail)

        # run() doesn't return RetryResult by default, use return_result()
        policy_rr = RetryPolicy().attempts(3).no_delay().return_result()
        result = policy_rr.run(always_fail)

        assert result.total_attempts == 3
        assert result.failed_attempts == 3
        assert result.successful_attempts == 0

    def test_mixed_attempts(self) -> None:
        call_count = [0]

        def sometimes_fail() -> str:
            call_count[0] += 1
            if call_count[0] < 3:
                raise ValueError("not yet")
            return "ok"

        policy = RetryPolicy().attempts(5).no_delay().on(ValueError).return_result()
        result = policy.run(sometimes_fail)

        assert result.total_attempts == 3
        assert result.failed_attempts == 2
        assert result.successful_attempts == 1

    def test_truthful_with_bounded_history(self) -> None:
        call_count = [0]

        def always_fail() -> None:
            call_count[0] += 1
            raise ValueError("boom")

        policy = RetryPolicy().attempts(10).no_delay().keep_history(3).return_result()
        result = policy.run(always_fail)

        assert result.total_attempts == 10
        assert result.failed_attempts == 10
        assert result.successful_attempts == 0
        assert len(result.attempts) <= 3

    def test_result_based_retry_counts_successful(self) -> None:
        call_count = [0]

        def bad_then_good() -> str:
            call_count[0] += 1
            if call_count[0] < 3:
                return "bad"
            return "good"

        policy = (
            RetryPolicy()
            .attempts(5)
            .no_delay()
            .retry_if_result(lambda v: v == "bad")
            .return_result()
        )
        result = policy.run(bad_then_good)

        assert result.total_attempts == 3
        assert result.failed_attempts == 0
        assert result.successful_attempts == 3


# ---------------------------------------------------------------------------
# Async executor
# ---------------------------------------------------------------------------


class TestAsyncExecutorMetrics:
    async def test_all_failed(self) -> None:
        calls = [0]

        async def always_fail() -> None:
            calls[0] += 1
            raise ValueError("async boom")

        policy = RetryPolicy().attempts(3).no_delay().return_result()
        result = await policy.run_async(always_fail)

        assert result.failed_attempts == 3
        assert result.successful_attempts == 0

    async def test_truthful_with_bounded_history(self) -> None:
        calls = [0]

        async def always_fail() -> None:
            calls[0] += 1
            raise ValueError("async boom")

        policy = RetryPolicy().attempts(10).no_delay().keep_history(3).return_result()
        result = await policy.run_async(always_fail)

        assert result.total_attempts == 10
        assert result.failed_attempts == 10
        assert result.successful_attempts == 0
        assert len(result.attempts) <= 3


# ---------------------------------------------------------------------------
# Context manager
# ---------------------------------------------------------------------------


class TestContextManagerMetrics:
    def test_sync_exception_path(self) -> None:
        policy = RetryPolicy().attempts(3).no_delay().return_result()
        iterator = policy.iter()
        for attempt in iterator:
            with attempt:
                raise ValueError("boom")

        result = iterator.result
        assert result is not None
        assert result.failed_attempts == 3
        assert result.successful_attempts == 0

    def test_sync_success_path(self) -> None:
        call_count = [0]
        policy = RetryPolicy().attempts(5).no_delay().retry_if_result(lambda v: v < 3)
        iterator = policy.iter()
        for attempt in iterator:
            with attempt:
                call_count[0] += 1
                attempt.set_result(call_count[0])

        result = iterator.result
        assert result is not None
        assert result.total_attempts == 3
        assert result.successful_attempts == 3
        assert result.failed_attempts == 0

    def test_sync_bounded_history_truthful(self) -> None:
        policy = RetryPolicy().attempts(10).no_delay().keep_history(3).return_result()
        iterator = policy.iter()
        for attempt in iterator:
            with attempt:
                raise ValueError("boom")

        result = iterator.result
        assert result is not None
        assert result.total_attempts == 10
        assert result.failed_attempts == 10
        assert result.successful_attempts == 0
        assert len(result.attempts) <= 3

    async def test_async_exception_path(self) -> None:
        policy = RetryPolicy().attempts(3).no_delay().return_result()
        iterator = policy.async_iter()
        async for attempt in iterator:
            async with attempt:
                raise ValueError("async boom")

        result = iterator.result
        assert result is not None
        assert result.failed_attempts == 3
        assert result.successful_attempts == 0

    async def test_async_bounded_history_truthful(self) -> None:
        policy = RetryPolicy().attempts(10).no_delay().keep_history(3).return_result()
        iterator = policy.async_iter()
        async for attempt in iterator:
            async with attempt:
                raise ValueError("boom")

        result = iterator.result
        assert result is not None
        assert result.total_attempts == 10
        assert result.failed_attempts == 10
        assert result.successful_attempts == 0
        assert len(result.attempts) <= 3
