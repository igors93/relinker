"""Composite retry conditions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from relinker.conditions.base import ConditionMixin, RetryCondition
from relinker.exceptions import InvalidRetryConfigError


@dataclass(frozen=True, slots=True)
class AnyCondition(ConditionMixin):
    """Retries when any child condition says retry."""

    conditions: tuple[RetryCondition, ...]

    def __post_init__(self) -> None:
        if not self.conditions:
            raise InvalidRetryConfigError(
                "AnyCondition requires at least one condition; got empty collection"
            )

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

    def __post_init__(self) -> None:
        if not self.conditions:
            raise InvalidRetryConfigError(
                "AllCondition requires at least one condition; got empty collection"
            )

    def should_retry_exception(self, error: BaseException) -> bool:
        """Return True when all children retry this exception."""
        return all(condition.should_retry_exception(error) for condition in self.conditions)

    def should_retry_result(self, value: Any) -> bool:
        """Return True when all children retry this value."""
        return all(condition.should_retry_result(value) for condition in self.conditions)
