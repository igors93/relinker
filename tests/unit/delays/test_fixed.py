from retryflow.delays.fixed import FixedDelay


def test_fixed_delay() -> None:
    assert FixedDelay(2).next_delay(1) == 2
