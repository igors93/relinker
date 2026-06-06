"""Regression tests for zero-base exponential delays at large attempts."""

from __future__ import annotations

from relinker.delays.exponential import ExponentialDelay
from relinker.delays.random_exponential import RandomExponentialDelay


def test_capped_exponential_delay_with_zero_base_remains_zero() -> None:
    """Overflow handling must preserve the documented zero-base formula."""
    delay = ExponentialDelay(
        base=0.0,
        factor=2.0,
        maximum=60.0,
    )

    assert delay.next_delay(1025) == 0.0


def test_capped_random_exponential_delay_with_zero_base_remains_zero() -> None:
    """A zero exponential cap must not become a random value up to maximum."""
    delay = RandomExponentialDelay(
        base=0.0,
        factor=2.0,
        minimum=0.0,
        maximum=60.0,
        seed=1,
    )

    assert delay.next_delay(1025) == 0.0
