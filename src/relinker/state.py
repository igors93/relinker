"""Runtime state objects."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from relinker.attempt import AttemptRecord

RetryCause = Literal["exception", "result"]


@dataclass(frozen=True, slots=True)
class RetryState:
    """Immutable snapshot of a retry execution."""

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
    policy_delay: float | None = None
    budget_delay: float | None = None
    policy_name: str | None = None

    @property
    def attempt_count(self) -> int:
        """Return how many attempts have been recorded in this snapshot."""
        return len(self.attempts)

    @property
    def failed_attempts(self) -> int:
        """Return how many recorded attempts raised an exception."""
        return sum(1 for attempt in self.attempts if attempt.failed)

    @property
    def successful_attempts(self) -> int:
        """Return how many recorded attempts completed without an exception."""
        return sum(1 for attempt in self.attempts if attempt.succeeded)

    def last_attempt(self) -> AttemptRecord | None:
        """Return the most recent attempt record, or None when no attempts were made."""
        return self.attempts[-1] if self.attempts else None

    @property
    def has_error(self) -> bool:
        """Return True when this state contains an exception."""
        return self.last_error is not None
