from retryflow.delays.random_delay import RandomDelay


def test_random_delay_is_inside_range() -> None:
    value = RandomDelay(minimum=1, maximum=2, seed=1).next_delay(1)

    assert 1 <= value <= 2
