"""Regression tests: exponential overflow saturation (Fix 4)."""

from __future__ import annotations

import math
import sys

import pytest

from relinker.delays.exponential import _SAFE_DELAY_CAP, ExponentialDelay
from relinker.delays.random_exponential import RandomExponentialDelay

# ---------------------------------------------------------------------------
# ExponentialDelay: finite return even at extreme attempt counts
# ---------------------------------------------------------------------------


def test_exponential_large_attempt_returns_finite() -> None:
    delay = ExponentialDelay(base=1.0, factor=2.0)
    result = delay.next_delay(10_000)
    assert math.isfinite(result), f"Expected finite, got {result}"


def test_exponential_large_attempt_saturates_at_safe_cap() -> None:
    delay = ExponentialDelay(base=1.0, factor=2.0)
    result = delay.next_delay(10_000)
    assert result == _SAFE_DELAY_CAP


def test_exponential_maximum_respected_when_set() -> None:
    delay = ExponentialDelay(base=1.0, factor=2.0, maximum=60.0)
    result = delay.next_delay(10_000)
    assert result == 60.0


def test_exponential_normal_attempts_unaffected() -> None:
    delay = ExponentialDelay(base=1.0, factor=2.0)
    assert delay.next_delay(1) == pytest.approx(1.0)
    assert delay.next_delay(2) == pytest.approx(2.0)
    assert delay.next_delay(3) == pytest.approx(4.0)
    assert delay.next_delay(4) == pytest.approx(8.0)


def test_exponential_base_zero_always_returns_zero() -> None:
    delay = ExponentialDelay(base=0.0, factor=2.0)
    assert delay.next_delay(10_000) == 0.0


def test_exponential_factor_one_does_not_overflow() -> None:
    delay = ExponentialDelay(base=1.0, factor=1.0)
    result = delay.next_delay(10_000)
    assert math.isfinite(result)
    assert result == pytest.approx(1.0)


def test_safe_delay_cap_is_finite() -> None:
    assert math.isfinite(_SAFE_DELAY_CAP)
    assert _SAFE_DELAY_CAP > 0
    assert sys.float_info.max >= _SAFE_DELAY_CAP


def test_safe_delay_cap_is_half_float_max() -> None:
    assert sys.float_info.max / 2 == _SAFE_DELAY_CAP


def test_exponential_overflow_does_not_raise() -> None:
    delay = ExponentialDelay(base=1e300, factor=1e300)
    result = delay.next_delay(5)
    assert math.isfinite(result)
    assert result == _SAFE_DELAY_CAP


def test_exponential_attempt_zero_is_handled() -> None:
    delay = ExponentialDelay(base=1.0, factor=2.0)
    result = delay.next_delay(0)
    assert math.isfinite(result)


# ---------------------------------------------------------------------------
# RandomExponentialDelay: finite return even at extreme attempt counts
# ---------------------------------------------------------------------------


def test_random_exponential_large_attempt_returns_finite() -> None:
    delay = RandomExponentialDelay(base=1.0, factor=2.0, seed=42)
    result = delay.next_delay(10_000)
    assert math.isfinite(result), f"Expected finite, got {result}"


def test_random_exponential_large_attempt_within_safe_cap() -> None:
    delay = RandomExponentialDelay(base=1.0, factor=2.0, seed=42)
    result = delay.next_delay(10_000)
    assert 0.0 <= result <= _SAFE_DELAY_CAP


def test_random_exponential_maximum_respected_when_set() -> None:
    delay = RandomExponentialDelay(base=1.0, factor=2.0, maximum=30.0, seed=1)
    result = delay.next_delay(10_000)
    assert 0.0 <= result <= 30.0


def test_random_exponential_normal_attempts_within_range() -> None:
    delay = RandomExponentialDelay(base=1.0, factor=2.0, minimum=0.0, seed=99)
    for attempt in range(1, 6):
        cap = 1.0 * (2.0 ** (attempt - 1))
        result = delay.next_delay(attempt)
        assert 0.0 <= result <= cap + 1e-9, (
            f"attempt {attempt}: result {result} out of range [0, {cap}]"
        )


def test_random_exponential_minimum_floor_respected() -> None:
    delay = RandomExponentialDelay(base=1.0, factor=2.0, minimum=5.0, seed=7)
    for attempt in range(1, 5):
        result = delay.next_delay(attempt)
        assert result >= 5.0, f"attempt {attempt}: result {result} below minimum"


def test_random_exponential_base_zero_returns_minimum() -> None:
    delay = RandomExponentialDelay(base=0.0, factor=2.0, minimum=3.0)
    assert delay.next_delay(10_000) == pytest.approx(3.0)


def test_random_exponential_overflow_does_not_raise() -> None:
    delay = RandomExponentialDelay(base=1e300, factor=1e300, seed=5)
    result = delay.next_delay(5)
    assert math.isfinite(result)


# ---------------------------------------------------------------------------
# Integration: policy does not raise with forever() + exponential + no maximum
# ---------------------------------------------------------------------------


def test_policy_forever_exponential_no_maximum_does_not_raise() -> None:
    from relinker import RetryPolicy

    call_count = 0

    def sometimes_fails() -> str:
        nonlocal call_count
        call_count += 1
        if call_count < 4:
            raise ValueError("transient")
        return "ok"

    policy = RetryPolicy().forever().exponential_delay().for_testing()
    result = policy.run(sometimes_fails)
    assert result == "ok"
    assert call_count == 4


def test_policy_exponential_no_maximum_warns_when_forever() -> None:
    from relinker import RetryPolicy

    policy = RetryPolicy().forever().exponential_delay().keep_history(5)
    codes = {w.code for w in policy.warnings()}
    assert "unbounded_exponential_with_forever" in codes


def test_policy_exponential_with_maximum_does_not_warn() -> None:
    from relinker import RetryPolicy

    policy = RetryPolicy().forever().exponential_delay(maximum=60.0).keep_history(5)
    codes = {w.code for w in policy.warnings()}
    assert "unbounded_exponential_with_forever" not in codes


def test_policy_bounded_attempts_with_exponential_no_maximum_does_not_warn() -> None:
    from relinker import RetryPolicy

    policy = RetryPolicy().attempts(5).exponential_delay()
    codes = {w.code for w in policy.warnings()}
    assert "unbounded_exponential_with_forever" not in codes
