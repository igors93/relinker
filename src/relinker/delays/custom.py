"""Custom delay strategy."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from relinker.delays.base import DelayMixin
from relinker.internal.validation import ensure_resolved_delay


@dataclass(frozen=True, slots=True)
class CustomDelay(DelayMixin):
    """Delegates delay calculation to a user-provided function."""

    callback: Callable[[int], float]

    def next_delay(self, attempt_number: int) -> float:
        """Return the validated delay produced by the callback."""
        delay = self.callback(attempt_number)
        return ensure_resolved_delay(delay)
