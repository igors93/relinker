"""
Tests for bounded history growth (Correction 2).

Verifies that:
- history_limit = 1000 is the default
- keep_history(N) keeps only the last N AttemptRecords
- Attempt numbers remain globally correct (not derived from history length)
- RetryResult.attempt_count reflects total attempts (history may be smaller)
- None means unlimited
- Invalid values are rejected
- Sync and async executors and context managers follow the same retention rule
"""

from __future__ import annotations

import pytest

from relinker import RetryPolicy
from relinker.exceptions import InvalidRetryConfigError

# ---------------------------------------------------------------------------
# Policy configuration
# ---------------------------------------------------------------------------


class TestHistoryLimitConfig:
    def test_default_limit_is_1000(self) -> None:
        assert RetryPolicy().history_limit == 1000

    def test_keep_history_sets_limit(self) -> None:
        policy = RetryPolicy().keep_history(5)
        assert policy.history_limit == 5

    def test_keep_history_none_unlimited(self) -> None:
        policy = RetryPolicy().keep_history(None)
        assert policy.history_limit is None

    def test_keep_history_zero_rejected(self) -> None:
        with pytest.raises(InvalidRetryConfigError):
            RetryPolicy().keep_history(0)

    def test_keep_history_negative_rejected(self) -> None:
        with pytest.raises(InvalidRetryConfigError):
            RetryPolicy().keep_history(-1)

    def test_keep_history_bool_rejected(self) -> None:
        with pytest.raises(InvalidRetryConfigError):
            RetryPolicy().keep_history(True)  # type: ignore[arg-type]

    def test_direct_invalid_history_limit_rejected(self) -> None:
        from dataclasses import replace

        with pytest.raises(InvalidRetryConfigError):
            replace(RetryPolicy(), history_limit=0)


# ---------------------------------------------------------------------------
# Sync executor: retained records are latest N attempts
# ---------------------------------------------------------------------------


class TestSyncHistoryRetention:
    def test_history_bounded_to_limit(self) -> None:
        total_attempts = [0]

        def always_fails() -> None:
            total_attempts[0] += 1
            raise ValueError("fail")

        policy = RetryPolicy().attempts(10).keep_history(3).no_delay().return_result()
        result = policy.run(always_fails)
        assert len(result.attempts) == 3
        assert result.attempt_count == 10

    def test_retained_records_are_latest(self) -> None:
        call_count = [0]

        def always_fails() -> None:
            call_count[0] += 1
            raise ValueError(f"attempt {call_count[0]}")

        policy = RetryPolicy().attempts(5).keep_history(2).no_delay().return_result()
        result = policy.run(always_fails)
        assert len(result.attempts) == 2
        errors = [str(a.error) for a in result.attempts if a.error]
        assert errors == ["attempt 4", "attempt 5"]

    def test_attempt_numbers_are_global(self) -> None:
        policy = RetryPolicy().attempts(5).keep_history(2).no_delay().return_result()
        result = policy.run(lambda: (_ for _ in ()).throw(ValueError("x")))
        # last two attempts are 4 and 5
        assert [a.number for a in result.attempts] == [4, 5]

    def test_attempt_count_reflects_all_attempts(self) -> None:
        policy = RetryPolicy().attempts(7).keep_history(2).no_delay().return_result()
        result = policy.run(lambda: (_ for _ in ()).throw(ValueError("x")))
        assert result.attempt_count == 7
        assert len(result.attempts) == 2

    def test_unlimited_history_with_none(self) -> None:
        policy = RetryPolicy().attempts(20).keep_history(None).no_delay().return_result()
        result = policy.run(lambda: (_ for _ in ()).throw(ValueError("x")))
        assert len(result.attempts) == 20
        assert result.attempt_count == 20


# ---------------------------------------------------------------------------
# Async executor: same retention rule
# ---------------------------------------------------------------------------


class TestAsyncHistoryRetention:
    async def test_async_history_bounded(self) -> None:
        async def always_fails() -> None:
            raise ValueError("fail")

        policy = RetryPolicy().attempts(10).keep_history(3).no_delay().return_result()
        result = await policy.run_async(always_fails)
        assert len(result.attempts) == 3
        assert result.attempt_count == 10

    async def test_async_unlimited_history(self) -> None:
        async def always_fails() -> None:
            raise ValueError("fail")

        policy = RetryPolicy().attempts(10).keep_history(None).no_delay().return_result()
        result = await policy.run_async(always_fails)
        assert len(result.attempts) == 10


# ---------------------------------------------------------------------------
# Context manager: same retention rule
# ---------------------------------------------------------------------------


class TestContextManagerHistoryRetention:
    def test_sync_context_manager_history_bounded(self) -> None:
        policy = RetryPolicy().attempts(5).keep_history(2).no_delay()
        iterator = policy.iter()
        try:
            for attempt in iterator:
                with attempt:
                    raise ValueError("fail")
        except ValueError:
            pass

        assert iterator.result is not None
        assert len(iterator.result.attempts) == 2
        assert iterator.result.attempt_count == 5

    async def test_async_context_manager_history_bounded(self) -> None:
        policy = RetryPolicy().attempts(5).keep_history(2).no_delay()
        iterator = policy.async_iter()
        try:
            async for attempt in iterator:
                async with attempt:
                    raise ValueError("fail")
        except ValueError:
            pass

        assert iterator.result is not None
        assert len(iterator.result.attempts) == 2
        assert iterator.result.attempt_count == 5
