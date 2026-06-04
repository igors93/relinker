from retryflow.delays.exponential import ExponentialDelay


def test_exponential_delay() -> None:
    delay = ExponentialDelay(base=1, factor=2, maximum=10)

    assert delay.next_delay(1) == 1
    assert delay.next_delay(2) == 2
    assert delay.next_delay(5) == 10
