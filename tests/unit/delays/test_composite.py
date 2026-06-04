from relinker.delays.fixed import FixedDelay
from relinker.delays.random_delay import RandomDelay


def test_additive_delay_sums_child_delays() -> None:
    delay = FixedDelay(1) + FixedDelay(2)

    assert delay.next_delay(1) == 3


def test_additive_delay_can_add_jitter() -> None:
    delay = FixedDelay(1) + RandomDelay(minimum=0, maximum=1, seed=123)

    value = delay.next_delay(1)

    assert 1 <= value <= 2
