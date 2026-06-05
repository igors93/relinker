"""
Attempt records.

An attempt is one execution of the wrapped function. Relinker stores attempts
so users can inspect what happened after a run.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class AttemptRecord:
    """
    Immutable information about a single attempt.

    Attributes:
        number: One-based attempt number.
        started_at: Monotonic timestamp when the attempt started.
        ended_at: Monotonic timestamp when the attempt ended.
        value: Returned value, when the attempt produced one. May be None.
        error: Raised exception, when the attempt failed.
        has_value: True when the attempt produced a return value.
            Use this rather than checking ``value is not None`` because
            None is a valid function result.
    """

    number: int
    started_at: float
    ended_at: float
    value: Any = None
    error: BaseException | None = None
    has_value: bool = False

    @property
    def duration(self) -> float:
        """Return how many seconds this attempt took."""
        return self.ended_at - self.started_at

    @property
    def succeeded(self) -> bool:
        """Return True when this attempt completed without an exception."""
        return self.error is None

    @property
    def failed(self) -> bool:
        """Return True when this attempt raised an exception."""
        return self.error is not None
