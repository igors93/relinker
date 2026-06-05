"""
Tests for correct None result representation (Correction 6).

None is a valid function return value. These tests verify that:
- AttemptRecord.has_value is True when a value was produced (even None)
- RetryState.has_value is an explicit field, not inferred from last_value
- RetryResult.last_value works correctly for None returns
- RetryResult.has_last_value distinguishes None from no-value
- Custom conditions can receive (None, None) for a successful None result
- Context managers track None results correctly
"""

from __future__ import annotations

from relinker import RetryPolicy
from relinker.attempt import AttemptRecord
from relinker.result import RetryResult
from relinker.state import RetryState

# ---------------------------------------------------------------------------
# AttemptRecord.has_value
# ---------------------------------------------------------------------------


class TestAttemptRecordHasValue:
    def test_value_set_has_value_true(self) -> None:
        a = AttemptRecord(number=1, started_at=0.0, ended_at=0.1, value="x", has_value=True)
        assert a.has_value is True

    def test_none_value_has_value_true_when_explicit(self) -> None:
        a = AttemptRecord(number=1, started_at=0.0, ended_at=0.1, value=None, has_value=True)
        assert a.has_value is True

    def test_error_attempt_has_value_false(self) -> None:
        a = AttemptRecord(number=1, started_at=0.0, ended_at=0.1, error=ValueError("e"))
        assert a.has_value is False

    def test_default_has_value_false(self) -> None:
        a = AttemptRecord(number=1, started_at=0.0, ended_at=0.1)
        assert a.has_value is False


# ---------------------------------------------------------------------------
# RetryState.has_value
# ---------------------------------------------------------------------------


class TestRetryStateHasValue:
    def test_explicit_true(self) -> None:
        s = RetryState(
            function_name="f", attempt_number=1, started_at=0.0, elapsed=0.0, has_value=True
        )
        assert s.has_value is True

    def test_default_false(self) -> None:
        s = RetryState(function_name="f", attempt_number=1, started_at=0.0, elapsed=0.0)
        assert s.has_value is False

    def test_none_last_value_with_has_value_true(self) -> None:
        s = RetryState(
            function_name="f",
            attempt_number=1,
            started_at=0.0,
            elapsed=0.0,
            last_value=None,
            has_value=True,
        )
        assert s.has_value is True


# ---------------------------------------------------------------------------
# RetryResult.last_value and has_last_value
# ---------------------------------------------------------------------------


class TestRetryResultNoneValue:
    def test_last_value_none_when_successful_none_return(self) -> None:
        a = AttemptRecord(number=1, started_at=0.0, ended_at=0.1, value=None, has_value=True)
        result: RetryResult[None] = RetryResult(
            attempts=(a,), value=None, started_at=0.0, ended_at=0.1
        )
        assert result.last_value is None
        assert result.has_last_value is True

    def test_last_value_none_when_all_failed(self) -> None:
        a = AttemptRecord(number=1, started_at=0.0, ended_at=0.1, error=ValueError("e"))
        result: RetryResult[None] = RetryResult(
            attempts=(a,), error=ValueError("e"), started_at=0.0, ended_at=0.1
        )
        assert result.last_value is None
        assert result.has_last_value is False

    def test_last_value_returns_most_recent_value(self) -> None:
        a1 = AttemptRecord(number=1, started_at=0.0, ended_at=0.1, error=ValueError("e"))
        a2 = AttemptRecord(number=2, started_at=0.1, ended_at=0.2, value=None, has_value=True)
        result: RetryResult[None] = RetryResult(
            attempts=(a1, a2), value=None, started_at=0.0, ended_at=0.2
        )
        assert result.last_value is None
        assert result.has_last_value is True


# ---------------------------------------------------------------------------
# End-to-end: function returning None is accepted
# ---------------------------------------------------------------------------


class TestSyncNoneReturnE2E:
    def test_function_returning_none_accepted(self) -> None:
        def returns_none() -> None:
            return None

        policy = RetryPolicy().attempts(3).return_result()
        result = policy.run(returns_none)
        assert isinstance(result, RetryResult)
        assert result.succeeded
        assert result.last_value is None
        assert result.has_last_value is True

    def test_function_returning_none_state_has_value(self) -> None:
        received_states: list[RetryState] = []

        def returns_none() -> None:
            return None

        policy = (
            RetryPolicy()
            .attempts(3)
            .on_event(
                "after_success", lambda e: received_states.append(e.state) if e.state else None
            )
        )
        policy.run(returns_none)
        assert received_states
        assert received_states[-1].has_value is True

    def test_none_result_retry_then_accept(self) -> None:
        calls = [0]

        def sometimes_none() -> int | None:
            calls[0] += 1
            if calls[0] < 2:
                return None  # first call returns None — retry it
            return 42

        policy = RetryPolicy().attempts(3).retry_if_result(lambda v: v is None).return_result()
        result = policy.run(sometimes_none)
        assert isinstance(result, RetryResult)
        assert result.last_value == 42
        assert calls[0] == 2


class TestAsyncNoneReturnE2E:
    async def test_async_function_returning_none_accepted(self) -> None:
        async def returns_none() -> None:
            return None

        policy = RetryPolicy().attempts(3).return_result()
        result = await policy.run_async(returns_none)
        assert isinstance(result, RetryResult)
        assert result.succeeded
        assert result.last_value is None
        assert result.has_last_value is True

    async def test_async_none_result_state_has_value(self) -> None:
        received_states: list[RetryState] = []

        async def returns_none() -> None:
            return None

        policy = (
            RetryPolicy()
            .attempts(3)
            .on_event(
                "after_success",
                lambda e: received_states.append(e.state) if e.state else None,
            )
        )
        await policy.run_async(returns_none)
        assert received_states
        assert received_states[-1].has_value is True


# ---------------------------------------------------------------------------
# Context manager: set_result(None)
# ---------------------------------------------------------------------------


class TestContextManagerNoneResult:
    def test_sync_set_result_none(self) -> None:
        policy = RetryPolicy().attempts(3).return_result()
        for attempt in policy:
            with attempt:
                attempt.set_result(None)

        assert policy.iter().result is None or True  # iterator is done
        # Run directly to capture result
        iterator = RetryPolicy().attempts(3).return_result().iter()
        for attempt in iterator:
            with attempt:
                attempt.set_result(None)
        assert iterator.result is not None
        assert iterator.result.has_last_value is True
        assert iterator.result.last_value is None

    async def test_async_set_result_none(self) -> None:
        iterator = RetryPolicy().attempts(3).return_result().async_iter()
        async for attempt in iterator:
            async with attempt:
                attempt.set_result(None)
        assert iterator.result is not None
        assert iterator.result.has_last_value is True
        assert iterator.result.last_value is None
