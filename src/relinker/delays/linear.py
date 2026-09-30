"""Linear delay strategy."""

from __future__ import annotations

from dataclasses import dataclass

from relinker.delays.base import DelayMixin
from relinker.internal.validation import MAX_SLEEP_SECONDS, ensure_non_negative, ensure_safe_delay


@dataclass(frozen=True, slots=True)
class LinearDelay(DelayMixin):
    """
    Delay that grows by a fixed step after each attempt.

    Example:
        start=1, step=2 -> 1, 3, 5, 7...

    Without ``maximum``, the delay saturates at MAX_SLEEP_SECONDS once the
    linear growth reaches it, like ExponentialDelay.
    """

    start: float = 0.0
    step: float = 1.0
    maximum: float | None = None

    def __post_init__(self) -> None:
        ensure_safe_delay("start", self.start)
        ensure_non_negative("step", self.step)
        if self.maximum is not None:
            ensure_safe_delay("maximum", self.maximum)

    def next_delay(self, attempt_number: int) -> float:
        """Return the linear delay for the given attempt."""
        delay = self.start + self.step * max(0, attempt_number - 1)
        ceiling = self.maximum if self.maximum is not None else MAX_SLEEP_SECONDS
        return min(delay, ceiling)
