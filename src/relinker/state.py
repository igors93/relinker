"""
Runtime state objects.

RetryState is a snapshot of the retry execution at a specific moment. It is used
by events and advanced integrations so users can inspect what Relinker knows
without depending on private executor internals.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from relinker.attempt import AttemptRecord

RetryCause = Literal["exception", "result"]


@dataclass(frozen=True, slots=True)
class RetryState:
    """
    Immutable snapshot of a retry execution.

    Attributes:
        function_name: Human-readable function name.
        attempt_number: Current one-based attempt number.
        started_at: Monotonic timestamp when the whole retry execution started.
        elapsed: Seconds elapsed since the whole retry execution started.
        attempts: Attempts recorded before this snapshot.
        last_value: Last returned value, when available. May be None even when
            has_value is True, because None is a valid function result.
        last_error: Last raised exception, when available.
        has_value: True when last_value was explicitly produced by the function.
            Check this instead of ``last_value is not None`` to distinguish a
            successful None return from an attempt that raised an exception.
        next_delay: Delay before the next attempt, when known.
        retry_cause: Whether retry was caused by an exception or a returned value.
        will_retry: True when Relinker decided another attempt should happen.
        will_stop: True when the stop strategy decided no more attempts should happen.
    """

    function_name: str
    attempt_number: int
    started_at: float
    elapsed: float
    attempts: tuple[AttemptRecord, ...] = ()
    last_value: Any = None
    last_error: BaseException | None = None
    has_value: bool = False
    next_delay: float | None = None
    retry_cause: RetryCause | None = None
    will_retry: bool = False
    will_stop: bool = False

    @property
    def attempt_count(self) -> int:
        """Return how many attempts have been recorded in this snapshot."""
        return len(self.attempts)

    @property
    def failed_attempts(self) -> int:
        """Return how many recorded attempts raised an exception."""
        return sum(1 for a in self.attempts if a.failed)

    @property
    def successful_attempts(self) -> int:
        """Return how many recorded attempts completed without an exception."""
        return sum(1 for a in self.attempts if a.succeeded)

    def last_attempt(self) -> AttemptRecord | None:
        """Return the most recent attempt record, or None when no attempts were made."""
        return self.attempts[-1] if self.attempts else None

    @property
    def has_error(self) -> bool:
        """Return True when this state contains an exception."""
        return self.last_error is not None
