"""Regression contracts for finite resolved delays."""

from __future__ import annotations

import math
import sys

import pytest

from relinker import InvalidRetryConfigError, RetryPolicy


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
    # With MAX_SLEEP_SECONDS ceiling, values above the ceiling are rejected at
    # construction time (before the policy runs), so the sleeper is never called.
    import math

    from relinker.internal.validation import MAX_SLEEP_SECONDS

    with pytest.raises(InvalidRetryConfigError):
        RetryPolicy().fixed_delay(math.nextafter(MAX_SLEEP_SECONDS, math.inf))
