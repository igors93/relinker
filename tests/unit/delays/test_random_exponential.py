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


def test_random_exponential_delay_zero_base_and_zero_minimum_returns_zero() -> None:
    delay = RandomExponentialDelay(base=0, minimum=0)

    assert delay.next_delay(1) == 0


def test_random_exponential_delay_zero_base_honors_positive_minimum() -> None:
    delay = RandomExponentialDelay(base=0, minimum=5)

    assert [delay.next_delay(attempt) for attempt in range(1, 5)] == [5, 5, 5, 5]


def test_random_exponential_delay_zero_base_honors_equal_minimum_and_maximum() -> None:
    delay = RandomExponentialDelay(base=0, minimum=5, maximum=5)

    assert delay.next_delay(1) == 5


def test_random_exponential_delay_zero_base_honors_minimum_with_seed_and_without_seed() -> None:
    seeded = RandomExponentialDelay(base=0, minimum=5, seed=123)
    unseeded = RandomExponentialDelay(base=0, minimum=5)

    assert seeded.next_delay(3) == 5
    assert unseeded.next_delay(3) == 5


def test_random_exponential_seed_preserves_reproducible_sequence() -> None:
    first = RandomExponentialDelay(base=1, factor=2, maximum=10, seed=7)
    second = RandomExponentialDelay(base=1, factor=2, maximum=10, seed=7)

    assert [first.next_delay(attempt) for attempt in range(1, 5)] == [
        second.next_delay(attempt) for attempt in range(1, 5)
    ]


def test_random_exponential_different_seeds_produce_different_sequences() -> None:
    first = RandomExponentialDelay(base=1, factor=2, maximum=10, seed=1)
    second = RandomExponentialDelay(base=1, factor=2, maximum=10, seed=2)

    assert [first.next_delay(attempt) for attempt in range(1, 9)] != [
        second.next_delay(attempt) for attempt in range(1, 9)
    ]
