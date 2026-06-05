"""
Tests for empty composite rejection (Correction 5).

Verifies that AnyCondition, AllCondition, AnyStopStrategy, and AllStopStrategy
all reject empty collections immediately at construction.
"""

from __future__ import annotations

import pytest

from relinker import RetryPolicy
from relinker.conditions.composite import AllCondition, AnyCondition
from relinker.conditions.exception import ExceptionCondition
from relinker.conditions.result import ResultCondition
from relinker.exceptions import InvalidRetryConfigError
from relinker.stop.attempts import StopAfterAttempt
from relinker.stop.composite import AllStopStrategy, AnyStopStrategy
from relinker.stop.max_time import StopAfterDelay

# ---------------------------------------------------------------------------
# AnyCondition
# ---------------------------------------------------------------------------


class TestAnyConditionEmpty:
    def test_empty_tuple_rejected(self) -> None:
        with pytest.raises(InvalidRetryConfigError, match="AnyCondition"):
            AnyCondition(())

    def test_single_child_accepted(self) -> None:
        cond = AnyCondition((ExceptionCondition((ValueError,)),))
        assert cond.should_retry_exception(ValueError("x"))

    def test_two_children_accepted(self) -> None:
        cond = AnyCondition(
            (
                ExceptionCondition((ValueError,)),
                ExceptionCondition((TypeError,)),
            )
        )
        assert cond.should_retry_exception(ValueError("x"))
        assert cond.should_retry_exception(TypeError())

    def test_policy_any_condition_empty_rejected(self) -> None:
        with pytest.raises(InvalidRetryConfigError):
            RetryPolicy().any_condition()

    def test_or_operator_accepted(self) -> None:
        a = ExceptionCondition((ValueError,))
        b = ExceptionCondition((TypeError,))
        combined = a | b
        assert combined.should_retry_exception(ValueError("x"))


# ---------------------------------------------------------------------------
# AllCondition
# ---------------------------------------------------------------------------


class TestAllConditionEmpty:
    def test_empty_tuple_rejected(self) -> None:
        with pytest.raises(InvalidRetryConfigError, match="AllCondition"):
            AllCondition(())

    def test_single_child_accepted(self) -> None:
        cond = AllCondition((ExceptionCondition((ValueError,)),))
        assert cond.should_retry_exception(ValueError("x"))

    def test_two_children_accepted(self) -> None:
        exc_cond = ExceptionCondition((ValueError,))
        result_cond = ResultCondition(lambda v: v < 0)
        cond = AllCondition((exc_cond, result_cond))
        assert not cond.should_retry_exception(ValueError("x"))

    def test_policy_all_conditions_empty_rejected(self) -> None:
        with pytest.raises(InvalidRetryConfigError):
            RetryPolicy().all_conditions()

    def test_and_operator_accepted(self) -> None:
        a = ExceptionCondition((ValueError,))
        b = ExceptionCondition((ValueError,))
        combined = a & b
        assert combined.should_retry_exception(ValueError("x"))


# ---------------------------------------------------------------------------
# AnyStopStrategy
# ---------------------------------------------------------------------------


class TestAnyStopStrategyEmpty:
    def test_empty_tuple_rejected(self) -> None:
        with pytest.raises(InvalidRetryConfigError, match="AnyStopStrategy"):
            AnyStopStrategy(())

    def test_single_strategy_accepted(self) -> None:
        strat = AnyStopStrategy((StopAfterAttempt(3),))
        assert not strat.should_stop(1, 0.0)
        assert strat.should_stop(3, 0.0)

    def test_two_strategies_accepted(self) -> None:
        strat = AnyStopStrategy((StopAfterAttempt(5), StopAfterDelay(10.0)))
        assert strat.should_stop(5, 0.0)
        assert strat.should_stop(1, 10.0)

    def test_or_operator_accepted(self) -> None:
        a = StopAfterAttempt(3)
        b = StopAfterDelay(60.0)
        combined = a | b
        assert combined.should_stop(3, 0.0)


# ---------------------------------------------------------------------------
# AllStopStrategy
# ---------------------------------------------------------------------------


class TestAllStopStrategyEmpty:
    def test_empty_tuple_rejected(self) -> None:
        with pytest.raises(InvalidRetryConfigError, match="AllStopStrategy"):
            AllStopStrategy(())

    def test_single_strategy_accepted(self) -> None:
        strat = AllStopStrategy((StopAfterAttempt(3),))
        assert strat.should_stop(3, 0.0)

    def test_two_strategies_must_both_stop(self) -> None:
        strat = AllStopStrategy((StopAfterAttempt(5), StopAfterDelay(10.0)))
        # attempt limit hit but not time limit
        assert not strat.should_stop(5, 0.0)
        # both hit
        assert strat.should_stop(5, 10.0)

    def test_and_operator_accepted(self) -> None:
        a = StopAfterAttempt(3)
        b = StopAfterDelay(60.0)
        combined = a & b
        assert not combined.should_stop(3, 0.0)
        assert combined.should_stop(3, 60.0)
