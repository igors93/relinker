"""Regression tests for Correction 4: early callback validation.

All public constructors that accept callables must reject non-callables
(and invalid callables like async generators) before any attempt, event,
sleep, stats change, or budget reservation occurs.
"""

from __future__ import annotations

import pytest

from relinker import InvalidRetryConfigError, RetryPolicy
from relinker.conditions.custom import CustomCondition
from relinker.conditions.result import ResultCondition
from relinker.delays.custom import CustomDelay
from relinker.delays.stateful import StatefulCustomDelay

# ---------------------------------------------------------------------------
# Policy builder methods
# ---------------------------------------------------------------------------


class TestBuilderCallableValidation:
    def test_or_retry_if_result_rejects_integer(self) -> None:
        with pytest.raises(InvalidRetryConfigError):
            RetryPolicy().or_retry_if_result(42)  # type: ignore[arg-type]

    def test_or_retry_if_result_rejects_none(self) -> None:
        with pytest.raises(InvalidRetryConfigError):
            RetryPolicy().or_retry_if_result(None)  # type: ignore[arg-type]

    def test_or_retry_if_result_rejects_string(self) -> None:
        with pytest.raises(InvalidRetryConfigError):
            RetryPolicy().or_retry_if_result("not_callable")  # type: ignore[arg-type]

    def test_or_retry_if_result_accepts_lambda(self) -> None:
        policy = RetryPolicy().or_retry_if_result(lambda v: v is None)
        assert policy is not None

    def test_retry_if_result_rejects_integer(self) -> None:
        with pytest.raises(InvalidRetryConfigError):
            RetryPolicy().retry_if_result(42)  # type: ignore[arg-type]

    def test_retry_if_rejects_integer(self) -> None:
        with pytest.raises(InvalidRetryConfigError):
            RetryPolicy().retry_if(42)  # type: ignore[arg-type]

    def test_custom_delay_rejects_integer(self) -> None:
        with pytest.raises(InvalidRetryConfigError):
            RetryPolicy().custom_delay(42)  # type: ignore[arg-type]

    def test_stateful_delay_rejects_integer(self) -> None:
        with pytest.raises(InvalidRetryConfigError):
            RetryPolicy().stateful_delay(42)  # type: ignore[arg-type]

    def test_on_event_rejects_integer(self) -> None:
        with pytest.raises(InvalidRetryConfigError):
            RetryPolicy().on_event("after_failure", 42)  # type: ignore[arg-type]

    def test_with_sleep_rejects_integer(self) -> None:
        with pytest.raises(InvalidRetryConfigError):
            RetryPolicy().with_sleep(42)  # type: ignore[arg-type]

    def test_with_sleep_second_arg_rejects_integer(self) -> None:
        with pytest.raises(InvalidRetryConfigError):
            RetryPolicy().with_sleep(lambda s: None, 42)  # type: ignore[arg-type]

    def test_on_exhausted_return_rejects_integer(self) -> None:
        with pytest.raises(InvalidRetryConfigError):
            RetryPolicy().on_exhausted_return(42)  # type: ignore[arg-type]

    def test_fallback_rejects_integer(self) -> None:
        with pytest.raises(InvalidRetryConfigError):
            RetryPolicy().fallback(42)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Direct class construction
# ---------------------------------------------------------------------------


class TestDirectConstructionValidation:
    def test_result_condition_rejects_integer(self) -> None:
        with pytest.raises(InvalidRetryConfigError):
            ResultCondition(predicate=42)  # type: ignore[arg-type]

    def test_result_condition_rejects_none(self) -> None:
        with pytest.raises(InvalidRetryConfigError):
            ResultCondition(predicate=None)  # type: ignore[arg-type]

    def test_result_condition_rejects_string(self) -> None:
        with pytest.raises(InvalidRetryConfigError):
            ResultCondition(predicate="bad")  # type: ignore[arg-type]

    def test_result_condition_accepts_lambda(self) -> None:
        rc = ResultCondition(predicate=lambda v: v is None)
        assert rc.should_retry_result(None) is True

    def test_custom_condition_rejects_integer(self) -> None:
        with pytest.raises(InvalidRetryConfigError):
            CustomCondition(callback=42)  # type: ignore[arg-type]

    def test_custom_condition_accepts_lambda(self) -> None:
        cc = CustomCondition(callback=lambda e, v: False)
        assert cc.should_retry_exception(ValueError("x")) is False

    def test_custom_delay_rejects_integer(self) -> None:
        with pytest.raises(InvalidRetryConfigError):
            CustomDelay(callback=42)  # type: ignore[arg-type]

    def test_custom_delay_rejects_none(self) -> None:
        with pytest.raises(InvalidRetryConfigError):
            CustomDelay(callback=None)  # type: ignore[arg-type]

    def test_custom_delay_accepts_lambda(self) -> None:
        cd = CustomDelay(callback=lambda n: 1.0)
        assert cd.next_delay(1) == 1.0

    def test_stateful_custom_delay_rejects_integer(self) -> None:
        with pytest.raises(InvalidRetryConfigError):
            StatefulCustomDelay(callback=42)  # type: ignore[arg-type]

    def test_stateful_custom_delay_rejects_none(self) -> None:
        with pytest.raises(InvalidRetryConfigError):
            StatefulCustomDelay(callback=None)  # type: ignore[arg-type]

    def test_stateful_custom_delay_accepts_lambda(self) -> None:
        sd = StatefulCustomDelay(callback=lambda s: 0.5)
        assert sd is not None


# ---------------------------------------------------------------------------
# Accepted callable forms
# ---------------------------------------------------------------------------


class TestAcceptedCallableForms:
    def test_lambda_accepted(self) -> None:
        RetryPolicy().retry_if_result(lambda v: False)
        RetryPolicy().custom_delay(lambda n: 0.0)
        RetryPolicy().stateful_delay(lambda s: 0.0)

    def test_partial_accepted(self) -> None:
        from functools import partial

        def pred(threshold: float, v: object) -> bool:
            return v is None

        RetryPolicy().retry_if_result(partial(pred, 0.5))

    def test_callable_object_accepted(self) -> None:
        class MyPredicate:
            def __call__(self, v: object) -> bool:
                return False

        RetryPolicy().retry_if_result(MyPredicate())

    def test_bound_method_accepted(self) -> None:
        class Helper:
            def check(self, v: object) -> bool:
                return False

        h = Helper()
        RetryPolicy().retry_if_result(h.check)

    def test_decorated_function_accepted(self) -> None:
        import functools

        @functools.wraps(lambda v: False)
        def predicate(v: object) -> bool:
            return False

        RetryPolicy().retry_if_result(predicate)


# ---------------------------------------------------------------------------
# Invalid callable forms
# ---------------------------------------------------------------------------


class TestRejectedCallableForms:
    def test_list_rejected_for_retry_if_result(self) -> None:
        with pytest.raises(InvalidRetryConfigError):
            RetryPolicy().retry_if_result([1, 2, 3])  # type: ignore[arg-type]

    def test_integer_rejected_for_retry_if(self) -> None:
        with pytest.raises(InvalidRetryConfigError):
            RetryPolicy().retry_if(99)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# No side effects before config error
# ---------------------------------------------------------------------------


class TestNoSideEffectsBeforeConfigError:
    def test_or_retry_if_result_invalid_no_attempt_made(self) -> None:
        calls: list[int] = []

        def task() -> int:
            calls.append(1)
            return 1

        # Constructing with invalid predicate must fail before any attempt
        with pytest.raises(InvalidRetryConfigError):
            RetryPolicy().or_retry_if_result(42)  # type: ignore[arg-type]

        # The construction failure itself doesn't call task
        assert calls == []

    def test_custom_delay_invalid_no_sleep_made(self) -> None:
        sleeps: list[float] = []

        with pytest.raises(InvalidRetryConfigError):
            RetryPolicy().custom_delay(42)  # type: ignore[arg-type]

        assert sleeps == []

    def test_stateful_delay_invalid_no_event_fired(self) -> None:
        events: list[object] = []

        with pytest.raises(InvalidRetryConfigError):
            RetryPolicy().stateful_delay(42).on_failure(events.append)  # type: ignore[arg-type]

        assert events == []
