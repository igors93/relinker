from retryflow.stop.attempts import StopAfterAttempt


def test_stop_after_attempt() -> None:
    stop = StopAfterAttempt(3)

    assert not stop.should_stop(2, 0)
    assert stop.should_stop(3, 0)
