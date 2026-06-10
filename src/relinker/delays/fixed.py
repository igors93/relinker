"""Fixed delay strategy."""

from __future__ import annotations

from dataclasses import dataclass

from relinker.delays.base import DelayMixin
from relinker.internal.validation import ensure_safe_delay


@dataclass(frozen=True, slots=True)
class FixedDelay(DelayMixin):
    """Always returns the same delay."""

    seconds: float = 0.0

    def __post_init__(self) -> None:
        ensure_safe_delay("seconds", self.seconds)

    def next_delay(self, attempt_number: int) -> float:
        """Return the configured fixed delay."""
        return self.seconds
