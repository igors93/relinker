"""Tests for the new RetryResult properties and summary()."""

from __future__ import annotations

import json

from relinker.attempt import AttemptRecord
from relinker.result import RetryResult


def _make_result_with_failures(n_failures: int, then_succeed: bool = True) -> RetryResult[str]:
    attempts = []
    for i in range(n_failures):
        attempts.append(
            AttemptRecord(
                number=i + 1,
                started_at=float(i),
                ended_at=float(i) + 0.1,
                error=ValueError(f"fail {i}"),
            )
        )
    if then_succeed:
        attempts.append(
            AttemptRecord(
                number=n_failures + 1,
                started_at=float(n_failures),
                ended_at=float(n_failures) + 0.1,
                value="ok",
            )
        )
    return RetryResult(
        attempts=tuple(attempts),
        value="ok" if then_succeed else None,
        error=None if then_succeed else ValueError("final"),
        started_at=0.0,
        ended_at=float(n_failures) + 0.1,
    )


def test_last_error_when_all_failed() -> None:
    attempt1 = AttemptRecord(number=1, started_at=0.0, ended_at=0.1, error=ValueError("first"))
    attempt2 = AttemptRecord(number=2, started_at=0.1, ended_at=0.2, error=OSError("second"))
    result: RetryResult[str] = RetryResult(
        attempts=(attempt1, attempt2),
        error=OSError("second"),
        started_at=0.0,
        ended_at=0.2,
    )
    assert isinstance(result.last_error, OSError)
    assert str(result.last_error) == "second"


def test_last_error_when_later_attempt_succeeded() -> None:
    result = _make_result_with_failures(2, then_succeed=True)
    assert isinstance(result.last_error, ValueError)


def test_last_error_no_errors_returns_none() -> None:
    attempt = AttemptRecord(number=1, started_at=0.0, ended_at=0.1, value="ok")
    result: RetryResult[str] = RetryResult(
        attempts=(attempt,), value="ok", started_at=0.0, ended_at=0.1
    )
    assert result.last_error is None


def test_last_value_from_latest_successful_attempt() -> None:
    attempt1 = AttemptRecord(number=1, started_at=0.0, ended_at=0.1, value="first", has_value=True)
    attempt2 = AttemptRecord(number=2, started_at=0.1, ended_at=0.2, value="second", has_value=True)
    result: RetryResult[str] = RetryResult(
        attempts=(attempt1, attempt2), value="second", started_at=0.0, ended_at=0.2
    )
    assert result.last_value == "second"


def test_last_value_all_failed_returns_none() -> None:
    attempt = AttemptRecord(number=1, started_at=0.0, ended_at=0.1, error=ValueError("fail"))
    result: RetryResult[str] = RetryResult(
        attempts=(attempt,), error=ValueError("fail"), started_at=0.0, ended_at=0.1
    )
    assert result.last_value is None


def test_failed_attempts_count() -> None:
    result = _make_result_with_failures(3, then_succeed=True)
    assert result.failed_attempts == 3


def test_failed_attempts_all_failed() -> None:
    result = _make_result_with_failures(2, then_succeed=False)
    assert result.failed_attempts == 2


def test_successful_attempts_count() -> None:
    result = _make_result_with_failures(2, then_succeed=True)
    assert result.successful_attempts == 1


def test_successful_attempts_all_failed() -> None:
    result = _make_result_with_failures(3, then_succeed=False)
    assert result.successful_attempts == 0


def test_error_types_distinct_types() -> None:
    attempt1 = AttemptRecord(number=1, started_at=0.0, ended_at=0.1, error=ValueError("v"))
    attempt2 = AttemptRecord(number=2, started_at=0.1, ended_at=0.2, error=OSError("o"))
    attempt3 = AttemptRecord(number=3, started_at=0.2, ended_at=0.3, error=ValueError("v2"))
    result: RetryResult[str] = RetryResult(
        attempts=(attempt1, attempt2, attempt3),
        started_at=0.0,
        ended_at=0.3,
    )
    types = result.error_types
    assert ValueError in types
    assert OSError in types
    assert len(types) == 2


def test_error_types_empty_when_no_errors() -> None:
    attempt = AttemptRecord(number=1, started_at=0.0, ended_at=0.1, value="ok")
    result: RetryResult[str] = RetryResult(
        attempts=(attempt,), value="ok", started_at=0.0, ended_at=0.1
    )
    assert result.error_types == ()


def test_summary_returns_dict() -> None:
    result = _make_result_with_failures(2, then_succeed=True)
    s = result.summary()
    assert isinstance(s, dict)
    assert "succeeded" in s
    assert "exhausted" in s
    assert "attempt_count" in s
    assert "failed_attempts" in s
    assert "total_time" in s
    assert "error" in s
    assert "error_types" in s


def test_summary_no_value_included() -> None:
    result = _make_result_with_failures(0, then_succeed=True)
    s = result.summary()
    assert "value" not in s


def test_summary_succeeded_case() -> None:
    result = _make_result_with_failures(0, then_succeed=True)
    s = result.summary()
    assert s["succeeded"] is True
    assert s["error"] is None
    assert s["error_types"] == []


def test_summary_failed_case() -> None:
    result = _make_result_with_failures(2, then_succeed=False)
    s = result.summary()
    assert s["succeeded"] is False
    assert s["error"] == "ValueError"
    assert "ValueError" in s["error_types"]


def test_summary_total_time_rounded() -> None:
    attempt = AttemptRecord(number=1, started_at=0.0, ended_at=0.123456789, value="ok")
    result: RetryResult[str] = RetryResult(
        attempts=(attempt,), value="ok", started_at=0.0, ended_at=0.123456789
    )
    s = result.summary()
    assert s["total_time"] == 0.123


def test_summary_is_json_serializable() -> None:
    result = _make_result_with_failures(1, then_succeed=True)
    text = json.dumps(result.summary())
    assert isinstance(text, str)


# --- story() tests ---


def test_story_succeeded() -> None:
    result = _make_result_with_failures(0, then_succeed=True)
    text = result.story()
    assert "succeeded" in text
    assert "Status" in text
    assert "Attempts" in text


def test_story_exception_exhaustion() -> None:
    attempt = AttemptRecord(number=1, started_at=0.0, ended_at=0.1, error=TimeoutError("timeout"))
    result: RetryResult[str] = RetryResult(
        attempts=(attempt,),
        error=TimeoutError("timeout"),
        started_at=0.0,
        ended_at=0.1,
        exhausted=True,
        retry_cause="exception",
    )
    text = result.story()
    assert "exhausted by exception" in text
    assert "TimeoutError" in text


def test_story_result_exhaustion() -> None:
    attempt = AttemptRecord(number=1, started_at=0.0, ended_at=0.1, value=None)
    result: RetryResult[str] = RetryResult(
        attempts=(attempt,),
        value=None,
        started_at=0.0,
        ended_at=0.1,
        exhausted=True,
        retry_cause="result",
    )
    text = result.story()
    assert "exhausted by result" in text
    assert "rejected" in text


def test_story_with_try_again_exhaustion() -> None:
    from relinker.exceptions import TryAgain

    ta = TryAgain("still polling")
    attempt = AttemptRecord(number=1, started_at=0.0, ended_at=0.1, error=ta)
    result: RetryResult[str] = RetryResult(
        attempts=(attempt,),
        error=ta,
        started_at=0.0,
        ended_at=0.1,
        exhausted=True,
        retry_cause="exception",
    )
    text = result.story()
    assert "TryAgain" in text
    assert "exhausted" in text


# --- to_dict() tests ---


def test_to_dict_excludes_value_by_default() -> None:
    attempt = AttemptRecord(number=1, started_at=0.0, ended_at=0.1, value="sensitive")
    result: RetryResult[str] = RetryResult(
        attempts=(attempt,), value="sensitive", started_at=0.0, ended_at=0.1
    )
    d = result.to_dict()
    assert "value" not in d


def test_to_dict_includes_value_when_requested() -> None:
    attempt = AttemptRecord(number=1, started_at=0.0, ended_at=0.1, value="my_value")
    result: RetryResult[str] = RetryResult(
        attempts=(attempt,), value="my_value", started_at=0.0, ended_at=0.1
    )
    d = result.to_dict(include_value=True)
    assert "value" in d
    assert d["value"] == "my_value"


def test_to_dict_contains_expected_keys() -> None:
    result = _make_result_with_failures(1, then_succeed=True)
    d = result.to_dict()
    for key in ("succeeded", "failed", "exhausted", "retry_cause", "attempt_count", "total_time"):
        assert key in d


def test_to_dict_attempts_list() -> None:
    result = _make_result_with_failures(2, then_succeed=True)
    d = result.to_dict()
    assert isinstance(d["attempts"], list)
    assert len(d["attempts"]) == 3  # 2 failures + 1 success


# --- to_json() tests ---


def test_to_json_excludes_value_by_default() -> None:
    attempt = AttemptRecord(number=1, started_at=0.0, ended_at=0.1, value="secret")
    result: RetryResult[str] = RetryResult(
        attempts=(attempt,), value="secret", started_at=0.0, ended_at=0.1
    )
    text = result.to_json()
    parsed = json.loads(text)
    assert "value" not in parsed


def test_to_json_is_valid_json() -> None:
    result = _make_result_with_failures(2, then_succeed=True)
    text = result.to_json()
    parsed = json.loads(text)
    assert isinstance(parsed, dict)


def test_to_json_with_indent() -> None:
    result = _make_result_with_failures(1, then_succeed=True)
    text = result.to_json(indent=2)
    assert "\n" in text
    assert '"succeeded"' in text
