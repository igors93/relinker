"""Custom delay strategy."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from relinker.delays.base import DelayMixin
from relinker.internal.validation import ensure_non_negative


@dataclass(frozen=True, slots=True)
class CustomDelay(DelayMixin):
    """Delegates delay calculation to a user-provided function."""

    callback: Callable[[int], float]

    def next_delay(self, attempt_number: int) -> float:
        """Return the delay produced by the callback."""
        delay = float(self.callback(attempt_number))
        ensure_non_negative("delay", delay)
        return delay
