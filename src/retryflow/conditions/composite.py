"""Composite retry conditions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from retryflow.conditions.base import ConditionMixin, RetryCondition


@dataclass(frozen=True, slots=True)
class AnyCondition(ConditionMixin):
    """Retries when any child condition says retry."""

    conditions: tuple[RetryCondition, ...]

    def should_retry_exception(self, error: BaseException) -> bool:
        """Return True when any child retries this exception."""
        return any(condition.should_retry_exception(error) for condition in self.conditions)

    def should_retry_result(self, value: Any) -> bool:
        """Return True when any child retries this value."""
        return any(condition.should_retry_result(value) for condition in self.conditions)


@dataclass(frozen=True, slots=True)
class AllCondition(ConditionMixin):
    """Retries only when all child conditions say retry."""

    conditions: tuple[RetryCondition, ...]

    def should_retry_exception(self, error: BaseException) -> bool:
        """Return True when all children retry this exception."""
        return all(condition.should_retry_exception(error) for condition in self.conditions)

    def should_retry_result(self, value: Any) -> bool:
        """Return True when all children retry this value."""
        return all(condition.should_retry_result(value) for condition in self.conditions)
