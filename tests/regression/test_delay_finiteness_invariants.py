"""Regression contracts for finite resolved delays."""

from __future__ import annotations

import math
import sys

from relinker import RetryPolicy


def test_exponential_delay_with_maximum_saturates_to_finite_maximum() -> None:
    policy = RetryPolicy().exponential_delay(
        base=sys.float_info.max,
        factor=sys.float_info.max,
        maximum=10.0,
    )

    delay = policy.delay_strategy.next_delay(3)

    assert math.isfinite(delay)
    assert delay <= 10.0
