"""Retry condition based on returned values."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from relinker.conditions.base import ConditionMixin
from relinker.internal.callables import ensure_callable


@dataclass(frozen=True, slots=True)
class ResultCondition(ConditionMixin):
    """Retries when a user-provided predicate returns True for a value."""

    predicate: Callable[[Any], bool]

    def __post_init__(self) -> None:
        ensure_callable("predicate", self.predicate)

    def should_retry_exception(self, error: BaseException) -> bool:
        """Result-based conditions do not retry exceptions."""
        return False

    def should_retry_result(self, value: Any) -> bool:
        """Return True when the value should trigger another attempt."""
        return bool(self.predicate(value))
