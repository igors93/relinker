"""Runtime state objects."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from relinker.attempt import AttemptRecord

RetryCause = Literal["exception", "result"]


@dataclass(frozen=True, slots=True)
class RetryState:
    """
    Immutable snapshot of a retry execution.

    Security note:
        ``last_value`` and ``last_error`` are excluded from ``repr()`` because
        they may contain secrets, tokens, or sensitive user data.
    """

    function_name: str
    attempt_number: int
    started_at: float
    elapsed: float
    attempts: tuple[AttemptRecord, ...] = ()
    last_value: Any = field(default=None, repr=False)
    last_error: BaseException | None = field(default=None, repr=False)
    has_value: bool = False
    next_delay: float | None = None
    retry_cause: RetryCause | None = None
    will_retry: bool = False
    will_stop: bool = False
    policy_delay: float | None = None
    budget_delay: float | None = None
    policy_name: str | None = None
    total_attempts: int = 0
    total_failed_attempts: int | None = None
    total_successful_attempts: int | None = None

    @property
    def attempt_count(self) -> int:
        """Return how many attempts have been made in total.

        When a history limit is configured, ``attempts`` may contain fewer
        records. Use this property instead of ``len(attempts)`` to obtain the
        complete execution total. When ``total_attempts`` is not populated
        (manually constructed snapshots), falls back to ``len(attempts)``.
        """
        return self.total_attempts if self.total_attempts else len(self.attempts)

    @property
    def retained_attempt_count(self) -> int:
        """Return the number of attempt records currently retained in memory."""
        return len(self.attempts)

    @property
    def failed_attempts(self) -> int:
        """Return how many attempts raised an exception."""
        if self.total_failed_attempts is not None:
            return self.total_failed_attempts
        return sum(1 for attempt in self.attempts if attempt.failed)

    @property
    def successful_attempts(self) -> int:
        """Return how many attempts completed without an exception."""
        if self.total_successful_attempts is not None:
            return self.total_successful_attempts
        return sum(1 for attempt in self.attempts if attempt.succeeded)

    def last_attempt(self) -> AttemptRecord | None:
        """Return the most recent attempt record, or None when no attempts were made."""
        return self.attempts[-1] if self.attempts else None

    @property
    def has_error(self) -> bool:
        """Return True when this state contains an exception."""
        return self.last_error is not None
