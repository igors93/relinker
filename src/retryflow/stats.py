"""
Retry statistics.

Statistics are intentionally simple and in-memory. They are attached to decorated
functions so users can inspect retry behavior without adding external tools.
"""

from __future__ import annotations

from dataclasses import dataclass
from threading import Lock
from typing import Any

from retryflow.result import RetryResult


@dataclass(frozen=True, slots=True)
class RetryStatsSnapshot:
    """Immutable snapshot of retry statistics."""

    calls: int
    successes: int
    failures: int
    exhausted: int
    total_attempts: int
    total_time: float

    @property
    def average_attempts(self) -> float:
        """Return the average number of attempts per call."""
        if self.calls == 0:
            return 0.0
        return self.total_attempts / self.calls

    @property
    def success_rate(self) -> float:
        """Return the success rate between 0 and 1."""
        if self.calls == 0:
            return 0.0
        return self.successes / self.calls

    @property
    def failure_rate(self) -> float:
        """Return the failure rate between 0 and 1."""
        if self.calls == 0:
            return 0.0
        return self.failures / self.calls

    def to_dict(self) -> dict[str, float | int]:
        """Return this snapshot as a plain dictionary."""
        return {
            "calls": self.calls,
            "successes": self.successes,
            "failures": self.failures,
            "exhausted": self.exhausted,
            "total_attempts": self.total_attempts,
            "total_time": self.total_time,
            "average_attempts": self.average_attempts,
            "success_rate": self.success_rate,
            "failure_rate": self.failure_rate,
        }


class RetryStats:
    """
    Mutable retry statistics attached to decorated functions.

    This class uses a lock so basic counters remain safe when the same decorated
    function is called from multiple threads.
    """

    def __init__(self) -> None:
        self._lock = Lock()
        self._calls = 0
        self._successes = 0
        self._failures = 0
        self._exhausted = 0
        self._total_attempts = 0
        self._total_time = 0.0

    def record(self, result: RetryResult[Any]) -> None:
        """Record one finished RetryResult."""
        with self._lock:
            self._calls += 1
            self._total_attempts += result.attempt_count
            self._total_time += result.total_time

            if result.succeeded:
                self._successes += 1
            else:
                self._failures += 1

            if result.exhausted:
                self._exhausted += 1

    def snapshot(self) -> RetryStatsSnapshot:
        """Return an immutable snapshot of current counters."""
        with self._lock:
            return RetryStatsSnapshot(
                calls=self._calls,
                successes=self._successes,
                failures=self._failures,
                exhausted=self._exhausted,
                total_attempts=self._total_attempts,
                total_time=self._total_time,
            )

    def reset(self) -> None:
        """Reset all counters to zero."""
        with self._lock:
            self._calls = 0
            self._successes = 0
            self._failures = 0
            self._exhausted = 0
            self._total_attempts = 0
            self._total_time = 0.0

    def to_dict(self) -> dict[str, float | int]:
        """Return current statistics as a plain dictionary."""
        return self.snapshot().to_dict()
