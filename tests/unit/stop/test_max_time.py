from retryflow.stop.max_time import StopAfterDelay


def test_stop_after_delay() -> None:
    stop = StopAfterDelay(10)

    assert not stop.should_stop(1, 9.9)
    assert stop.should_stop(1, 10)
