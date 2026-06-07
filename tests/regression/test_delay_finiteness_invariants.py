"""Regression contracts for finite resolved delays."""

from __future__ import annotations

import math
import sys

import pytest

from relinker import InvalidRetryConfigError, RetryPolicy
from relinker.delays.fixed import FixedDelay


def test_exponential_delay_with_maximum_saturates_to_finite_maximum() -> None:
    policy = RetryPolicy().exponential_delay(
        base=sys.float_info.max,
        factor=sys.float_info.max,
        maximum=10.0,
    )

    delay = policy.delay_strategy.next_delay(3)

    assert math.isfinite(delay)
    assert delay <= 10.0


def test_additive_delay_overflow_is_rejected_before_sleep() -> None:
    sleeps: list[float] = []
    policy = (
        RetryPolicy()
        .attempts(2)
        .on(OSError)
        .fixed_delay(sys.float_info.max)
        .add_delay(FixedDelay(sys.float_info.max))
        .with_sleep(sleeps.append)
    )

    def fail() -> None:
        raise OSError("temporary")

    with pytest.raises(InvalidRetryConfigError, match="resolved delay"):
        policy.run(fail)

    assert sleeps == []
