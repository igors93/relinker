from __future__ import annotations

from relinker.internal.runtime import RetryRuntime


def test_runtime_initialization_tracks_execution_metadata() -> None:
    runtime = RetryRuntime(
        function_name="task",
        started_at=10.0,
        history_limit=3,
    )

    assert runtime.function_name == "task"
    assert runtime.started_at == 10.0
    assert runtime.attempt_number == 0
    assert runtime.failed_count == 0
    assert runtime.success_count == 0
    assert tuple(runtime.attempts) == ()
    assert runtime.attempts.maxlen == 3


def test_begin_attempt_returns_next_one_based_attempt_number() -> None:
    runtime = RetryRuntime(function_name="task", started_at=10.0, history_limit=3)

    assert runtime.begin_attempt() == 1
    assert runtime.begin_attempt() == 2
    assert runtime.attempt_number == 2


def test_record_success_preserves_none_as_a_value() -> None:
    runtime = RetryRuntime(function_name="task", started_at=10.0, history_limit=3)
    runtime.begin_attempt()

    record = runtime.record_success(
        started_at=10.0,
        ended_at=11.0,
        value=None,
        has_value=True,
    )

    assert record.number == 1
    assert record.value is None
    assert record.has_value is True
    assert record.error is None
    assert runtime.success_count == 1
    assert runtime.failed_count == 0


def test_record_success_preserves_block_without_result() -> None:
    runtime = RetryRuntime(function_name="task", started_at=10.0, history_limit=3)
    runtime.begin_attempt()

    record = runtime.record_success(
        started_at=10.0,
        ended_at=11.0,
        value=None,
        has_value=False,
    )

    assert record.value is None
    assert record.has_value is False


def test_record_failure_tracks_original_error() -> None:
    runtime = RetryRuntime(function_name="task", started_at=10.0, history_limit=3)
    runtime.begin_attempt()
    error = RuntimeError("boom")

    record = runtime.record_failure(
        started_at=10.0,
        ended_at=11.0,
        error=error,
    )

    assert record.error is error
    assert runtime.failed_count == 1
    assert runtime.success_count == 0


def test_limited_history_keeps_complete_totals() -> None:
    runtime = RetryRuntime(function_name="task", started_at=10.0, history_limit=2)
    first_error = RuntimeError("first")
    second_error = RuntimeError("second")

    runtime.begin_attempt()
    runtime.record_failure(started_at=10.0, ended_at=11.0, error=first_error)
    runtime.begin_attempt()
    runtime.record_success(started_at=11.0, ended_at=12.0, value="ok")
    runtime.begin_attempt()
    runtime.record_failure(started_at=12.0, ended_at=13.0, error=second_error)

    assert len(runtime.attempts) == 2
    assert runtime.attempt_number == 3
    assert runtime.failed_count == 2
    assert runtime.success_count == 1
    assert [record.number for record in runtime.attempts] == [2, 3]


def test_state_builds_snapshot_from_runtime(monkeypatch) -> None:
    import relinker.internal.executor_helpers as executor_helpers

    monkeypatch.setattr(executor_helpers, "now", lambda: 15.0)
    runtime = RetryRuntime(function_name="task", started_at=10.0, history_limit=3)
    error = RuntimeError("boom")
    runtime.begin_attempt()
    runtime.record_failure(started_at=10.0, ended_at=11.0, error=error)

    state = runtime.state(
        last_error=error,
        retry_cause="exception",
        will_retry=True,
    )

    assert state.function_name == "task"
    assert state.attempt_number == runtime.attempt_number
    assert state.started_at == 10.0
    assert state.elapsed == 5.0
    assert state.attempts == tuple(runtime.attempts)
    assert state.last_error is error
    assert state.retry_cause == "exception"
    assert state.will_retry is True


def test_result_builds_final_result_from_runtime() -> None:
    runtime = RetryRuntime(function_name="task", started_at=10.0, history_limit=3)
    error = RuntimeError("boom")
    runtime.begin_attempt()
    runtime.record_failure(started_at=10.0, ended_at=11.0, error=error)

    result = runtime.result(
        ended_at=20.0,
        error=error,
        exhausted=True,
        retry_cause="exception",
    )

    assert result.started_at == 10.0
    assert result.ended_at == 20.0
    assert result.attempts == tuple(runtime.attempts)
    assert result.attempt_count == runtime.attempt_number
    assert result.failed_attempts == runtime.failed_count
    assert result.successful_attempts == runtime.success_count
    assert result.error is error
    assert result.exhausted is True
    assert result.retry_cause == "exception"


def test_result_normalizes_invalid_retry_cause() -> None:
    runtime = RetryRuntime(function_name="task", started_at=10.0, history_limit=3)
    retry_cause = "invalid"

    result = runtime.result(
        ended_at=20.0,
        retry_cause=retry_cause,
    )

    assert result.retry_cause is None
