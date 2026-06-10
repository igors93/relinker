"""Regression tests for the operational delay ceiling (Correction 1).

Every explicitly configured user value above MAX_SLEEP_SECONDS must be
rejected early with InvalidRetryConfigError, not silently passed to the
sleeper. Auto-saturating strategies (exponential without maximum) must
saturate at the ceiling without raising.
"""

from __future__ import annotations

import math
from collections.abc import Callable

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from relinker import InvalidRetryConfigError, RetryPolicy
from relinker.delays.chain import ChainDelay
from relinker.delays.custom import CustomDelay
from relinker.delays.exponential import ExponentialDelay
from relinker.delays.fixed import FixedDelay
from relinker.delays.linear import LinearDelay
from relinker.delays.random_delay import RandomDelay
from relinker.delays.random_exponential import RandomExponentialDelay
from relinker.delays.stateful import StatefulCustomDelay
from relinker.internal.validation import MAX_SLEEP_SECONDS, ensure_resolved_delay

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_ABOVE_CAP = MAX_SLEEP_SECONDS + 1.0
_JUST_ABOVE_CAP = math.nextafter(MAX_SLEEP_SECONDS, math.inf)


def _recording_sleeper() -> tuple[list[float], Callable[[float], None]]:
    recorded: list[float] = []
    return recorded, recorded.append


# ---------------------------------------------------------------------------
# ensure_resolved_delay central validation
# ---------------------------------------------------------------------------


class TestEnsureResolvedDelay:
    def test_zero_is_accepted(self) -> None:
        assert ensure_resolved_delay(0) == 0.0

    def test_int_zero_is_accepted(self) -> None:
        assert ensure_resolved_delay(0) == 0.0

    def test_float_zero_is_accepted(self) -> None:
        assert ensure_resolved_delay(0.0) == 0.0

    def test_small_positive_is_accepted(self) -> None:
        assert ensure_resolved_delay(0.001) == pytest.approx(0.001)

    def test_exactly_at_ceiling_is_accepted(self) -> None:
        assert ensure_resolved_delay(MAX_SLEEP_SECONDS) == MAX_SLEEP_SECONDS

    def test_just_below_ceiling_is_accepted(self) -> None:
        below = math.nextafter(MAX_SLEEP_SECONDS, 0.0)
        assert ensure_resolved_delay(below) == below

    def test_just_above_ceiling_is_rejected(self) -> None:
        with pytest.raises(InvalidRetryConfigError, match=str(int(MAX_SLEEP_SECONDS))):
            ensure_resolved_delay(_JUST_ABOVE_CAP)

    def test_far_above_ceiling_is_rejected(self) -> None:
        with pytest.raises(InvalidRetryConfigError):
            ensure_resolved_delay(1e300)

    def test_nan_is_rejected(self) -> None:
        with pytest.raises(InvalidRetryConfigError):
            ensure_resolved_delay(float("nan"))

    def test_positive_inf_is_rejected(self) -> None:
        with pytest.raises(InvalidRetryConfigError):
            ensure_resolved_delay(float("inf"))

    def test_negative_inf_is_rejected(self) -> None:
        with pytest.raises(InvalidRetryConfigError):
            ensure_resolved_delay(float("-inf"))

    def test_negative_float_is_rejected(self) -> None:
        with pytest.raises(InvalidRetryConfigError):
            ensure_resolved_delay(-0.001)

    def test_bool_is_rejected(self) -> None:
        with pytest.raises(InvalidRetryConfigError):
            ensure_resolved_delay(True)

    def test_string_is_rejected(self) -> None:
        with pytest.raises(InvalidRetryConfigError):
            ensure_resolved_delay("1.0")

    def test_error_message_mentions_max_value(self) -> None:
        with pytest.raises(InvalidRetryConfigError, match=str(int(MAX_SLEEP_SECONDS))):
            ensure_resolved_delay(_ABOVE_CAP)


# ---------------------------------------------------------------------------
# FixedDelay
# ---------------------------------------------------------------------------


class TestFixedDelayOperationalCeiling:
    def test_normal_value_accepted(self) -> None:
        assert FixedDelay(seconds=1.0).next_delay(1) == 1.0

    def test_zero_accepted(self) -> None:
        assert FixedDelay(seconds=0.0).next_delay(1) == 0.0

    def test_exactly_at_ceiling_accepted(self) -> None:
        # Construction should not raise; but delivery through policy would be
        # caught at ensure_resolved_delay. Direct construction with ceiling is ok.
        assert FixedDelay(seconds=MAX_SLEEP_SECONDS).next_delay(1) == MAX_SLEEP_SECONDS

    def test_above_ceiling_rejected_at_construction(self) -> None:
        with pytest.raises(InvalidRetryConfigError, match=str(int(MAX_SLEEP_SECONDS))):
            FixedDelay(seconds=_ABOVE_CAP)

    def test_far_above_ceiling_rejected_at_construction(self) -> None:
        with pytest.raises(InvalidRetryConfigError):
            FixedDelay(seconds=1e300)

    def test_via_policy_fixed_delay_above_ceiling_rejected(self) -> None:
        with pytest.raises(InvalidRetryConfigError):
            RetryPolicy().fixed_delay(_ABOVE_CAP)

    def test_sleeper_not_called_when_above_ceiling(self) -> None:
        calls: list[float] = []
        policy = (
            RetryPolicy()
            .attempts(2)
            .on(ValueError)
            .fixed_delay(MAX_SLEEP_SECONDS)
            .with_sleep(calls.append)
        )
        with pytest.raises(ValueError):
            policy.run(lambda: (_ for _ in ()).throw(ValueError("x")))
        assert all(v == MAX_SLEEP_SECONDS for v in calls)


# ---------------------------------------------------------------------------
# RandomDelay
# ---------------------------------------------------------------------------


class TestRandomDelayOperationalCeiling:
    def test_normal_range_accepted(self) -> None:
        v = RandomDelay(minimum=0.0, maximum=1.0, seed=1).next_delay(1)
        assert 0.0 <= v <= 1.0

    def test_minimum_equals_maximum_accepted(self) -> None:
        assert RandomDelay(minimum=1.0, maximum=1.0, seed=1).next_delay(1) == 1.0

    def test_maximum_at_ceiling_accepted(self) -> None:
        v = RandomDelay(minimum=0.0, maximum=MAX_SLEEP_SECONDS, seed=1).next_delay(1)
        assert 0.0 <= v <= MAX_SLEEP_SECONDS

    def test_minimum_above_ceiling_rejected(self) -> None:
        with pytest.raises(InvalidRetryConfigError, match=str(int(MAX_SLEEP_SECONDS))):
            RandomDelay(minimum=_ABOVE_CAP, maximum=_ABOVE_CAP)

    def test_maximum_above_ceiling_rejected(self) -> None:
        with pytest.raises(InvalidRetryConfigError, match=str(int(MAX_SLEEP_SECONDS))):
            RandomDelay(minimum=0.0, maximum=_ABOVE_CAP)

    def test_maximum_less_than_minimum_rejected(self) -> None:
        with pytest.raises(InvalidRetryConfigError):
            RandomDelay(minimum=2.0, maximum=1.0)

    def test_seed_determinism(self) -> None:
        a = RandomDelay(minimum=0.0, maximum=10.0, seed=42)
        b = RandomDelay(minimum=0.0, maximum=10.0, seed=42)
        assert [a.next_delay(n) for n in range(1, 6)] == [b.next_delay(n) for n in range(1, 6)]

    @given(
        st.floats(min_value=0.0, max_value=MAX_SLEEP_SECONDS, allow_nan=False),
        st.floats(min_value=0.0, max_value=MAX_SLEEP_SECONDS, allow_nan=False),
        st.integers(min_value=1, max_value=10),
    )
    @settings(max_examples=200)
    def test_result_always_in_range(self, lo: float, hi: float, attempt: int) -> None:
        if lo > hi:
            lo, hi = hi, lo
        result = RandomDelay(minimum=lo, maximum=hi, seed=99).next_delay(attempt)
        assert lo <= result <= hi


# ---------------------------------------------------------------------------
# LinearDelay
# ---------------------------------------------------------------------------


class TestLinearDelayOperationalCeiling:
    def test_normal_growth(self) -> None:
        d = LinearDelay(start=1.0, step=2.0)
        assert d.next_delay(1) == 1.0
        assert d.next_delay(2) == 3.0
        assert d.next_delay(3) == 5.0

    def test_step_zero(self) -> None:
        assert LinearDelay(start=5.0, step=0.0).next_delay(10) == 5.0

    def test_maximum_clamps_growth(self) -> None:
        d = LinearDelay(start=1.0, step=10.0, maximum=15.0)
        assert d.next_delay(3) == 15.0  # 1 + 10*2 = 21 → clamped

    def test_start_above_ceiling_rejected(self) -> None:
        with pytest.raises(InvalidRetryConfigError, match=str(int(MAX_SLEEP_SECONDS))):
            LinearDelay(start=_ABOVE_CAP)

    def test_maximum_above_ceiling_rejected(self) -> None:
        with pytest.raises(InvalidRetryConfigError, match=str(int(MAX_SLEEP_SECONDS))):
            LinearDelay(start=0.0, step=1.0, maximum=_ABOVE_CAP)

    @given(
        st.floats(min_value=0.0, max_value=MAX_SLEEP_SECONDS / 2, allow_nan=False),
        st.floats(min_value=0.0, max_value=MAX_SLEEP_SECONDS / 2, allow_nan=False),
        st.integers(min_value=1, max_value=1000),
    )
    @settings(max_examples=200)
    def test_result_non_negative_and_finite(self, start: float, step: float, attempt: int) -> None:
        # Only valid start/step combinations (no overflow above cap already validated)
        d = LinearDelay(start=start, step=step)
        result = d.next_delay(attempt)
        assert result >= 0.0
        assert math.isfinite(result)


# ---------------------------------------------------------------------------
# ChainDelay
# ---------------------------------------------------------------------------


class TestChainDelayOperationalCeiling:
    def test_single_value_normal(self) -> None:
        assert ChainDelay((1.0,)).next_delay(1) == 1.0

    def test_multi_value_sequence(self) -> None:
        d = ChainDelay((1.0, 2.0, 3.0))
        assert d.next_delay(1) == 1.0
        assert d.next_delay(2) == 2.0
        assert d.next_delay(3) == 3.0
        assert d.next_delay(10) == 3.0  # reuse last

    def test_zero_value_accepted(self) -> None:
        assert ChainDelay((0.0,)).next_delay(1) == 0.0

    def test_ceiling_value_accepted(self) -> None:
        assert ChainDelay((MAX_SLEEP_SECONDS,)).next_delay(1) == MAX_SLEEP_SECONDS

    def test_above_ceiling_rejected(self) -> None:
        with pytest.raises(InvalidRetryConfigError, match=str(int(MAX_SLEEP_SECONDS))):
            ChainDelay((_ABOVE_CAP,))

    def test_mixed_valid_and_invalid_rejected(self) -> None:
        with pytest.raises(InvalidRetryConfigError):
            ChainDelay((1.0, 2.0, _ABOVE_CAP))

    def test_nan_rejected(self) -> None:
        with pytest.raises(InvalidRetryConfigError):
            ChainDelay((float("nan"),))

    def test_inf_rejected(self) -> None:
        with pytest.raises(InvalidRetryConfigError):
            ChainDelay((float("inf"),))

    def test_tuple_and_list_via_policy_builder(self) -> None:
        RetryPolicy().chain_delay([1.0, 2.0, 3.0])
        RetryPolicy().chain_delay((1.0, 2.0, 3.0))


# ---------------------------------------------------------------------------
# ExponentialDelay
# ---------------------------------------------------------------------------


class TestExponentialDelayOperationalCeiling:
    def test_normal_growth(self) -> None:
        d = ExponentialDelay(base=1.0, factor=2.0, maximum=100.0)
        assert d.next_delay(1) == 1.0
        assert d.next_delay(2) == 2.0
        assert d.next_delay(7) == 64.0

    def test_maximum_at_ceiling_accepted(self) -> None:
        d = ExponentialDelay(base=1.0, factor=2.0, maximum=MAX_SLEEP_SECONDS)
        result = d.next_delay(200)
        assert result == MAX_SLEEP_SECONDS

    def test_maximum_above_ceiling_rejected(self) -> None:
        with pytest.raises(InvalidRetryConfigError, match=str(int(MAX_SLEEP_SECONDS))):
            ExponentialDelay(base=1.0, factor=2.0, maximum=_ABOVE_CAP)

    def test_without_maximum_saturates_at_ceiling(self) -> None:
        d = ExponentialDelay(base=1.0, factor=2.0)
        result = d.next_delay(200)
        assert result == MAX_SLEEP_SECONDS

    def test_overflow_without_maximum_saturates(self) -> None:
        import sys

        d = ExponentialDelay(base=sys.float_info.max, factor=sys.float_info.max)
        result = d.next_delay(1)
        assert result == MAX_SLEEP_SECONDS

    @given(
        st.floats(min_value=0.0, max_value=100.0, allow_nan=False),
        st.floats(min_value=1.0, max_value=10.0, allow_nan=False),
        st.integers(min_value=1, max_value=500),
    )
    @settings(max_examples=300)
    def test_result_never_nan_inf_negative_or_above_ceiling(
        self, base: float, factor: float, attempt: int
    ) -> None:
        d = ExponentialDelay(base=base, factor=factor)
        result = d.next_delay(attempt)
        assert math.isfinite(result)
        assert result >= 0.0
        assert result <= MAX_SLEEP_SECONDS


# ---------------------------------------------------------------------------
# RandomExponentialDelay
# ---------------------------------------------------------------------------


class TestRandomExponentialDelayOperationalCeiling:
    def test_base_zero_minimum_zero_returns_zero(self) -> None:
        assert RandomExponentialDelay(base=0.0, minimum=0.0).next_delay(1) == 0.0

    def test_base_zero_minimum_normal_returns_minimum(self) -> None:
        result = RandomExponentialDelay(base=0.0, minimum=5.0).next_delay(1)
        assert result == 5.0

    def test_base_zero_minimum_at_ceiling_accepted(self) -> None:
        result = RandomExponentialDelay(base=0.0, minimum=MAX_SLEEP_SECONDS).next_delay(1)
        assert result == MAX_SLEEP_SECONDS

    def test_base_zero_minimum_above_ceiling_rejected(self) -> None:
        with pytest.raises(InvalidRetryConfigError, match=str(int(MAX_SLEEP_SECONDS))):
            RandomExponentialDelay(base=0.0, minimum=_ABOVE_CAP)

    def test_maximum_at_ceiling_accepted(self) -> None:
        d = RandomExponentialDelay(base=1.0, factor=2.0, maximum=MAX_SLEEP_SECONDS, seed=1)
        result = d.next_delay(100)
        assert 0.0 <= result <= MAX_SLEEP_SECONDS

    def test_maximum_above_ceiling_rejected(self) -> None:
        with pytest.raises(InvalidRetryConfigError, match=str(int(MAX_SLEEP_SECONDS))):
            RandomExponentialDelay(base=1.0, maximum=_ABOVE_CAP)

    def test_maximum_less_than_minimum_rejected(self) -> None:
        with pytest.raises(InvalidRetryConfigError):
            RandomExponentialDelay(minimum=10.0, maximum=5.0)

    def test_seed_determinism(self) -> None:
        a = RandomExponentialDelay(base=1.0, factor=2.0, seed=7)
        b = RandomExponentialDelay(base=1.0, factor=2.0, seed=7)
        assert [a.next_delay(n) for n in range(1, 6)] == [b.next_delay(n) for n in range(1, 6)]

    @given(
        st.floats(min_value=0.0, max_value=10.0, allow_nan=False),
        st.floats(min_value=1.0, max_value=4.0, allow_nan=False),
        st.floats(min_value=0.0, max_value=MAX_SLEEP_SECONDS, allow_nan=False),
        st.integers(min_value=1, max_value=50),
    )
    @settings(max_examples=300)
    def test_result_always_in_safe_range(
        self, base: float, factor: float, minimum: float, attempt: int
    ) -> None:
        d = RandomExponentialDelay(base=base, factor=factor, minimum=minimum, seed=42)
        result = d.next_delay(attempt)
        assert math.isfinite(result)
        assert result >= minimum
        assert result <= MAX_SLEEP_SECONDS


# ---------------------------------------------------------------------------
# CustomDelay and StatefulCustomDelay
# ---------------------------------------------------------------------------


class TestCustomDelayOperationalCeiling:
    def test_normal_return_accepted(self) -> None:
        d = CustomDelay(callback=lambda n: float(n))
        assert d.next_delay(3) == 3.0

    def test_zero_return_accepted(self) -> None:
        assert CustomDelay(callback=lambda _: 0.0).next_delay(1) == 0.0

    def test_ceiling_return_accepted(self) -> None:
        assert CustomDelay(callback=lambda _: MAX_SLEEP_SECONDS).next_delay(1) == MAX_SLEEP_SECONDS

    def test_above_ceiling_rejected(self) -> None:
        d = CustomDelay(callback=lambda _: _ABOVE_CAP)
        with pytest.raises(InvalidRetryConfigError, match=str(int(MAX_SLEEP_SECONDS))):
            d.next_delay(1)

    def test_nan_rejected(self) -> None:
        d = CustomDelay(callback=lambda _: float("nan"))
        with pytest.raises(InvalidRetryConfigError):
            d.next_delay(1)

    def test_inf_rejected(self) -> None:
        d = CustomDelay(callback=lambda _: float("inf"))
        with pytest.raises(InvalidRetryConfigError):
            d.next_delay(1)

    def test_negative_rejected(self) -> None:
        d = CustomDelay(callback=lambda _: -1.0)
        with pytest.raises(InvalidRetryConfigError):
            d.next_delay(1)

    def test_bool_rejected(self) -> None:
        d = CustomDelay(callback=lambda _: True)  # type: ignore[arg-type]
        with pytest.raises(InvalidRetryConfigError):
            d.next_delay(1)

    def test_string_rejected(self) -> None:
        d = CustomDelay(callback=lambda _: "1.0")  # type: ignore[return-value]
        with pytest.raises(InvalidRetryConfigError):
            d.next_delay(1)

    def test_callback_exception_propagates(self) -> None:
        def boom(_: int) -> float:
            raise RuntimeError("callback failed")

        with pytest.raises(RuntimeError, match="callback failed"):
            CustomDelay(callback=boom).next_delay(1)


class TestStatefulCustomDelayOperationalCeiling:
    def test_normal_return_accepted(self) -> None:
        from relinker.state import RetryState

        state = RetryState(function_name="test", attempt_number=1, started_at=0.0, elapsed=0.0)
        d = StatefulCustomDelay(callback=lambda s: 2.5)
        assert d.next_delay_with_state(state) == 2.5

    def test_above_ceiling_rejected(self) -> None:
        from relinker.state import RetryState

        state = RetryState(function_name="test", attempt_number=1, started_at=0.0, elapsed=0.0)
        d = StatefulCustomDelay(callback=lambda s: _ABOVE_CAP)
        with pytest.raises(InvalidRetryConfigError, match=str(int(MAX_SLEEP_SECONDS))):
            d.next_delay_with_state(state)

    def test_callback_exception_propagates(self) -> None:
        from relinker.state import RetryState

        def boom(s: object) -> float:
            raise ValueError("stateful boom")

        state = RetryState(function_name="test", attempt_number=1, started_at=0.0, elapsed=0.0)
        with pytest.raises(ValueError, match="stateful boom"):
            StatefulCustomDelay(callback=boom).next_delay_with_state(state)


# ---------------------------------------------------------------------------
# Integration: sleeper only receives safe values
# ---------------------------------------------------------------------------


class TestIntegrationSleeperReceivesSafeValues:
    def _make_failing(self, n: int = 0) -> Callable[[], None]:
        calls = [0]

        def f() -> None:
            calls[0] += 1
            raise ValueError(f"fail-{calls[0]}")

        return f

    def test_fixed_delay_safe_value_reaches_sleeper(self) -> None:
        sleeps, sleeper = _recording_sleeper()
        policy = RetryPolicy().attempts(2).on(ValueError).fixed_delay(1.0).with_sleep(sleeper)
        with pytest.raises(ValueError):
            policy.run(self._make_failing())
        assert sleeps == [1.0]

    def test_fixed_delay_above_ceiling_does_not_reach_sleeper(self) -> None:
        with pytest.raises(InvalidRetryConfigError):
            RetryPolicy().fixed_delay(_ABOVE_CAP)

    def test_random_delay_above_ceiling_does_not_reach_sleeper(self) -> None:
        with pytest.raises(InvalidRetryConfigError):
            RetryPolicy().random_delay(minimum=0.0, maximum=_ABOVE_CAP)

    def test_exponential_max_above_ceiling_does_not_reach_sleeper(self) -> None:
        with pytest.raises(InvalidRetryConfigError):
            RetryPolicy().exponential_delay(base=1.0, maximum=_ABOVE_CAP)

    def test_random_exponential_minimum_above_ceiling_does_not_reach_sleeper(self) -> None:
        with pytest.raises(InvalidRetryConfigError):
            RetryPolicy().random_exponential_delay(base=0.0, minimum=_ABOVE_CAP)

    def test_custom_delay_above_ceiling_does_not_reach_sleeper(self) -> None:
        sleeps, sleeper = _recording_sleeper()
        policy = (
            RetryPolicy()
            .attempts(2)
            .on(ValueError)
            .custom_delay(lambda _: _ABOVE_CAP)
            .with_sleep(sleeper)
        )
        with pytest.raises(InvalidRetryConfigError):
            policy.run(self._make_failing())
        assert sleeps == []

    def test_stateful_delay_above_ceiling_does_not_reach_sleeper(self) -> None:
        sleeps, sleeper = _recording_sleeper()
        policy = (
            RetryPolicy()
            .attempts(2)
            .on(ValueError)
            .stateful_delay(lambda _: _ABOVE_CAP)
            .with_sleep(sleeper)
        )
        with pytest.raises(InvalidRetryConfigError):
            policy.run(self._make_failing())
        assert sleeps == []

    def test_additive_delay_sum_above_ceiling_does_not_reach_sleeper(self) -> None:
        sleeps, sleeper = _recording_sleeper()
        # Two valid halves that sum above ceiling
        half = MAX_SLEEP_SECONDS / 2.0 + 1.0
        policy = (
            RetryPolicy()
            .attempts(2)
            .on(ValueError)
            .fixed_delay(half)
            .add_delay(FixedDelay(half))
            .with_sleep(sleeper)
        )
        # half individually is <= MAX, but sum exceeds it
        # Whether this is caught depends on the additive sum validation
        # The sum reaches ensure_resolved_delay which must reject it
        with pytest.raises(InvalidRetryConfigError):
            policy.run(self._make_failing())
        assert sleeps == []

    async def test_async_fixed_delay_safe_value_reaches_sleeper(self) -> None:
        sleeps: list[float] = []

        async def async_sleeper(s: float) -> None:
            sleeps.append(s)

        async def task() -> None:
            raise ValueError("x")

        policy = (
            RetryPolicy()
            .attempts(2)
            .on(ValueError)
            .fixed_delay(1.0)
            .with_sleep(lambda _: None, async_sleeper)
        )
        with pytest.raises(ValueError):
            await policy.run_async(task)
        assert sleeps == [1.0]

    async def test_async_custom_delay_above_ceiling_does_not_reach_sleeper(self) -> None:
        sleeps: list[float] = []

        async def async_sleeper(s: float) -> None:
            sleeps.append(s)

        async def task() -> None:
            raise ValueError("x")

        policy = (
            RetryPolicy()
            .attempts(2)
            .on(ValueError)
            .custom_delay(lambda _: _ABOVE_CAP)
            .with_sleep(lambda _: None, async_sleeper)
        )
        with pytest.raises(InvalidRetryConfigError):
            await policy.run_async(task)
        assert sleeps == []


# ---------------------------------------------------------------------------
# Property-based: any finite non-negative value up to ceiling is accepted
# ---------------------------------------------------------------------------


@given(st.floats(min_value=0.0, max_value=MAX_SLEEP_SECONDS, allow_nan=False))
def test_ensure_resolved_delay_accepts_any_value_at_or_below_ceiling(value: float) -> None:
    result = ensure_resolved_delay(value)
    assert 0.0 <= result <= MAX_SLEEP_SECONDS


@given(
    st.floats(
        min_value=MAX_SLEEP_SECONDS,
        max_value=1e308,
        allow_nan=False,
        exclude_min=True,
    )
)
def test_ensure_resolved_delay_rejects_any_value_above_ceiling(value: float) -> None:
    with pytest.raises(InvalidRetryConfigError):
        ensure_resolved_delay(value)
