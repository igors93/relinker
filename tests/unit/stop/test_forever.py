from retryflow.stop.forever import StopForever


def test_stop_forever_never_stops() -> None:
    stop = StopForever()

    assert not stop.should_stop(1_000_000, 999999)
