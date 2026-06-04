"""Base delay strategy interface."""

from __future__ import annotations

from typing import Protocol


class DelayStrategy(Protocol):
    """Protocol implemented by all delay strategies."""

    def next_delay(self, attempt_number: int) -> float:
        """
        Return the delay before the next attempt.

        attempt_number is one-based and represents the attempt that just failed.
        """
