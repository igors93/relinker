"""Exponential delay strategy."""

from __future__ import annotations

import math
import sys
from dataclasses import dataclass

from relinker.delays.base import DelayMixin
from relinker.internal.validation import ensure_non_negative, ensure_positive

# When exponential backoff overflows to inf and no explicit maximum is configured,
# the delay saturates here. This prevents InvalidRetryConfigError in long-running
# or forever() policies while keeping the delay representable and finite.
# Callers that need a practical ceiling should set maximum= explicitly.
_SAFE_DELAY_CAP: float = sys.float_info.max / 2


@dataclass(frozen=True, slots=True)
class ExponentialDelay(DelayMixin):
    """
    Exponential backoff delay.

    Formula:
        delay = min(maximum, base * factor ** (attempt_number - 1))

    When ``maximum`` is not set and the computed value overflows to infinity
    (very high attempt counts with factor > 1), the delay saturates at an
    internal finite ceiling instead of propagating ``inf`` to the sleep call.
    Use ``maximum=`` to control the ceiling explicitly.
    """

    base: float = 1.0
    factor: float = 2.0
    maximum: float | None = None

    def __post_init__(self) -> None:
        ensure_non_negative("base", self.base)
        ensure_positive("factor", self.factor)
        if self.maximum is not None:
            ensure_non_negative("maximum", self.maximum)

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
        if not math.isfinite(delay):
            return _SAFE_DELAY_CAP
        return delay
