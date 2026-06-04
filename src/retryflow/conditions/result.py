"""Retry condition based on returned values."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from retryflow.conditions.base import ConditionMixin


@dataclass(frozen=True, slots=True)
class ResultCondition(ConditionMixin):
    """Retries when a user-provided predicate returns True for a value."""

    predicate: Callable[[Any], bool]

    def should_retry_exception(self, error: BaseException) -> bool:
        """Result-based conditions do not retry exceptions."""
        return False

    def should_retry_result(self, value: Any) -> bool:
        """Return True when the value should trigger another attempt."""
        return bool(self.predicate(value))
