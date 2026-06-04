from relinker.attempt import AttemptRecord


def test_attempt_duration_and_status() -> None:
    attempt = AttemptRecord(number=1, started_at=1.0, ended_at=2.5, value="ok")

    assert attempt.duration == 1.5
    assert attempt.succeeded
    assert not attempt.failed
