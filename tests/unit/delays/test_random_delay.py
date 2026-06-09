import pytest

from relinker import InvalidRetryConfigError
from relinker.delays.random_delay import RandomDelay


def test_random_delay_is_inside_range() -> None:
    value = RandomDelay(minimum=1, maximum=2, seed=1).next_delay(1)

    assert 1 <= value <= 2


def test_random_delay_rejects_invalid_range() -> None:
    with pytest.raises(InvalidRetryConfigError):
        RandomDelay(minimum=2, maximum=1)


def test_random_delay_seed_preserves_reproducible_sequence() -> None:
    first = RandomDelay(minimum=0, maximum=1, seed=7)
    second = RandomDelay(minimum=0, maximum=1, seed=7)

    assert [first.next_delay(attempt) for attempt in range(1, 5)] == [
        second.next_delay(attempt) for attempt in range(1, 5)
    ]


def test_random_delay_different_seeds_produce_different_sequences() -> None:
    first = RandomDelay(minimum=0, maximum=1, seed=1)
    second = RandomDelay(minimum=0, maximum=1, seed=2)

    assert [first.next_delay(attempt) for attempt in range(1, 9)] != [
        second.next_delay(attempt) for attempt in range(1, 9)
    ]
