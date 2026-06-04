from relinker.delays.chain import ChainDelay
from relinker.delays.linear import LinearDelay
from relinker.delays.random_exponential import RandomExponentialDelay


def test_linear_delay() -> None:
    delay = LinearDelay(start=1, step=2, maximum=5)

    assert delay.next_delay(1) == 1
    assert delay.next_delay(2) == 3
    assert delay.next_delay(3) == 5
    assert delay.next_delay(4) == 5


def test_chain_delay_reuses_last_value() -> None:
    delay = ChainDelay((0.1, 0.5, 1.0))

    assert delay.next_delay(1) == 0.1
    assert delay.next_delay(2) == 0.5
    assert delay.next_delay(3) == 1.0
    assert delay.next_delay(4) == 1.0


def test_random_exponential_delay_is_inside_expected_range() -> None:
    delay = RandomExponentialDelay(base=1, factor=2, minimum=0, maximum=10, seed=1)

    value = delay.next_delay(3)

    assert 0 <= value <= 4
