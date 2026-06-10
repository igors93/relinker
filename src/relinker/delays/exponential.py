"""Exponential delay strategy."""

from __future__ import annotations

from dataclasses import dataclass

from relinker.delays.base import DelayMixin
from relinker.internal.validation import ensure_non_negative, ensure_positive

# Maximum delay produced when exponential growth overflows and no explicit
# maximum is configured.  The value is 1 day (86 400 seconds).
#
# Rationale:
#   - time.sleep() and asyncio.sleep() use _PyTime_t (signed int64, nanoseconds)
#     internally.  Values above ~9.22e9 seconds raise OverflowError on all
#     supported platforms (Python 3.10-3.14, Linux/macOS/Windows).
#     sys.float_info.max / 2 ≈ 8.99e307 is far outside this range.
#   - 86 400 s (1 day) is more than enough for any practical backoff ceiling.
#   - Callers that need a different ceiling must set ``maximum=`` explicitly.
_SAFE_DELAY_CAP: float = 86_400.0


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
        if delay > _SAFE_DELAY_CAP:
            return _SAFE_DELAY_CAP
        return delay
