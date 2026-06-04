"""
Result objects for retry executions.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Generic

from retryflow.attempt import AttemptRecord
from retryflow.typing import T


@dataclass(frozen=True, slots=True)
class RetryResult(Generic[T]):
    """
    Final execution result.

    This object is useful when users want observability instead of only receiving
    a returned value or an exception.
    """

    attempts: tuple[AttemptRecord, ...]
    value: T | None = None
    error: BaseException | None = None
    started_at: float = 0.0
    ended_at: float = 0.0

    @property
    def succeeded(self) -> bool:
        """Return True when the overall execution succeeded."""
        return self.error is None

    @property
    def failed(self) -> bool:
        """Return True when the overall execution failed."""
        return self.error is not None

    @property
    def attempt_count(self) -> int:
        """Return how many attempts were made."""
        return len(self.attempts)

    @property
    def total_time(self) -> float:
        """Return total execution time in seconds."""
        return self.ended_at - self.started_at

    def last_attempt(self) -> AttemptRecord | None:
        """Return the last attempt, or None when nothing was executed."""
        return self.attempts[-1] if self.attempts else None

    def story(self) -> str:
        """
        Return a readable execution story.

        This is intentionally plain text because it is useful in logs, test
        failures, terminal output, and debugging sessions.
        """
        lines = [
            "RetryFlow execution story",
            "",
            f"Status: {'succeeded' if self.succeeded else 'failed'}",
            f"Attempts: {self.attempt_count}",
            f"Total time: {self.total_time:.4f}s",
            "",
        ]

        for attempt in self.attempts:
            status = "succeeded" if attempt.succeeded else "failed"
            lines.append(f"Attempt {attempt.number}: {status} in {attempt.duration:.4f}s")
            if attempt.error is not None:
                lines.append(f"  Error: {attempt.error.__class__.__name__}: {attempt.error}")

        return "\n".join(lines)
