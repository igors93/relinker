"""
Result objects for retry executions.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Generic, Literal, cast

from relinker.attempt import AttemptRecord
from relinker.typing import T

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

        When a policy uses bounded history, `attempts` contains only the retained
        records. Aggregate counters still describe the complete execution.
    """

    attempts: tuple[AttemptRecord, ...]
    value: T | None = None
    error: BaseException | None = None
    started_at: float = 0.0
    ended_at: float = 0.0
    exhausted: bool = False
    retry_cause: RetryCause | None = None
    total_attempts: int = 0
    total_failed_attempts: int | None = None
    total_successful_attempts: int | None = None
    policy_name: str | None = None

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
        """
        Return how many attempts were made in total.

        When a history limit is configured, `attempts` may contain fewer records
        than this count. Use this property instead of `len(attempts)` to obtain
        the complete execution total.
        """
        return self.total_attempts if self.total_attempts else len(self.attempts)

    @property
    def retained_attempt_count(self) -> int:
        """Return the number of attempt records currently retained in memory."""
        return len(self.attempts)

    @property
    def history_truncated(self) -> bool:
        """Return True when older attempt records were discarded."""
        return self.retained_attempt_count < self.attempt_count

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

    @property
    def last_error(self) -> BaseException | None:
        """Return the most recent error available in the retained attempt history."""
        for attempt in reversed(self.attempts):
            if attempt.error is not None:
                return attempt.error
        return None

    @property
    def has_last_value(self) -> bool:
        """Return True when the retained history contains a produced value."""
        return any(attempt.has_value for attempt in self.attempts)

    @property
    def last_value(self) -> T | None:
        """
        Return the most recent value available in the retained attempt history.

        The returned value may be None. Use `has_last_value` to distinguish a
        produced None value from the absence of a retained value.
        """
        for attempt in reversed(self.attempts):
            if attempt.has_value:
                return cast(T, attempt.value)
        return None

    @property
    def failed_attempts(self) -> int:
        """
        Return the total number of attempts that raised an exception.

        Executors populate `total_failed_attempts` independently from retained
        history. Manually constructed results that omit this aggregate fall back
        to counting the available records.
        """
        if self.total_failed_attempts is not None:
            return self.total_failed_attempts
        return sum(1 for attempt in self.attempts if attempt.failed)

    @property
    def successful_attempts(self) -> int:
        """
        Return the total number of attempts that returned without an exception.

        Executors populate `total_successful_attempts` independently from retained
        history. Manually constructed results that omit this aggregate fall back
        to counting the available records.
        """
        if self.total_successful_attempts is not None:
            return self.total_successful_attempts
        return sum(1 for attempt in self.attempts if attempt.succeeded)

    @property
    def error_types(self) -> tuple[type[BaseException], ...]:
        """Return distinct exception types available in the retained history."""
        seen: list[type[BaseException]] = []

        for attempt in self.attempts:
            if attempt.error is None:
                continue

            error_type: type[BaseException] = type(attempt.error)

            if error_type not in seen:
                seen.append(error_type)

        return tuple(seen)

    def last_attempt(self) -> AttemptRecord | None:
        """Return the last retained attempt, or None when no record is available."""
        return self.attempts[-1] if self.attempts else None

    def summary(self) -> dict[str, Any]:
        """
        Return a compact dictionary suitable for logging.

        Values are intentionally excluded to keep log lines small and safe.
        Use `to_dict(include_value=True)` when you need the full result.
        """
        return {
            "succeeded": self.succeeded,
            "exhausted": self.exhausted,
            "retry_cause": self.retry_cause,
            "attempt_count": self.attempt_count,
            "failed_attempts": self.failed_attempts,
            "successful_attempts": self.successful_attempts,
            "retained_attempt_count": self.retained_attempt_count,
            "history_truncated": self.history_truncated,
            "total_time": round(self.total_time, 3),
            "policy_name": self.policy_name,
            "error": self.error.__class__.__name__ if self.error is not None else None,
            "error_types": [error_type.__name__ for error_type in self.error_types],
        }

    def to_dict(self, *, include_value: bool = False) -> dict[str, Any]:
        """
        Return a JSON-friendly dictionary.

        By default the returned value is not included because application values
        may be large, private, or not JSON-serializable. Set `include_value=True`
        when you explicitly want it.

        The `attempts` list contains retained history. Aggregate counters describe
        the complete execution even when older records were discarded.
        """
        data: dict[str, Any] = {
            "succeeded": self.succeeded,
            "failed": self.failed,
            "exhausted": self.exhausted,
            "retry_cause": self.retry_cause,
            "attempt_count": self.attempt_count,
            "failed_attempts": self.failed_attempts,
            "successful_attempts": self.successful_attempts,
            "retained_attempt_count": self.retained_attempt_count,
            "history_truncated": self.history_truncated,
            "total_time": self.total_time,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "policy_name": self.policy_name,
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

        If `include_value=True` and the value is not JSON-serializable,
        `json.dumps()` raises `TypeError`. That is intentional because Relinker
        should not silently alter application data.
        """
        return json.dumps(self.to_dict(include_value=include_value), indent=indent)

    def story(self) -> str:
        """
        Return a readable execution story.

        This is intentionally plain text because it is useful in logs, test
        failures, terminal output, and debugging sessions. When history is
        truncated, the story says how many records were retained.
        """
        if self.succeeded:
            status = "succeeded"
        elif self.exhausted:
            status = f"exhausted by {self.retry_cause}"
        else:
            status = "failed"

        lines = [
            "Relinker execution story",
            "",
            f"Status: {status}",
            f"Attempts: {self.attempt_count}",
            f"Failed attempts: {self.failed_attempts}",
            f"Successful attempts: {self.successful_attempts}",
            f"Total time: {self.total_time:.4f}s",
            "",
        ]

        if self.history_truncated:
            lines.extend(
                [
                    (
                        f"Retained history: last {self.retained_attempt_count} "
                        f"of {self.attempt_count} attempts"
                    ),
                    "",
                ]
            )

        for attempt in self.attempts:
            attempt_status = "succeeded" if attempt.succeeded else "failed"
            lines.append(f"Attempt {attempt.number}: {attempt_status} in {attempt.duration:.4f}s")
            if attempt.error is not None:
                lines.append(f"  Error: {attempt.error.__class__.__name__}: {attempt.error}")
            elif self.exhausted_by_result and attempt is self.attempts[-1]:
                lines.append("  Result was returned but rejected by retry condition.")

        return "\n".join(lines)
