"""Random exponential delay strategy."""

from __future__ import annotations

from dataclasses import dataclass
from random import Random

from relinker.delays.base import DelayMixin
from relinker.exceptions import InvalidRetryConfigError
from relinker.internal.validation import MAX_SLEEP_SECONDS, ensure_positive, ensure_safe_delay


@dataclass(frozen=True, slots=True)
class RandomExponentialDelay(DelayMixin):
    """
    Exponential backoff with random jitter.

    This uses a "full jitter" style strategy:
        delay = random(minimum, exponential_cap)

    It is useful when many clients may retry at the same time. Fixed seeds keep
    tests reproducible, but also repeat per-attempt delays across executions that
    reuse the same seed.
    """

    base: float = 1.0
    factor: float = 2.0
    minimum: float = 0.0
    maximum: float | None = None
    seed: int | None = None

    def __post_init__(self) -> None:
        from relinker.internal.validation import ensure_non_negative

        ensure_non_negative("base", self.base)
        ensure_positive("factor", self.factor)
        ensure_safe_delay("minimum", self.minimum)
        if self.maximum is not None:
            ensure_safe_delay("maximum", self.maximum)
            if self.maximum < self.minimum:
                raise InvalidRetryConfigError("maximum must be greater than or equal to minimum")

    def next_delay(self, attempt_number: int) -> float:
        """Return a random exponential delay for the given attempt."""
        if self.base == 0.0:
            return float(self.minimum)
        try:
            cap = self.base * (self.factor ** max(0, attempt_number - 1))
        except OverflowError:
            cap = float("inf")
        if self.maximum is not None:
            cap = min(cap, self.maximum)
        elif cap > MAX_SLEEP_SECONDS:
            cap = MAX_SLEEP_SECONDS

        upper = max(self.minimum, cap)
        random = Random(self.seed + attempt_number if self.seed is not None else None)
        return random.uniform(self.minimum, upper)
