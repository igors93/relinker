"""Random delay strategy."""

from __future__ import annotations

from dataclasses import dataclass
from random import Random

from retryflow.internal.validation import ensure_non_negative


@dataclass(frozen=True, slots=True)
class RandomDelay:
    """Returns a random delay between minimum and maximum."""

    minimum: float = 0.0
    maximum: float = 1.0
    seed: int | None = None

    def __post_init__(self) -> None:
        ensure_non_negative("minimum", self.minimum)
        ensure_non_negative("maximum", self.maximum)
        if self.maximum < self.minimum:
            msg = "maximum must be greater than or equal to minimum"
            raise ValueError(msg)

    def next_delay(self, attempt_number: int) -> float:
        """Return a random delay."""
        random = Random(self.seed + attempt_number if self.seed is not None else None)
        return random.uniform(self.minimum, self.maximum)
