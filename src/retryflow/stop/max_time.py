"""Stop strategy based on elapsed time."""

from __future__ import annotations

from dataclasses import dataclass

from retryflow.internal.validation import ensure_non_negative
from retryflow.stop.base import StopMixin


@dataclass(frozen=True, slots=True)
class StopAfterDelay(StopMixin):
    """Stops after the configured amount of elapsed seconds."""

    seconds: float

    def __post_init__(self) -> None:
        ensure_non_negative("seconds", self.seconds)

    def should_stop(self, attempt_number: int, elapsed: float) -> bool:
        """Return True when elapsed time reached the configured limit."""
        return elapsed >= self.seconds
