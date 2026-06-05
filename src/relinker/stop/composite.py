"""Composite stop strategies."""

from __future__ import annotations

from dataclasses import dataclass

from relinker.exceptions import InvalidRetryConfigError
from relinker.stop.base import StopMixin, StopStrategy


@dataclass(frozen=True, slots=True)
class AnyStopStrategy(StopMixin):
    """Stops when any child strategy stops."""

    strategies: tuple[StopStrategy, ...]

    def __post_init__(self) -> None:
        if not self.strategies:
            raise InvalidRetryConfigError(
                "AnyStopStrategy requires at least one strategy; got empty collection"
            )

    def should_stop(self, attempt_number: int, elapsed: float) -> bool:
        """Return True when any child strategy stops."""
        return any(strategy.should_stop(attempt_number, elapsed) for strategy in self.strategies)


@dataclass(frozen=True, slots=True)
class AllStopStrategy(StopMixin):
    """Stops only when all child strategies stop."""

    strategies: tuple[StopStrategy, ...]

    def __post_init__(self) -> None:
        if not self.strategies:
            raise InvalidRetryConfigError(
                "AllStopStrategy requires at least one strategy; got empty collection"
            )

    def should_stop(self, attempt_number: int, elapsed: float) -> bool:
        """Return True when all child strategies stop."""
        return all(strategy.should_stop(attempt_number, elapsed) for strategy in self.strategies)
