"""
Regression tests for C1: outcome/has_outcome on RetryBlockIterator
and AsyncRetryBlockIterator.

After exhaustion the iterator.outcome holds the resolved fallback value and
iterator.has_outcome is True. Before completion has_outcome must be False.
"""

from __future__ import annotations

import pytest

from relinker import RetryPolicy
from relinker.result import RetryResult

# ---------------------------------------------------------------------------
# Sync — exception-path exhaustion
# ---------------------------------------------------------------------------


class TestSyncOutcomeExceptionPath:
    def test_has_outcome_false_before_completion(self) -> None:
        policy = RetryPolicy().attempts(3).no_delay().return_result()
        iterator = policy.iter()
        for attempt in iterator:
            with attempt:
                assert not iterator.has_outcome
                raise ValueError("boom")

    def test_fallback_value_via_return_result(self) -> None:
        policy = RetryPolicy().attempts(2).no_delay().return_result()
        iterator = policy.iter()
        for attempt in iterator:
            with attempt:
                raise ValueError("boom")

        assert iterator.has_outcome
        assert isinstance(iterator.outcome, RetryResult)
        assert iterator.outcome.exhausted

    def test_fallback_value_via_on_exhausted_return(self) -> None:
        policy = RetryPolicy().attempts(2).no_delay().on_exhausted_return(lambda r: 42)
        iterator = policy.iter()
        for attempt in iterator:
            with attempt:
                raise ValueError("boom")

        assert iterator.has_outcome
        assert iterator.outcome == 42

    def test_on_exhausted_raise_does_not_set_has_outcome(self) -> None:
        policy = RetryPolicy().attempts(2).no_delay().on_exhausted_raise(RuntimeError("exhausted!"))
        iterator = policy.iter()
        with pytest.raises(RuntimeError, match="exhausted!"):
            for attempt in iterator:
                with attempt:
                    raise ValueError("boom")

        assert not iterator.has_outcome

    def test_raise_last_does_not_set_has_outcome(self) -> None:
        policy = RetryPolicy().attempts(2).no_delay()
        iterator = policy.iter()
        with pytest.raises(ValueError, match="boom"):
            for attempt in iterator:
                with attempt:
                    raise ValueError("boom")

        assert not iterator.has_outcome

    def test_result_available_alongside_outcome(self) -> None:
        policy = RetryPolicy().attempts(2).no_delay().return_result()
        iterator = policy.iter()
        for attempt in iterator:
            with attempt:
                raise ValueError("boom")

        assert iterator.result is not None
        assert iterator.has_outcome
        assert iterator.outcome is iterator.result


# ---------------------------------------------------------------------------
# Sync — result-path exhaustion
# ---------------------------------------------------------------------------


class TestSyncOutcomeResultPath:
    def test_fallback_value_result_path_return_result(self) -> None:
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

        assert iterator.has_outcome
        assert isinstance(iterator.outcome, RetryResult)

    def test_fallback_value_result_path_on_exhausted_return(self) -> None:
        policy = (
            RetryPolicy()
            .attempts(2)
            .no_delay()
            .retry_if_result(lambda v: v == "bad")
            .on_exhausted_return(lambda r: "recovered")
        )
        iterator = policy.iter()
        for attempt in iterator:
            with attempt:
                attempt.set_result("bad")

        assert iterator.has_outcome
        assert iterator.outcome == "recovered"


# ---------------------------------------------------------------------------
# Async — exception-path exhaustion
# ---------------------------------------------------------------------------


class TestAsyncOutcomeExceptionPath:
    async def test_has_outcome_false_before_completion(self) -> None:
        policy = RetryPolicy().attempts(3).no_delay().return_result()
        iterator = policy.async_iter()
        async for attempt in iterator:
            async with attempt:
                assert not iterator.has_outcome
                raise ValueError("boom")

    async def test_fallback_value_via_return_result(self) -> None:
        policy = RetryPolicy().attempts(2).no_delay().return_result()
        iterator = policy.async_iter()
        async for attempt in iterator:
            async with attempt:
                raise ValueError("boom")

        assert iterator.has_outcome
        assert isinstance(iterator.outcome, RetryResult)
        assert iterator.outcome.exhausted

    async def test_fallback_value_via_on_exhausted_return(self) -> None:
        policy = RetryPolicy().attempts(2).no_delay().on_exhausted_return(lambda r: 99)
        iterator = policy.async_iter()
        async for attempt in iterator:
            async with attempt:
                raise ValueError("boom")

        assert iterator.has_outcome
        assert iterator.outcome == 99

    async def test_on_exhausted_raise_does_not_set_has_outcome(self) -> None:
        policy = (
            RetryPolicy()
            .attempts(2)
            .no_delay()
            .on_exhausted_raise(RuntimeError("async-exhausted!"))
        )
        iterator = policy.async_iter()
        with pytest.raises(RuntimeError, match="async-exhausted!"):
            async for attempt in iterator:
                async with attempt:
                    raise ValueError("boom")

        assert not iterator.has_outcome

    async def test_result_path_outcome(self) -> None:
        policy = (
            RetryPolicy()
            .attempts(2)
            .no_delay()
            .retry_if_result(lambda v: v == "bad")
            .on_exhausted_return(lambda r: "async-recovered")
        )
        iterator = policy.async_iter()
        async for attempt in iterator:
            async with attempt:
                attempt.set_result("bad")

        assert iterator.has_outcome
        assert iterator.outcome == "async-recovered"
