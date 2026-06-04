"""Composite delay strategies."""

from __future__ import annotations

from dataclasses import dataclass

from retryflow.delays.base import DelayMixin, DelayStrategy


@dataclass(frozen=True, slots=True)
class AdditiveDelay(DelayMixin):
    """A delay strategy that sums multiple delay strategies."""

    strategies: tuple[DelayStrategy, ...]

    def next_delay(self, attempt_number: int) -> float:
        """Return the sum of all child delays."""
        return sum(strategy.next_delay(attempt_number) for strategy in self.strategies)
