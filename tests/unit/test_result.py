from retryflow.attempt import AttemptRecord
from retryflow.result import RetryResult


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
