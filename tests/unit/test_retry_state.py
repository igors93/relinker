"""Tests for RetryState properties and fields."""

from __future__ import annotations

from relinker.attempt import AttemptRecord
from relinker.state import RetryState


def _attempt(
    number: int, error: BaseException | None = None, value: object = None
) -> AttemptRecord:
    return AttemptRecord(
        number=number,
        started_at=0.0,
        ended_at=0.1,
        error=error,
        value=value,
    )


def test_attempt_count_empty() -> None:
    state = RetryState(function_name="t", attempt_number=1, started_at=0.0, elapsed=0.0)
    assert state.attempt_count == 0


def test_attempt_count_with_attempts() -> None:
    state = RetryState(
        function_name="t",
        attempt_number=3,
        started_at=0.0,
        elapsed=0.0,
        attempts=(_attempt(1, ValueError("e")), _attempt(2, ValueError("e")), _attempt(3)),
    )
    assert state.attempt_count == 3


def test_failed_attempts_all_failed() -> None:
    state = RetryState(
        function_name="t",
        attempt_number=2,
        started_at=0.0,
        elapsed=0.0,
        attempts=(_attempt(1, ValueError("e")), _attempt(2, OSError("e"))),
    )
    assert state.failed_attempts == 2


def test_failed_attempts_mixed() -> None:
    state = RetryState(
        function_name="t",
        attempt_number=3,
        started_at=0.0,
        elapsed=0.0,
        attempts=(_attempt(1, ValueError("e")), _attempt(2), _attempt(3)),
    )
    assert state.failed_attempts == 1
    assert state.successful_attempts == 2


def test_successful_attempts_all_succeeded() -> None:
    state = RetryState(
        function_name="t",
        attempt_number=2,
        started_at=0.0,
        elapsed=0.0,
        attempts=(_attempt(1, value="a"), _attempt(2, value="b")),
    )
    assert state.successful_attempts == 2
    assert state.failed_attempts == 0


def test_last_attempt_empty() -> None:
    state = RetryState(function_name="t", attempt_number=1, started_at=0.0, elapsed=0.0)
    assert state.last_attempt() is None


def test_last_attempt_returns_most_recent() -> None:
    a1 = _attempt(1, ValueError("e"))
    a2 = _attempt(2)
    state = RetryState(
        function_name="t",
        attempt_number=2,
        started_at=0.0,
        elapsed=0.0,
        attempts=(a1, a2),
    )
    assert state.last_attempt() is a2


def test_has_error_true() -> None:
    state = RetryState(
        function_name="t",
        attempt_number=1,
        started_at=0.0,
        elapsed=0.0,
        last_error=ValueError("e"),
    )
    assert state.has_error is True


def test_has_error_false() -> None:
    state = RetryState(function_name="t", attempt_number=1, started_at=0.0, elapsed=0.0)
    assert state.has_error is False


def test_has_value_true() -> None:
    state = RetryState(
        function_name="t",
        attempt_number=1,
        started_at=0.0,
        elapsed=0.0,
        last_value="something",
        has_value=True,
    )
    assert state.has_value is True


def test_has_value_false_by_default() -> None:
    state = RetryState(
        function_name="t",
        attempt_number=1,
        started_at=0.0,
        elapsed=0.0,
        last_value="something",
    )
    assert state.has_value is False


def test_has_value_false_when_last_error_set() -> None:
    state = RetryState(
        function_name="t",
        attempt_number=1,
        started_at=0.0,
        elapsed=0.0,
        last_value="something",
        last_error=ValueError("e"),
    )
    assert state.has_value is False
