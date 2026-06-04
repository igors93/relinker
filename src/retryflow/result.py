"""
Result objects for retry executions.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Generic, Literal

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

    def to_dict(self, *, include_value: bool = False) -> dict[str, Any]:
        """
        Return a JSON-friendly dictionary.

        By default the returned value is not included because application values
        may be large, private, or not JSON-serializable. Set include_value=True
        when you explicitly want it.
        """
        data: dict[str, Any] = {
            "succeeded": self.succeeded,
            "failed": self.failed,
            "exhausted": self.exhausted,
            "retry_cause": self.retry_cause,
            "attempt_count": self.attempt_count,
            "total_time": self.total_time,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "error": None,
            "attempts": [
                {
                    "number": attempt.number,
                    "succeeded": attempt.succeeded,
                    "failed": attempt.failed,
                    "started_at": attempt.started_at,
                    "ended_at": attempt.ended_at,
                    "duration": attempt.duration,
                    "error_type": (
                        attempt.error.__class__.__name__ if attempt.error is not None else None
                    ),
                    "error_message": str(attempt.error) if attempt.error is not None else None,
                }
                for attempt in self.attempts
            ],
        }

        if self.error is not None:
            data["error"] = {
                "type": self.error.__class__.__name__,
                "message": str(self.error),
            }

        if include_value:
            data["value"] = self.value

        return data

    def to_json(self, *, include_value: bool = False, indent: int | None = None) -> str:
        """
        Return this result as JSON.

        If include_value=True and the value is not JSON-serializable, json.dumps
        will raise TypeError. That is intentional because RetryFlow should not
        silently alter application data.
        """
        return json.dumps(self.to_dict(include_value=include_value), indent=indent)

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
            lines.append(f"Attempt {attempt.number}: {attempt_status} in {attempt.duration:.4f}s")
            if attempt.error is not None:
                lines.append(f"  Error: {attempt.error.__class__.__name__}: {attempt.error}")
            elif self.exhausted_by_result and attempt is self.attempts[-1]:
                lines.append("  Result was returned but rejected by retry condition.")

        return "\n".join(lines)
