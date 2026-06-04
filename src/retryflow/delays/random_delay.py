"""Random delay strategy."""

from __future__ import annotations

from dataclasses import dataclass
from random import Random

from retryflow.exceptions import InvalidRetryConfigError
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
            raise InvalidRetryConfigError("maximum must be greater than or equal to minimum")

    def next_delay(self, attempt_number: int) -> float:
        """
        Return a random delay.

        When a seed is provided, each attempt gets a deterministic random stream.
        This keeps tests reproducible while preserving random behavior per attempt.
        """
        random = Random(self.seed + attempt_number if self.seed is not None else None)
        return random.uniform(self.minimum, self.maximum)
