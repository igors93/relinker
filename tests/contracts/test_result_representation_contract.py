"""Contracts for history retention and RetryResult representations."""

from __future__ import annotations

import json

from relinker import RetryPolicy

from ._support import policy_without_sleep


def test_history_limit_one_keeps_only_final_record_and_full_totals() -> None:
    calls = 0

    def operation() -> str:
        nonlocal calls
        calls += 1
        if calls < 3:
            raise TimeoutError(f"failure-{calls}")
        return "ok"

    result = (
        policy_without_sleep(RetryPolicy().attempts(3).on(TimeoutError).keep_history(1))
        .return_result()
        .run(operation)
    )
    assert result.attempt_count == 3
    assert result.retained_attempt_count == 1
    assert result.history_truncated is True
    assert result.attempts[0].number == 3
    assert result.failed_attempts == 2
    assert result.successful_attempts == 1


def test_unbounded_history_preserves_all_attempt_numbers() -> None:
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
    assert [attempt.number for attempt in result.attempts] == [1, 2, 3, 4]
    assert result.history_truncated is False


def test_last_error_returns_latest_retained_error_before_success() -> None:
    calls = 0

    def operation() -> str:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise TimeoutError("first")
        if calls == 2:
            raise ConnectionError("second")
        return "ok"

    result = (
        policy_without_sleep(RetryPolicy().attempts(3).on(TimeoutError, ConnectionError))
        .return_result()
        .run(operation)
    )
    assert isinstance(result.last_error, ConnectionError)
    assert str(result.last_error) == "second"


def test_error_types_preserve_first_seen_distinct_order() -> None:
    calls = 0

    def operation() -> str:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise TimeoutError("first")
        if calls == 2:
            raise ConnectionError("second")
        if calls == 3:
            raise TimeoutError("third")
        return "ok"

    result = (
        policy_without_sleep(RetryPolicy().attempts(4).on(TimeoutError, ConnectionError))
        .return_result()
        .run(operation)
    )
    assert result.error_types == (TimeoutError, ConnectionError)


def test_summary_excludes_exception_messages_and_values() -> None:
    secret = "token=super-secret"
    result = (
        policy_without_sleep(RetryPolicy().attempts(1).return_result())
        .run(lambda: (_ for _ in ()).throw(RuntimeError(secret)))
    )
    summary = result.summary()
    assert secret not in repr(summary)
    assert "value" not in summary
    assert summary["error"] == "RuntimeError"


def test_to_dict_redacts_top_level_and_attempt_error_messages() -> None:
    secret = "private-payload"
    result = RetryPolicy().attempts(1).return_result().run(
        lambda: (_ for _ in ()).throw(RuntimeError(secret))
    )
    data = result.to_dict(include_error_message=False)
    assert data["error"] == {"type": "RuntimeError", "message": None}
    assert data["attempts"][0]["error_message"] is None  # type: ignore[index]
    assert secret not in repr(data)


def test_to_json_is_valid_json_with_redaction() -> None:
    result = RetryPolicy().attempts(1).return_result().run(
        lambda: (_ for _ in ()).throw(RuntimeError("secret"))
    )
    data = json.loads(result.to_json(include_error_message=False))
    assert data["failed"] is True
    assert data["error"]["type"] == "RuntimeError"
    assert data["error"]["message"] is None


def test_to_dict_omits_value_by_default() -> None:
    result = RetryPolicy().return_result().run(lambda: {"large": "object"})
    assert "value" not in result.to_dict()


def test_to_dict_includes_value_only_when_requested() -> None:
    value = {"status": "ok"}
    result = RetryPolicy().return_result().run(lambda: value)
    data = result.to_dict(include_value=True)
    assert data["value"] is value


def test_story_can_redact_exception_message() -> None:
    secret = "password=123"
    result = RetryPolicy().attempts(1).return_result().run(
        lambda: (_ for _ in ()).throw(RuntimeError(secret))
    )
    story = result.story(include_error_message=False)
    assert "RuntimeError" in story
    assert secret not in story


def test_last_attempt_returns_final_retained_attempt() -> None:
    calls = 0

    def operation() -> str:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise TimeoutError("temporary")
        return "ok"

    result = (
        policy_without_sleep(RetryPolicy().attempts(2).on(TimeoutError))
        .return_result()
        .run(operation)
    )
    assert result.last_attempt() is result.attempts[-1]
    assert result.last_attempt() is not None
    assert result.last_attempt().number == 2  # type: ignore[union-attr]


def test_total_time_is_non_negative_for_normal_execution() -> None:
    result = RetryPolicy().return_result().run(lambda: "ok")
    assert result.total_time >= 0
    assert result.ended_at >= result.started_at
