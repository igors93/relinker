"""Fixed delay strategy."""

from __future__ import annotations

from dataclasses import dataclass

from retryflow.internal.validation import ensure_non_negative


@dataclass(frozen=True, slots=True)
class FixedDelay:
    """Always returns the same delay."""

    seconds: float = 0.0

    def __post_init__(self) -> None:
        ensure_non_negative("seconds", self.seconds)

    def next_delay(self, attempt_number: int) -> float:
        """Return the configured fixed delay."""
        return self.seconds
