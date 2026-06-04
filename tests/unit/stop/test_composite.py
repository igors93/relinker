from retryflow.stop.attempts import StopAfterAttempt
from retryflow.stop.max_time import StopAfterDelay


def test_any_stop_strategy() -> None:
    stop = StopAfterAttempt(3) | StopAfterDelay(10)

    assert not stop.should_stop(2, 5)
    assert stop.should_stop(3, 5)
    assert stop.should_stop(2, 10)


def test_all_stop_strategy() -> None:
    stop = StopAfterAttempt(3) & StopAfterDelay(10)

    assert not stop.should_stop(3, 5)
    assert not stop.should_stop(2, 10)
    assert stop.should_stop(3, 10)
