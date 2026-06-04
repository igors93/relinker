"""Base stop strategy interface."""

from __future__ import annotations

from typing import Protocol


class StopStrategy(Protocol):
    """Protocol implemented by all stop strategies."""

    def should_stop(self, attempt_number: int, elapsed: float) -> bool:
        """
        Return True when RetryFlow should stop after the current attempt.

        attempt_number is one-based and represents the attempt that just ran.
        elapsed is total elapsed time in seconds.
        """
