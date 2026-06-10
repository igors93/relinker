"""Regression tests: sensitive data is not exposed via repr or default logging."""

from __future__ import annotations

import contextlib
import logging

import pytest

from relinker import RetryPolicy
from relinker.attempt import AttemptRecord
from relinker.event import RetryEvent
from relinker.result import RetryResult
from relinker.state import RetryState

# ---------------------------------------------------------------------------
# Sentinel objects whose __str__ / __repr__ track calls and may raise
# ---------------------------------------------------------------------------


class _TrackingStr:
    """Value whose repr/str increments a counter."""

    def __init__(self, secret: str) -> None:
        self._secret = secret
        self.repr_calls = 0
        self.str_calls = 0

    def __repr__(self) -> str:
        self.repr_calls += 1
        return f"TRACKING_REPR({self._secret})"

    def __str__(self) -> str:
        self.str_calls += 1
        return f"TRACKING_STR({self._secret})"


class _ExplodingStr:
    """Value whose repr/str raises an exception."""

    def __repr__(self) -> str:
        raise RuntimeError("repr should not be called")

    def __str__(self) -> str:
        raise RuntimeError("str should not be called")


class _SecretError(Exception):
    def __init__(self, secret: str) -> None:
        super().__init__(secret)
        self._secret = secret

    def __str__(self) -> str:
        return f"SECRET:{self._secret}"

    def __repr__(self) -> str:
        return f"SecretError(SECRET:{self._secret})"


class _FailingStrError(Exception):
    def __str__(self) -> str:
        raise RuntimeError("__str__ failed")

    def __repr__(self) -> str:
        raise RuntimeError("__repr__ failed")


# ---------------------------------------------------------------------------
# AttemptRecord: value and error excluded from repr
# ---------------------------------------------------------------------------


def test_attempt_record_repr_excludes_value() -> None:
    secret = _TrackingStr("my-api-key")
    record = AttemptRecord(number=1, started_at=0.0, ended_at=1.0, value=secret, has_value=True)
    r = repr(record)
    assert "my-api-key" not in r
    assert "TRACKING_REPR" not in r
    assert secret.repr_calls == 0, "repr was called on sensitive value"


def test_attempt_record_repr_excludes_error() -> None:
    error = _SecretError("token=abc123")
    record = AttemptRecord(number=1, started_at=0.0, ended_at=1.0, error=error)
    r = repr(record)
    assert "token=abc123" not in r
    assert "SECRET:" not in r


def test_attempt_record_value_still_accessible() -> None:
    secret = _TrackingStr("secret")
    record = AttemptRecord(number=1, started_at=0.0, ended_at=1.0, value=secret, has_value=True)
    assert record.value is secret


def test_attempt_record_error_still_accessible() -> None:
    error = _SecretError("payload")
    record = AttemptRecord(number=1, started_at=0.0, ended_at=1.0, error=error)
    assert record.error is error


def test_attempt_record_repr_does_not_call_exploding_value() -> None:
    record = AttemptRecord(
        number=1, started_at=0.0, ended_at=1.0, value=_ExplodingStr(), has_value=True
    )
    repr(record)  # must not raise


def test_attempt_record_repr_does_not_call_exploding_error() -> None:
    try:
        raise _ExplodingStr()  # type: ignore[misc]
    except Exception as exc:
        error = exc

    record = AttemptRecord(number=1, started_at=0.0, ended_at=1.0, error=error)
    repr(record)  # must not raise


# ---------------------------------------------------------------------------
# RetryResult: value and error excluded from repr
# ---------------------------------------------------------------------------


def test_retry_result_repr_excludes_value() -> None:
    secret = _TrackingStr("password=hunter2")
    result = RetryResult(attempts=(), value=secret, total_attempts=1)
    r = repr(result)
    assert "password=hunter2" not in r
    assert "TRACKING_REPR" not in r
    assert secret.repr_calls == 0


def test_retry_result_repr_excludes_error() -> None:
    error = _SecretError("bearer-token-xyz")
    result = RetryResult(attempts=(), error=error, total_attempts=1, exhausted=True)
    r = repr(result)
    assert "bearer-token-xyz" not in r


def test_retry_result_value_still_accessible() -> None:
    sentinel = object()
    result = RetryResult(attempts=(), value=sentinel, total_attempts=1)
    assert result.value is sentinel


def test_retry_result_error_still_accessible() -> None:
    error = _SecretError("payload")
    result = RetryResult(attempts=(), error=error, total_attempts=1, exhausted=True)
    assert result.error is error


# ---------------------------------------------------------------------------
# RetryState: last_value and last_error excluded from repr
# ---------------------------------------------------------------------------


def test_retry_state_repr_excludes_last_value() -> None:
    secret = _TrackingStr("oauth-token")
    state = RetryState(
        function_name="fn",
        attempt_number=1,
        started_at=0.0,
        elapsed=0.1,
        last_value=secret,
        has_value=True,
    )
    r = repr(state)
    assert "oauth-token" not in r
    assert "TRACKING_REPR" not in r
    assert secret.repr_calls == 0


def test_retry_state_repr_excludes_last_error() -> None:
    error = _SecretError("session-secret")
    state = RetryState(
        function_name="fn",
        attempt_number=1,
        started_at=0.0,
        elapsed=0.1,
        last_error=error,
    )
    r = repr(state)
    assert "session-secret" not in r


def test_retry_state_last_value_accessible() -> None:
    sentinel = object()
    state = RetryState(
        function_name="fn", attempt_number=1, started_at=0.0, elapsed=0.0, last_value=sentinel
    )
    assert state.last_value is sentinel


# ---------------------------------------------------------------------------
# RetryEvent: value and error excluded from repr
# ---------------------------------------------------------------------------


def test_retry_event_repr_excludes_value() -> None:
    secret = _TrackingStr("private-key")
    event = RetryEvent(name="after_success", attempt_number=1, function_name="fn", value=secret)
    r = repr(event)
    assert "private-key" not in r
    assert "TRACKING_REPR" not in r
    assert secret.repr_calls == 0


def test_retry_event_repr_excludes_error() -> None:
    error = _SecretError("credit-card-number")
    event = RetryEvent(name="after_failure", attempt_number=1, function_name="fn", error=error)
    r = repr(event)
    assert "credit-card-number" not in r


# ---------------------------------------------------------------------------
# Conventional logging: default does NOT include error message
# ---------------------------------------------------------------------------


def test_with_logging_default_giveup_excludes_error_message(
    caplog: pytest.LogCaptureFixture,
) -> None:
    error = _SecretError("db-password-secret")
    call_count = 0

    def fail() -> None:
        nonlocal call_count
        call_count += 1
        raise error

    policy = RetryPolicy().attempts(2).with_logging(level=logging.WARNING)

    with caplog.at_level(logging.WARNING), contextlib.suppress(_SecretError):
        policy.run(fail)

    messages = "\n".join(caplog.messages)
    assert "db-password-secret" not in messages
    assert "SECRET:" not in messages


def test_with_logging_explicit_includes_error_message(
    caplog: pytest.LogCaptureFixture,
) -> None:
    error = _SecretError("traceable-secret")
    call_count = 0

    def fail() -> None:
        nonlocal call_count
        call_count += 1
        raise error

    policy = (
        RetryPolicy().attempts(2).with_logging(level=logging.WARNING, include_error_message=True)
    )

    with caplog.at_level(logging.WARNING), contextlib.suppress(_SecretError):
        policy.run(fail)

    messages = "\n".join(caplog.messages)
    assert "traceable-secret" in messages


# ---------------------------------------------------------------------------
# debug(): default does NOT include error message
# ---------------------------------------------------------------------------


def test_debug_default_does_not_print_error_message(
    capsys: pytest.CaptureFixture[str],
) -> None:
    error = _SecretError("private-data")
    call_count = 0

    def fail() -> None:
        nonlocal call_count
        call_count += 1
        raise error

    policy = RetryPolicy().attempts(2).for_testing().debug()

    with contextlib.suppress(_SecretError):
        policy.run(fail)

    captured = capsys.readouterr()
    assert "private-data" not in captured.out
    assert "SECRET:" not in captured.out
    assert "failed" in captured.out


def test_debug_explicit_includes_error_message(
    capsys: pytest.CaptureFixture[str],
) -> None:
    error = _SecretError("traceable-data")
    call_count = 0

    def fail() -> None:
        nonlocal call_count
        call_count += 1
        raise error

    policy = RetryPolicy().attempts(2).for_testing().debug(include_error_message=True)

    with contextlib.suppress(_SecretError):
        policy.run(fail)

    captured = capsys.readouterr()
    assert "traceable-data" in captured.out


def test_debug_handles_failing_str_in_error(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """debug() with include_error_message=True must not crash when __str__ fails."""
    error = _FailingStrError("broken")
    call_count = 0

    def fail() -> None:
        nonlocal call_count
        call_count += 1
        raise error

    policy = RetryPolicy().attempts(2).for_testing().debug(include_error_message=True)

    with contextlib.suppress(_FailingStrError):
        policy.run(fail)

    captured = capsys.readouterr()
    assert "error rendering message" in captured.out


# ---------------------------------------------------------------------------
# Structured logging: already safe by default (regression guard)
# ---------------------------------------------------------------------------


def test_with_structured_logging_default_excludes_error_message(
    caplog: pytest.LogCaptureFixture,
) -> None:
    error = _SecretError("structured-secret")

    def fail() -> None:
        raise error

    policy = RetryPolicy().attempts(2).with_structured_logging(level=logging.INFO)

    with caplog.at_level(logging.INFO), contextlib.suppress(_SecretError):
        policy.run(fail)

    messages = "\n".join(caplog.messages)
    assert "structured-secret" not in messages


# ---------------------------------------------------------------------------
# repr does not invoke __str__ or __repr__ on sensitive objects
# ---------------------------------------------------------------------------


def test_repr_does_not_call_tracking_str_repr() -> None:
    sentinel = _TrackingStr("key")
    error = _SecretError("secret")

    record = AttemptRecord(number=1, started_at=0.0, ended_at=1.0, value=sentinel, error=error)
    result = RetryResult(attempts=(record,), value=sentinel, error=error, total_attempts=1)
    state = RetryState(
        function_name="f",
        attempt_number=1,
        started_at=0.0,
        elapsed=0.0,
        last_value=sentinel,
        last_error=error,
    )
    event = RetryEvent(
        name="after_failure", attempt_number=1, function_name="f", value=sentinel, error=error
    )

    repr(record)
    repr(result)
    repr(state)
    repr(event)

    assert sentinel.repr_calls == 0, "repr() was called on sensitive value"
    assert sentinel.str_calls == 0, "str() was called on sensitive value"
