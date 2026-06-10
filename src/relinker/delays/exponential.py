"""Exponential delay strategy."""

from __future__ import annotations

from dataclasses import dataclass

from relinker.delays.base import DelayMixin
from relinker.internal.validation import (
    MAX_SLEEP_SECONDS,
    ensure_non_negative,
    ensure_positive,
    ensure_safe_delay,
)

# Re-exported for backward compatibility with code that imported _SAFE_DELAY_CAP directly.
_SAFE_DELAY_CAP: float = MAX_SLEEP_SECONDS


@dataclass(frozen=True, slots=True)
class ExponentialDelay(DelayMixin):
    """
    Exponential backoff delay.

    Formula:
        delay = min(maximum, base * factor ** (attempt_number - 1))

    When ``maximum`` is not set and the computed value overflows to infinity
    (very high attempt counts with factor > 1), the delay saturates at
    MAX_SLEEP_SECONDS instead of propagating ``inf`` to the sleep call.
    Use ``maximum=`` to control the ceiling explicitly; values above
    MAX_SLEEP_SECONDS are rejected early.
    """

    base: float = 1.0
    factor: float = 2.0
    maximum: float | None = None

    def __post_init__(self) -> None:
        ensure_non_negative("base", self.base)
        ensure_positive("factor", self.factor)
        if self.maximum is not None:
            ensure_safe_delay("maximum", self.maximum)

    def next_delay(self, attempt_number: int) -> float:
        """Return exponential delay for the given attempt number."""
        if self.base == 0.0:
            return 0.0
        try:
            delay = self.base * (self.factor ** max(0, attempt_number - 1))
        except OverflowError:
            delay = float("inf")
        if self.maximum is not None:
            return min(delay, self.maximum)
        if delay > MAX_SLEEP_SECONDS:
            return MAX_SLEEP_SECONDS
        return delay
