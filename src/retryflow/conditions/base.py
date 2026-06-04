"""Base retry condition interfaces and composition helpers."""

from __future__ import annotations

from typing import Any, Protocol, cast


class RetryCondition(Protocol):
    """
    Protocol implemented by retry conditions.

    A condition can decide based on an exception, a returned value, or both.
    """

    def should_retry_exception(self, error: BaseException) -> bool:
        """Return True when this exception should be retried."""

    def should_retry_result(self, value: Any) -> bool:
        """Return True when this returned value should be retried."""


class ConditionMixin:
    """
    Mixin that gives retry conditions boolean composition.

    This mixin is intentionally not a Protocol itself. The cast calls below tell
    static type checkers that classes using this mixin are expected to implement
    the RetryCondition protocol.
    """

    def __or__(self, other: RetryCondition) -> RetryCondition:
        """Return a condition that passes when either condition passes."""
        from retryflow.conditions.composite import AnyCondition

        return AnyCondition((cast(RetryCondition, self), other))

    def __and__(self, other: RetryCondition) -> RetryCondition:
        """Return a condition that passes only when both conditions pass."""
        from retryflow.conditions.composite import AllCondition

        return AllCondition((cast(RetryCondition, self), other))
