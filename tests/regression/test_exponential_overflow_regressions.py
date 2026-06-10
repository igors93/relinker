"""Regression tests: exponential overflow saturation."""

from __future__ import annotations

import math
import sys

import pytest

from relinker.delays.exponential import _SAFE_DELAY_CAP, ExponentialDelay
from relinker.delays.random_exponential import RandomExponentialDelay

# ---------------------------------------------------------------------------
# Regression: _SAFE_DELAY_CAP was sys.float_info.max / 2, which overflows
# time.sleep() and asyncio.sleep() on all real platforms.
# On Python 3.10+ both sleepers use _PyTime_t (signed int64, nanosecond
# resolution). Max representable: (2**63 - 1) ns ≈ 9.22e9 s ≈ 292 years.
# Verified on Windows Python 3.10:
#   time.sleep(sys.float_info.max / 2)
#   → OverflowError: timestamp too large to convert to C _PyTime_t
#
# Direct time.sleep() is NOT called in tests to avoid actually sleeping for
# the cap duration. Instead we validate through bound checks and fake sleepers.
# ---------------------------------------------------------------------------

# Conservative platform ceiling derived from _PyTime_t (signed int64 nanoseconds).
_PYTIME_MAX_SECONDS = (2**63 - 1) / 1e9  # ≈ 9.22e9 s ≈ 292 years


def test_safe_delay_cap_within_pytime_limit() -> None:
    """_SAFE_DELAY_CAP must be within the _PyTime_t range accepted by all sleepers.

    time.sleep() and asyncio.sleep() use _PyTime_t (int64, nanoseconds).
    Values > _PYTIME_MAX_SECONDS raise:
        OverflowError: timestamp too large to convert to C _PyTime_t
    """
    assert _SAFE_DELAY_CAP <= _PYTIME_MAX_SECONDS, (
        f"_SAFE_DELAY_CAP={_SAFE_DELAY_CAP!r} exceeds _PyTime_t limit "
        f"({_PYTIME_MAX_SECONDS:.3e}s). time.sleep() raises OverflowError."
    )


def test_safe_delay_cap_is_not_half_float_max() -> None:
    """_SAFE_DELAY_CAP must NOT be sys.float_info.max / 2 (the regressed value)."""
    regressed_value = sys.float_info.max / 2
    assert regressed_value != _SAFE_DELAY_CAP, (
        "_SAFE_DELAY_CAP is still set to sys.float_info.max / 2, which overflows sleepers."
    )


def test_policy_with_overflow_delay_sends_sleeper_safe_value() -> None:
    """A sleeper that validates its argument must not receive an overflow-causing value."""
    from relinker import RetryPolicy

    overflow_errors: list[str] = []
    received_delays: list[float] = []

    def validating_sleeper(seconds: float) -> None:
        received_delays.append(seconds)
        if seconds > _PYTIME_MAX_SECONDS:
            overflow_errors.append(
                f"delay {seconds!r} exceeds _PyTime_t limit — would overflow time.sleep"
            )

    calls = 0

    def fail() -> None:
        nonlocal calls
        calls += 1
        raise ValueError("boom")

    policy = (
        RetryPolicy()
        .attempts(3)
        .on(ValueError)
        .exponential_delay(base=sys.float_info.max, factor=sys.float_info.max)
        .with_sleep(validating_sleeper)
    )

    with pytest.raises(ValueError):
        policy.run(fail)

    assert overflow_errors == [], f"Sleeper received oversized values: {overflow_errors}"
    assert all(math.isfinite(d) for d in received_delays)


def test_random_exponential_overflow_sends_sleeper_safe_value() -> None:
    """RandomExponentialDelay overflow must also produce a sleeper-safe value."""
    from relinker import RetryPolicy

    overflow_errors: list[str] = []

    def validating_sleeper(seconds: float) -> None:
        if seconds > _PYTIME_MAX_SECONDS:
            overflow_errors.append(f"delay {seconds!r} overflows _PyTime_t")

    calls = 0

    def fail() -> None:
        nonlocal calls
        calls += 1
        raise ValueError("boom")

    policy = (
        RetryPolicy()
        .attempts(3)
        .on(ValueError)
        .random_exponential_delay(base=sys.float_info.max, factor=sys.float_info.max, seed=1)
        .with_sleep(validating_sleeper)
    )

    with pytest.raises(ValueError):
        policy.run(fail)

    assert overflow_errors == []


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


def test_safe_delay_cap_is_one_day() -> None:
    assert _SAFE_DELAY_CAP == 86_400.0


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
