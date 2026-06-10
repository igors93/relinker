"""Composite delay strategies."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from relinker.delays.base import DelayMixin, DelayStrategy

if TYPE_CHECKING:
    from relinker.state import RetryState


@dataclass(frozen=True, slots=True)
class AdditiveDelay(DelayMixin):
    """A delay strategy that sums multiple delay strategies."""

    strategies: tuple[DelayStrategy, ...]

    def next_delay(self, attempt_number: int) -> float:
        """Return the sum of all child delays (attempt-number path, no real state)."""
        return _resolve_additive_tree(self, attempt_number, None)

    def next_delay_with_state(self, attempt_number: int, state: RetryState) -> float:
        """Return the sum of all child delays, passing real state to stateful children."""
        return _resolve_additive_tree(self, attempt_number, state)


def _resolve_additive_tree(
    root: AdditiveDelay,
    attempt_number: int,
    state: RetryState | None,
) -> float:
    """Iterative resolution so deeply nested trees never cause RecursionError."""
    from relinker.delays.stateful import StatefulCustomDelay

    frames = [_AdditiveDelayFrame(delay=root)]
    resolved_child: float | None = None

    while frames:
        frame = frames[-1]

        if resolved_child is not None:
            frame.values.append(resolved_child)
            resolved_child = None

        if frame.index >= len(frame.delay.strategies):
            resolved_child = sum(frame.values)
            frames.pop()
            continue

        strategy = frame.delay.strategies[frame.index]
        frame.index += 1

        if isinstance(strategy, AdditiveDelay):
            frames.append(_AdditiveDelayFrame(delay=strategy))
        elif isinstance(strategy, StatefulCustomDelay) and state is not None:
            frame.values.append(strategy.next_delay_with_state(state))
        else:
            frame.values.append(strategy.next_delay(attempt_number))

    if resolved_child is None:  # Defensive guard; the root frame always resolves.
        return 0.0
    return resolved_child


@dataclass(slots=True)
class _AdditiveDelayFrame:
    delay: AdditiveDelay
    index: int = 0
    values: list[float] = field(default_factory=list)
