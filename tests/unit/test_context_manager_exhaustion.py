"""
Tests for context manager exhaustion behavior alignment (Correction 3).

Verifies that context managers apply the same finish_exhausted() behaviors
as normal executors: return_result, exhausted_callback, exhausted_exception_factory,
and raise behaviors, for both exception-path and result-path exhaustion.
"""

from __future__ import annotations

import pytest

from relinker import RetryPolicy
from relinker.exceptions import RetryExhaustedError
from relinker.result import RetryResult

# ---------------------------------------------------------------------------
# Exception-path exhaustion in sync context manager
# ---------------------------------------------------------------------------


class TestSyncExceptionExhaustionBehaviors:
    def test_return_result_suppresses_exception(self) -> None:
        policy = RetryPolicy().attempts(2).no_delay().return_result()
        iterator = policy.iter()
        for attempt in iterator:
            with attempt:
                raise ValueError("boom")

        assert iterator.result is not None
        assert iterator.result.exhausted
        assert iterator.result.retry_cause == "exception"

    def test_exhausted_callback_called_on_exception_exhaustion(self) -> None:
        received: list[RetryResult[None]] = []

        policy = (
            RetryPolicy().attempts(2).no_delay().on_exhausted_return(lambda r: received.append(r))
        )
        iterator = policy.iter()
        for attempt in iterator:
            with attempt:
                raise ValueError("boom")

        assert len(received) == 1
        assert received[0].exhausted

    def test_on_exhausted_raise_replaces_exception(self) -> None:
        policy = RetryPolicy().attempts(2).no_delay().on_exhausted_raise(RuntimeError("exhausted!"))
        iterator = policy.iter()
        with pytest.raises(RuntimeError, match="exhausted!"):
            for attempt in iterator:
                with attempt:
                    raise ValueError("boom")

    def test_non_retryable_exception_propagates(self) -> None:
        policy = (
            RetryPolicy()
            .attempts(5)
            .no_delay()
            .retry_if(lambda exc, val: isinstance(exc, TypeError))
        )
        iterator = policy.iter()
        with pytest.raises(ValueError, match="boom"):
            for attempt in iterator:
                with attempt:
                    raise ValueError("boom")

    def test_exhausted_by_exception_propagates_without_return_result(self) -> None:
        policy = RetryPolicy().attempts(2).no_delay()
        iterator = policy.iter()
        with pytest.raises(ValueError, match="boom"):
            for attempt in iterator:
                with attempt:
                    raise ValueError("boom")


# ---------------------------------------------------------------------------
# Result-path exhaustion in sync context manager
# ---------------------------------------------------------------------------


class TestSyncResultExhaustionBehaviors:
    def test_return_result_on_result_exhaustion(self) -> None:
        policy = (
            RetryPolicy()
            .attempts(2)
            .no_delay()
            .retry_if_result(lambda v: v == "bad")
            .return_result()
        )
        iterator = policy.iter()
        for attempt in iterator:
            with attempt:
                attempt.set_result("bad")

        assert iterator.result is not None
        assert iterator.result.exhausted
        assert iterator.result.retry_cause == "result"

    def test_result_exhausted_raises_when_configured(self) -> None:
        policy = (
            RetryPolicy()
            .attempts(2)
            .no_delay()
            .retry_if_result(lambda v: v == "bad")
            .raise_on_result_exhausted()
        )
        iterator = policy.iter()
        with pytest.raises(RetryExhaustedError):
            for attempt in iterator:
                with attempt:
                    attempt.set_result("bad")

    def test_exhausted_callback_on_result_exhaustion(self) -> None:
        received: list[RetryResult[str]] = []

        policy = (
            RetryPolicy()
            .attempts(2)
            .no_delay()
            .retry_if_result(lambda v: v == "bad")
            .on_exhausted_return(lambda r: received.append(r))
        )
        iterator = policy.iter()
        for attempt in iterator:
            with attempt:
                attempt.set_result("bad")

        assert len(received) == 1
        assert received[0].exhausted_by_result

    def test_result_budget_exhaustion_applies_behavior(self) -> None:
        """should_stop_before_sleep path also uses finish_exhausted."""
        policy = (
            RetryPolicy()
            .max_time(0.001)
            .no_delay()
            .retry_if_result(lambda v: v == "bad")
            .raise_on_result_exhausted()
        )
        iterator = policy.iter()
        with pytest.raises(RetryExhaustedError):
            for attempt in iterator:
                with attempt:
                    attempt.set_result("bad")


# ---------------------------------------------------------------------------
# Async context manager: same behaviors
# ---------------------------------------------------------------------------


class TestAsyncContextManagerExhaustionBehaviors:
    async def test_async_return_result_suppresses_exception(self) -> None:
        policy = RetryPolicy().attempts(2).no_delay().return_result()
        iterator = policy.async_iter()
        async for attempt in iterator:
            async with attempt:
                raise ValueError("boom")

        assert iterator.result is not None
        assert iterator.result.exhausted

    async def test_async_result_exhausted_raises(self) -> None:
        policy = (
            RetryPolicy()
            .attempts(2)
            .no_delay()
            .retry_if_result(lambda v: v == "bad")
            .raise_on_result_exhausted()
        )
        iterator = policy.async_iter()
        with pytest.raises(RetryExhaustedError):
            async for attempt in iterator:
                async with attempt:
                    attempt.set_result("bad")

    async def test_async_exhausted_callback_on_exception(self) -> None:
        received: list[RetryResult[None]] = []

        policy = (
            RetryPolicy().attempts(2).no_delay().on_exhausted_return(lambda r: received.append(r))
        )
        iterator = policy.async_iter()
        async for attempt in iterator:
            async with attempt:
                raise ValueError("boom")

        assert len(received) == 1
        assert received[0].exhausted
