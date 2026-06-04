"""Linear delay strategy."""

from __future__ import annotations

from dataclasses import dataclass

from relinker.delays.base import DelayMixin
from relinker.internal.validation import ensure_non_negative


@dataclass(frozen=True, slots=True)
class LinearDelay(DelayMixin):
    """
    Delay that grows by a fixed step after each attempt.

    Example:
        start=1, step=2 -> 1, 3, 5, 7...
    """

    start: float = 0.0
    step: float = 1.0
    maximum: float | None = None

    def __post_init__(self) -> None:
        ensure_non_negative("start", self.start)
        ensure_non_negative("step", self.step)
        if self.maximum is not None:
            ensure_non_negative("maximum", self.maximum)

    def next_delay(self, attempt_number: int) -> float:
        """Return the linear delay for the given attempt."""
        delay = self.start + self.step * max(0, attempt_number - 1)
        if self.maximum is not None:
            return min(delay, self.maximum)
        return delay
