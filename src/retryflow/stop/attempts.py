"""Stop strategy based on attempt count."""

from __future__ import annotations

from dataclasses import dataclass

from retryflow.internal.validation import ensure_positive_int
from retryflow.stop.base import StopMixin


@dataclass(frozen=True, slots=True)
class StopAfterAttempt(StopMixin):
    """Stops after a maximum number of attempts."""

    maximum: int = 3

    def __post_init__(self) -> None:
        ensure_positive_int("maximum", self.maximum)

    def should_stop(self, attempt_number: int, elapsed: float) -> bool:
        """Return True when the maximum number of attempts has been reached."""
        return attempt_number >= self.maximum
