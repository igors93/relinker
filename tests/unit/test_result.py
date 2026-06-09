from __future__ import annotations

import json

from relinker.attempt import AttemptRecord
from relinker.result import RetryResult


def _failed_result(*errors: Exception, value: object = None) -> RetryResult[object]:
    attempts = tuple(
        AttemptRecord(
            number=index,
            started_at=float(index - 1),
            ended_at=float(index) - 0.5,
            error=error,
        )
        for index, error in enumerate(errors, start=1)
    )
    return RetryResult(
        attempts=attempts,
        value=value,
        error=errors[-1] if errors else None,
        started_at=0.0,
        ended_at=float(len(attempts)),
        exhausted=bool(errors),
        retry_cause="exception" if errors else None,
        total_attempts=len(attempts),
        total_failed_attempts=len(attempts),
        total_successful_attempts=0,
    )


def test_result_story_for_success() -> None:
    attempt = AttemptRecord(number=1, started_at=0.0, ended_at=0.1, value="ok")
    result = RetryResult(attempts=(attempt,), value="ok", started_at=0.0, ended_at=0.1)

    assert result.succeeded
    assert not result.failed
    assert result.attempt_count == 1
    assert "succeeded" in result.story()


def test_result_story_for_result_exhaustion() -> None:
    attempt = AttemptRecord(number=1, started_at=0.0, ended_at=0.1, value=None)
    result = RetryResult(
        attempts=(attempt,),
        value=None,
        started_at=0.0,
        ended_at=0.1,
        exhausted=True,
        retry_cause="result",
    )

    assert not result.succeeded
    assert result.failed
    assert result.exhausted_by_result
    assert "exhausted by result" in result.story()


def test_result_detailed_output_keeps_error_messages_by_default() -> None:
    result = _failed_result(RuntimeError("token=secret-value"))

    data = result.to_dict()

    assert data["error"] == {
        "type": "RuntimeError",
        "message": "token=secret-value",
    }
    assert data["attempts"][0]["error_message"] == "token=secret-value"
    assert "token=secret-value" in result.to_json()
    assert "RuntimeError: token=secret-value" in result.story()


def test_result_to_dict_can_exclude_all_error_messages() -> None:
    result = _failed_result(
        RuntimeError("api-key=first-secret"),
        TimeoutError("authorization=second-secret"),
    )

    data = result.to_dict(include_error_message=False)
    serialized = json.dumps(data)

    assert data["error"] == {"type": "TimeoutError", "message": None}
    assert [attempt["error_type"] for attempt in data["attempts"]] == [
        "RuntimeError",
        "TimeoutError",
    ]
    assert [attempt["error_message"] for attempt in data["attempts"]] == [None, None]
    assert data["attempt_count"] == 2
    assert data["failed_attempts"] == 2
    assert "first-secret" not in serialized
    assert "second-secret" not in serialized


def test_result_to_json_can_exclude_error_messages() -> None:
    result = _failed_result(RuntimeError("token=secret-value"))

    payload = result.to_json(include_error_message=False)

    assert "secret-value" not in payload
    assert '"type": "RuntimeError"' in payload
    assert '"message": null' in payload
    assert json.loads(payload) == result.to_dict(include_error_message=False)


def test_result_story_can_exclude_error_messages() -> None:
    result = _failed_result(RuntimeError("token=secret-value"))

    story = result.story(include_error_message=False)

    assert "Attempt 1: failed" in story
    assert "Error: RuntimeError" in story
    assert "secret-value" not in story


def test_explicit_error_message_inclusion_matches_existing_output() -> None:
    result = _failed_result(RuntimeError("token=secret-value"))

    assert result.to_dict(include_error_message=True) == result.to_dict()
    assert result.to_json(include_error_message=True) == result.to_json()
    assert result.story(include_error_message=True) == result.story()


def test_error_message_redaction_is_independent_from_value_inclusion() -> None:
    result = _failed_result(RuntimeError("token=secret-value"), value={"cached": True})

    data = result.to_dict(include_value=True, include_error_message=False)

    assert data["value"] == {"cached": True}
    assert data["error"] == {"type": "RuntimeError", "message": None}
    assert data["attempts"][0]["error_message"] is None


def test_redacted_output_does_not_render_or_mutate_error() -> None:
    class TrackedError(Exception):
        def __init__(self) -> None:
            super().__init__("secret-value")
            self.render_count = 0

        def __str__(self) -> str:
            self.render_count += 1
            return "secret-value"

    error = TrackedError()
    result = _failed_result(error)

    result.to_dict(include_error_message=False)
    result.to_json(include_error_message=False)
    result.story(include_error_message=False)

    assert error.render_count == 0
    assert result.error is error
    assert result.attempts[0].error is error


def test_error_message_option_does_not_change_results_without_errors() -> None:
    attempt = AttemptRecord(
        number=1,
        started_at=0.0,
        ended_at=0.1,
        value="ok",
        has_value=True,
    )
    result = RetryResult(attempts=(attempt,), value="ok", started_at=0.0, ended_at=0.1)

    assert result.to_dict(include_error_message=False) == result.to_dict()
    assert result.to_json(include_error_message=False) == result.to_json()
    assert result.story(include_error_message=False) == result.story()
