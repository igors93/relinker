"""Base delay strategy interface and composition helpers."""

from __future__ import annotations

from typing import Protocol, cast


class DelayStrategy(Protocol):
    """Protocol implemented by all delay strategies."""

    def next_delay(self, attempt_number: int) -> float:
        """
        Return the delay before the next attempt.

        attempt_number is one-based and represents the attempt that just failed.
        """


class DelayMixin:
    """
    Mixin that allows delay strategies to be added together.

    The cast call tells static type checkers that classes using this mixin are
    expected to implement the DelayStrategy protocol.
    """

    def __add__(self, other: DelayStrategy) -> DelayStrategy:
        """Return a delay strategy that sums both delays."""
        from relinker.delays.composite import AdditiveDelay

        return AdditiveDelay((cast(DelayStrategy, self), other))
