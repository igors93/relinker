"""Exponential delay strategy."""

from __future__ import annotations

from dataclasses import dataclass

from retryflow.internal.validation import ensure_non_negative, ensure_positive


@dataclass(frozen=True, slots=True)
class ExponentialDelay:
    """
    Exponential backoff delay.

    Formula:
        delay = min(maximum, base * factor ** (attempt_number - 1))
    """

    base: float = 1.0
    factor: float = 2.0
    maximum: float | None = None

    def __post_init__(self) -> None:
        ensure_non_negative("base", self.base)
        ensure_positive("factor", self.factor)
        if self.maximum is not None:
            ensure_non_negative("maximum", self.maximum)

    def next_delay(self, attempt_number: int) -> float:
        """Return exponential delay for the given attempt number."""
        delay = self.base * (self.factor ** max(0, attempt_number - 1))
        if self.maximum is not None:
            return min(delay, self.maximum)
        return delay
