"""
Regression tests for C4: StatefulCustomDelay._run must reject NaN, inf, and bool
via ensure_non_negative (not just bare < 0 check).
"""

from __future__ import annotations

import pytest

from relinker import RetryPolicy
from relinker.exceptions import InvalidRetryConfigError


class TestStatefulDelayEnsureNonNegative:
    def _policy_with_delay(self, value: object) -> RetryPolicy:  # type: ignore[type-arg]
        return (
            RetryPolicy().attempts(3).no_delay().on(ValueError).stateful_delay(lambda s: value)  # type: ignore[arg-type, return-value]
        )

    def _raise_task(self) -> None:
        raise ValueError("trigger retry")

    def test_nan_raises(self) -> None:
        policy = self._policy_with_delay(float("nan"))
        with pytest.raises(InvalidRetryConfigError, match="stateful delay"):
            policy.run(self._raise_task)

    def test_positive_inf_raises(self) -> None:
        policy = self._policy_with_delay(float("inf"))
        with pytest.raises(InvalidRetryConfigError, match="stateful delay"):
            policy.run(self._raise_task)

    def test_negative_inf_raises(self) -> None:
        policy = self._policy_with_delay(float("-inf"))
        with pytest.raises(InvalidRetryConfigError, match="stateful delay"):
            policy.run(self._raise_task)

    def test_bool_true_raises(self) -> None:
        policy = self._policy_with_delay(True)
        with pytest.raises(InvalidRetryConfigError, match="stateful delay"):
            policy.run(self._raise_task)

    def test_bool_false_raises(self) -> None:
        policy = self._policy_with_delay(False)
        with pytest.raises(InvalidRetryConfigError, match="stateful delay"):
            policy.run(self._raise_task)

    def test_negative_raises(self) -> None:
        policy = self._policy_with_delay(-0.001)
        with pytest.raises(InvalidRetryConfigError, match="stateful delay"):
            policy.run(self._raise_task)

    def test_zero_accepted(self) -> None:
        calls = [0]

        def task() -> str:
            calls[0] += 1
            if calls[0] < 2:
                raise ValueError("retry")
            return "done"

        policy = RetryPolicy().attempts(5).on(ValueError).stateful_delay(lambda s: 0.0)
        result = policy.run(task)
        assert result == "done"

    def test_int_zero_rejected_as_bool_alternative(self) -> None:
        """int(0) is valid (not a bool), should be accepted and coerced to float."""
        calls = [0]

        def task() -> str:
            calls[0] += 1
            if calls[0] < 2:
                raise ValueError("retry")
            return "done"

        policy = RetryPolicy().attempts(5).on(ValueError).stateful_delay(lambda s: 0)
        result = policy.run(task)
        assert result == "done"
