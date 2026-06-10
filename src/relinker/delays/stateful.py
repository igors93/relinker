"""
State-aware delay strategy.

Regular delay strategies receive only the attempt number. A stateful delay
strategy receives the full RetryState snapshot, enabling delays that adapt
based on the last error, last value, elapsed time, or other execution context.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from relinker.internal.callables import ensure_callable
from relinker.internal.validation import ensure_resolved_delay

if TYPE_CHECKING:
    from relinker.delays.base import DelayStrategy
    from relinker.state import RetryState


@dataclass(frozen=True, slots=True)
class StatefulCustomDelay:
    """
    Delay strategy that receives a RetryState instead of only the attempt number.

    This allows delays that adapt based on execution context, such as reading
    a Retry-After response header or backing off based on the error type.

    The callback must return a non-negative float. A negative return value
    raises InvalidRetryConfigError immediately.

    Example:
        policy = RetryPolicy().stateful_delay(lambda state: state.attempt_number * 0.5)
    """

    callback: Callable[[RetryState], float]

    def __post_init__(self) -> None:
        ensure_callable("callback", self.callback)

    def next_delay(self, attempt_number: int) -> float:
        """
        Attempt-number fallback for delay composition without a RetryState.

        This path builds a minimal state and executes the callback. It does not make
        RetryPolicy.simulate() support stateful callbacks; simulation rejects user
        callbacks instead of executing application code.
        """
        from relinker.state import RetryState

        minimal = RetryState(
            function_name="<simulation>",
            attempt_number=attempt_number,
            started_at=0.0,
            elapsed=0.0,
        )
        return self._run(minimal)

    def next_delay_with_state(self, state: RetryState) -> float:
        """Return the delay for the given execution state."""
        return self._run(state)

    def _run(self, state: RetryState) -> float:
        delay = self.callback(state)
        return ensure_resolved_delay(delay)


def delay_needs_state(strategy: DelayStrategy) -> bool:
    """Return True if the strategy tree contains any StatefulCustomDelay."""
    from relinker.delays.composite import AdditiveDelay

    if isinstance(strategy, StatefulCustomDelay):
        return True
    if isinstance(strategy, AdditiveDelay):
        stack = list(strategy.strategies)
        while stack:
            child = stack.pop()
            if isinstance(child, StatefulCustomDelay):
                return True
            if isinstance(child, AdditiveDelay):
                stack.extend(child.strategies)
    return False


def resolve_delay(
    strategy: DelayStrategy,
    attempt_number: int,
    state: RetryState | None,
) -> float:
    """
    Resolve the next delay value passing real execution state to any stateful children.

    - StatefulCustomDelay at root: uses next_delay_with_state(state) when state is provided
    - AdditiveDelay at root: uses next_delay_with_state(attempt_number, state) so
      every stateful child in the tree receives the real state
    - All other strategies, or when state is None: uses next_delay(attempt_number)
    """
    from relinker.delays.composite import AdditiveDelay

    if isinstance(strategy, StatefulCustomDelay):
        if state is not None:
            return strategy.next_delay_with_state(state)
        return strategy.next_delay(attempt_number)
    if isinstance(strategy, AdditiveDelay):
        if state is not None:
            return strategy.next_delay_with_state(attempt_number, state)
        return strategy.next_delay(attempt_number)
    return strategy.next_delay(attempt_number)
