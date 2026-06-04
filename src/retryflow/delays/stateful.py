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

from retryflow.exceptions import InvalidRetryConfigError

if TYPE_CHECKING:
    from retryflow.delays.base import DelayStrategy
    from retryflow.state import RetryState


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

    def next_delay(self, attempt_number: int) -> float:
        """
        Simulation fallback: build a minimal state from attempt_number only.

        When simulate() calls this method, last_value and last_error will be None.
        The callback should handle None gracefully (e.g. fall back to a default).
        """
        from retryflow.state import RetryState

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
        if delay < 0:
            raise InvalidRetryConfigError(
                f"stateful delay callback returned a negative value: {delay}"
            )
        return delay


def resolve_delay(
    strategy: DelayStrategy,
    attempt_number: int,
    state: RetryState,
) -> float:
    """
    Resolve the next delay value.

    Uses the state-aware path when the strategy is a StatefulCustomDelay;
    otherwise falls back to the standard attempt-number-based path.

    This function is used by executors and context managers so they do not
    need to know which kind of delay strategy is configured.
    """
    if isinstance(strategy, StatefulCustomDelay):
        return strategy.next_delay_with_state(state)
    return strategy.next_delay(attempt_number)
