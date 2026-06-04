"""Base stop strategy interface and composition helpers."""

from __future__ import annotations

from typing import Protocol, cast


class StopStrategy(Protocol):
    """Protocol implemented by all stop strategies."""

    def should_stop(self, attempt_number: int, elapsed: float) -> bool:
        """
        Return True when Relinker should stop after the current attempt.

        attempt_number is one-based and represents the attempt that just ran.
        elapsed is total elapsed time in seconds.
        """


class StopMixin:
    """
    Mixin that allows stop strategies to be combined with `|` and `&`.

    The cast calls tell static type checkers that classes using this mixin are
    expected to implement the StopStrategy protocol.
    """

    def __or__(self, other: StopStrategy) -> StopStrategy:
        """Return a stop strategy that stops when either strategy stops."""
        from relinker.stop.composite import AnyStopStrategy

        return AnyStopStrategy((cast(StopStrategy, self), other))

    def __and__(self, other: StopStrategy) -> StopStrategy:
        """Return a stop strategy that stops only when both strategies stop."""
        from relinker.stop.composite import AllStopStrategy

        return AllStopStrategy((cast(StopStrategy, self), other))
