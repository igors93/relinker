import pytest

from relinker import InvalidRetryConfigError
from relinker.delays.random_exponential import RandomExponentialDelay


def test_random_exponential_delay_rejects_maximum_smaller_than_minimum() -> None:
    with pytest.raises(InvalidRetryConfigError):
        RandomExponentialDelay(minimum=5, maximum=1)


def test_random_exponential_delay_uses_expected_range() -> None:
    delay = RandomExponentialDelay(base=1, factor=2, minimum=0, maximum=10, seed=1)

    value = delay.next_delay(3)

    assert 0 <= value <= 4
