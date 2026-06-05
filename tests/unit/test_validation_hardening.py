"""
Tests for hardened numeric validation (Correction 4).

Verifies that NaN, infinity, booleans, and invalid types are rejected
across all public numeric configuration points.
"""

from __future__ import annotations

import pytest

from relinker import RetryPolicy
from relinker.delays.chain import ChainDelay
from relinker.delays.exponential import ExponentialDelay
from relinker.delays.fixed import FixedDelay
from relinker.delays.linear import LinearDelay
from relinker.delays.random_delay import RandomDelay
from relinker.exceptions import InvalidRetryConfigError
from relinker.internal.validation import (
    ensure_finite_float,
    ensure_non_negative,
    ensure_positive,
    ensure_positive_int,
)
from relinker.stop.attempts import StopAfterAttempt
from relinker.stop.max_time import StopAfterDelay

# ---------------------------------------------------------------------------
# ensure_finite_float
# ---------------------------------------------------------------------------


class TestEnsureFiniteFloat:
    def test_valid_int(self) -> None:
        assert ensure_finite_float("x", 5) == 5.0

    def test_valid_float(self) -> None:
        assert ensure_finite_float("x", 3.14) == pytest.approx(3.14)

    def test_zero(self) -> None:
        assert ensure_finite_float("x", 0) == 0.0

    def test_nan_rejected(self) -> None:
        with pytest.raises(InvalidRetryConfigError, match="finite"):
            ensure_finite_float("x", float("nan"))

    def test_positive_inf_rejected(self) -> None:
        with pytest.raises(InvalidRetryConfigError, match="finite"):
            ensure_finite_float("x", float("inf"))

    def test_negative_inf_rejected(self) -> None:
        with pytest.raises(InvalidRetryConfigError, match="finite"):
            ensure_finite_float("x", float("-inf"))

    def test_true_rejected(self) -> None:
        with pytest.raises(InvalidRetryConfigError, match="bool"):
            ensure_finite_float("x", True)

    def test_false_rejected(self) -> None:
        with pytest.raises(InvalidRetryConfigError, match="bool"):
            ensure_finite_float("x", False)

    def test_string_rejected(self) -> None:
        with pytest.raises(InvalidRetryConfigError):
            ensure_finite_float("x", "1")

    def test_none_rejected(self) -> None:
        with pytest.raises(InvalidRetryConfigError):
            ensure_finite_float("x", None)

    def test_error_includes_name(self) -> None:
        with pytest.raises(InvalidRetryConfigError, match="my_param"):
            ensure_finite_float("my_param", float("nan"))


# ---------------------------------------------------------------------------
# ensure_non_negative
# ---------------------------------------------------------------------------


class TestEnsureNonNegative:
    def test_zero_allowed(self) -> None:
        ensure_non_negative("x", 0)  # must not raise

    def test_positive_allowed(self) -> None:
        ensure_non_negative("x", 1.5)

    def test_negative_rejected(self) -> None:
        with pytest.raises(InvalidRetryConfigError, match="greater than or equal"):
            ensure_non_negative("x", -0.001)

    def test_nan_rejected(self) -> None:
        with pytest.raises(InvalidRetryConfigError):
            ensure_non_negative("x", float("nan"))

    def test_inf_rejected(self) -> None:
        with pytest.raises(InvalidRetryConfigError):
            ensure_non_negative("x", float("inf"))

    def test_bool_rejected(self) -> None:
        with pytest.raises(InvalidRetryConfigError):
            ensure_non_negative("x", True)


# ---------------------------------------------------------------------------
# ensure_positive
# ---------------------------------------------------------------------------


class TestEnsurePositive:
    def test_positive_allowed(self) -> None:
        ensure_positive("x", 0.001)

    def test_zero_rejected(self) -> None:
        with pytest.raises(InvalidRetryConfigError, match="greater than 0"):
            ensure_positive("x", 0)

    def test_negative_rejected(self) -> None:
        with pytest.raises(InvalidRetryConfigError):
            ensure_positive("x", -1)

    def test_nan_rejected(self) -> None:
        with pytest.raises(InvalidRetryConfigError):
            ensure_positive("x", float("nan"))

    def test_inf_rejected(self) -> None:
        with pytest.raises(InvalidRetryConfigError):
            ensure_positive("x", float("inf"))

    def test_bool_rejected(self) -> None:
        with pytest.raises(InvalidRetryConfigError):
            ensure_positive("x", True)


# ---------------------------------------------------------------------------
# ensure_positive_int
# ---------------------------------------------------------------------------


class TestEnsurePositiveInt:
    def test_valid_int(self) -> None:
        ensure_positive_int("x", 1)  # must not raise

    def test_large_int(self) -> None:
        ensure_positive_int("x", 1_000_000)

    def test_zero_rejected(self) -> None:
        with pytest.raises(InvalidRetryConfigError):
            ensure_positive_int("x", 0)

    def test_negative_rejected(self) -> None:
        with pytest.raises(InvalidRetryConfigError):
            ensure_positive_int("x", -1)

    def test_true_rejected(self) -> None:
        with pytest.raises(InvalidRetryConfigError):
            ensure_positive_int("x", True)

    def test_false_rejected(self) -> None:
        with pytest.raises(InvalidRetryConfigError):
            ensure_positive_int("x", False)

    def test_float_rejected(self) -> None:
        with pytest.raises(InvalidRetryConfigError):
            ensure_positive_int("x", 1.0)

    def test_nan_rejected(self) -> None:
        with pytest.raises(InvalidRetryConfigError):
            ensure_positive_int("x", float("nan"))  # type: ignore[arg-type]

    def test_error_includes_name(self) -> None:
        with pytest.raises(InvalidRetryConfigError, match="attempts"):
            ensure_positive_int("attempts", True)


# ---------------------------------------------------------------------------
# StopAfterAttempt
# ---------------------------------------------------------------------------


class TestStopAfterAttemptValidation:
    def test_valid(self) -> None:
        StopAfterAttempt(1)

    def test_zero_rejected(self) -> None:
        with pytest.raises(InvalidRetryConfigError):
            StopAfterAttempt(0)

    def test_negative_rejected(self) -> None:
        with pytest.raises(InvalidRetryConfigError):
            StopAfterAttempt(-1)

    def test_true_rejected(self) -> None:
        with pytest.raises(InvalidRetryConfigError):
            StopAfterAttempt(True)  # type: ignore[arg-type]

    def test_false_rejected(self) -> None:
        with pytest.raises(InvalidRetryConfigError):
            StopAfterAttempt(False)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# StopAfterDelay (max_time)
# ---------------------------------------------------------------------------


class TestStopAfterDelayValidation:
    def test_valid(self) -> None:
        StopAfterDelay(5.0)

    def test_zero_allowed(self) -> None:
        StopAfterDelay(0.0)

    def test_negative_rejected(self) -> None:
        with pytest.raises(InvalidRetryConfigError):
            StopAfterDelay(-1.0)

    def test_nan_rejected(self) -> None:
        with pytest.raises(InvalidRetryConfigError):
            StopAfterDelay(float("nan"))

    def test_inf_rejected(self) -> None:
        with pytest.raises(InvalidRetryConfigError):
            StopAfterDelay(float("inf"))

    def test_bool_rejected(self) -> None:
        with pytest.raises(InvalidRetryConfigError):
            StopAfterDelay(True)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# FixedDelay
# ---------------------------------------------------------------------------


class TestFixedDelayValidation:
    def test_valid(self) -> None:
        FixedDelay(1.0)

    def test_zero_allowed(self) -> None:
        FixedDelay(0.0)

    def test_nan_rejected(self) -> None:
        with pytest.raises(InvalidRetryConfigError):
            FixedDelay(float("nan"))

    def test_inf_rejected(self) -> None:
        with pytest.raises(InvalidRetryConfigError):
            FixedDelay(float("inf"))

    def test_bool_rejected(self) -> None:
        with pytest.raises(InvalidRetryConfigError):
            FixedDelay(True)  # type: ignore[arg-type]

    def test_negative_rejected(self) -> None:
        with pytest.raises(InvalidRetryConfigError):
            FixedDelay(-1.0)


# ---------------------------------------------------------------------------
# ExponentialDelay
# ---------------------------------------------------------------------------


class TestExponentialDelayValidation:
    def test_valid(self) -> None:
        ExponentialDelay(base=1.0, factor=2.0)

    def test_nan_base_rejected(self) -> None:
        with pytest.raises(InvalidRetryConfigError):
            ExponentialDelay(base=float("nan"), factor=2.0)

    def test_inf_factor_rejected(self) -> None:
        with pytest.raises(InvalidRetryConfigError):
            ExponentialDelay(base=1.0, factor=float("inf"))

    def test_zero_factor_rejected(self) -> None:
        with pytest.raises(InvalidRetryConfigError):
            ExponentialDelay(base=1.0, factor=0.0)

    def test_bool_base_rejected(self) -> None:
        with pytest.raises(InvalidRetryConfigError):
            ExponentialDelay(base=True, factor=2.0)  # type: ignore[arg-type]

    def test_nan_maximum_rejected(self) -> None:
        with pytest.raises(InvalidRetryConfigError):
            ExponentialDelay(base=1.0, factor=2.0, maximum=float("nan"))


# ---------------------------------------------------------------------------
# LinearDelay
# ---------------------------------------------------------------------------


class TestLinearDelayValidation:
    def test_nan_start_rejected(self) -> None:
        with pytest.raises(InvalidRetryConfigError):
            LinearDelay(start=float("nan"), step=1.0)

    def test_inf_step_rejected(self) -> None:
        with pytest.raises(InvalidRetryConfigError):
            LinearDelay(start=0.0, step=float("inf"))

    def test_bool_start_rejected(self) -> None:
        with pytest.raises(InvalidRetryConfigError):
            LinearDelay(start=True, step=1.0)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# RandomDelay
# ---------------------------------------------------------------------------


class TestRandomDelayValidation:
    def test_nan_minimum_rejected(self) -> None:
        with pytest.raises(InvalidRetryConfigError):
            RandomDelay(minimum=float("nan"), maximum=1.0)

    def test_inf_maximum_rejected(self) -> None:
        with pytest.raises(InvalidRetryConfigError):
            RandomDelay(minimum=0.0, maximum=float("inf"))

    def test_bool_minimum_rejected(self) -> None:
        with pytest.raises(InvalidRetryConfigError):
            RandomDelay(minimum=True, maximum=1.0)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# ChainDelay
# ---------------------------------------------------------------------------


class TestChainDelayValidation:
    def test_nan_in_delays_rejected(self) -> None:
        with pytest.raises(InvalidRetryConfigError):
            ChainDelay((1.0, float("nan"), 2.0))

    def test_inf_in_delays_rejected(self) -> None:
        with pytest.raises(InvalidRetryConfigError):
            ChainDelay((1.0, float("inf")))

    def test_bool_in_delays_rejected(self) -> None:
        with pytest.raises(InvalidRetryConfigError):
            ChainDelay((True,))  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# RetryPolicy builder convenience methods
# ---------------------------------------------------------------------------


class TestRetryPolicyBuilderValidation:
    def test_attempts_true_rejected(self) -> None:
        with pytest.raises(InvalidRetryConfigError):
            RetryPolicy().attempts(True)  # type: ignore[arg-type]

    def test_attempts_false_rejected(self) -> None:
        with pytest.raises(InvalidRetryConfigError):
            RetryPolicy().attempts(False)  # type: ignore[arg-type]

    def test_max_time_nan_rejected(self) -> None:
        with pytest.raises(InvalidRetryConfigError):
            RetryPolicy().max_time(float("nan"))

    def test_max_time_inf_rejected(self) -> None:
        with pytest.raises(InvalidRetryConfigError):
            RetryPolicy().max_time(float("inf"))

    def test_fixed_delay_nan_rejected(self) -> None:
        with pytest.raises(InvalidRetryConfigError):
            RetryPolicy().fixed_delay(float("nan"))

    def test_fixed_delay_inf_rejected(self) -> None:
        with pytest.raises(InvalidRetryConfigError):
            RetryPolicy().fixed_delay(float("inf"))

    def test_valid_config(self) -> None:
        # Sanity: valid config should not raise
        policy = RetryPolicy().attempts(3).fixed_delay(1.0).max_time(60.0)
        assert policy is not None
