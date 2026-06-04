"""
Result objects for retry executions.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, Literal

from retryflow.attempt import AttemptRecord
from retryflow.typing import T


RetryCause = Literal["exception", "result"]


@dataclass(frozen=True, slots=True)
class RetryResult(Generic[T]):
    """
    Final execution result.

    This object is useful when users want observability instead of only receiving
    a returned value or an exception.

    Important:
        A run can fail because an exception was raised, or because the retry policy
        kept rejecting returned values until the stop strategy was reached. The
        `exhausted` and `retry_cause` fields make that difference explicit.
    """

    attempts: tuple[AttemptRecord, ...]
    value: T | None = None
    error: BaseException | None = None
    started_at: float = 0.0
    ended_at: float = 0.0
    exhausted: bool = False
    retry_cause: RetryCause | None = None

    @property
    def succeeded(self) -> bool:
        """Return True when the overall execution ended with an accepted value."""
        return self.error is None and not self.exhausted

    @property
    def failed(self) -> bool:
        """Return True when execution ended with an error or exhausted retry policy."""
        return self.error is not None or self.exhausted

    @property
    def attempt_count(self) -> int:
        """Return how many attempts were made."""
        return len(self.attempts)

    @property
    def total_time(self) -> float:
        """Return total execution time in seconds."""
        return self.ended_at - self.started_at

    @property
    def exhausted_by_exception(self) -> bool:
        """Return True when retry stopped after repeated exceptions."""
        return self.exhausted and self.retry_cause == "exception"

    @property
    def exhausted_by_result(self) -> bool:
        """Return True when retry stopped after repeated rejected return values."""
        return self.exhausted and self.retry_cause == "result"

    def last_attempt(self) -> AttemptRecord | None:
        """Return the last attempt, or None when nothing was executed."""
        return self.attempts[-1] if self.attempts else None

    def story(self) -> str:
        """
        Return a readable execution story.

        This is intentionally plain text because it is useful in logs, test
        failures, terminal output, and debugging sessions.
        """
        if self.succeeded:
            status = "succeeded"
        elif self.exhausted:
            status = f"exhausted by {self.retry_cause}"
        else:
            status = "failed"

        lines = [
            "RetryFlow execution story",
            "",
            f"Status: {status}",
            f"Attempts: {self.attempt_count}",
            f"Total time: {self.total_time:.4f}s",
            "",
        ]

        for attempt in self.attempts:
            attempt_status = "succeeded" if attempt.succeeded else "failed"
            lines.append(
                f"Attempt {attempt.number}: {attempt_status} in {attempt.duration:.4f}s"
            )
            if attempt.error is not None:
                lines.append(f"  Error: {attempt.error.__class__.__name__}: {attempt.error}")
            elif self.exhausted_by_result and attempt is self.attempts[-1]:
                lines.append("  Result was returned but rejected by retry condition.")

        return "\n".join(lines)
