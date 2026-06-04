from retryflow.attempt import AttemptRecord
from retryflow.result import RetryResult


def test_result_story() -> None:
    attempt = AttemptRecord(number=1, started_at=0.0, ended_at=0.1, value="ok")
    result = RetryResult(attempts=(attempt,), value="ok", started_at=0.0, ended_at=0.1)

    assert result.succeeded
    assert result.attempt_count == 1
    assert "succeeded" in result.story()
