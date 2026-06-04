"""
Policy diagnostics and simulation.

Diagnostics are advisory. RetryFlow does not block application-level decisions,
but it can help users understand risky or surprising retry configurations.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PolicyWarning:
    """
    Advisory warning about a retry policy.

    Warnings are intentionally non-blocking. They exist to help users reason
    about behavior before deploying a policy.
    """

    code: str
    message: str
    hint: str | None = None


@dataclass(frozen=True, slots=True)
class RetrySimulationAttempt:
    """One simulated retry attempt."""

    attempt_number: int
    delay_before_next_attempt: float
    stops_after_attempt: bool


@dataclass(frozen=True, slots=True)
class RetrySimulation:
    """
    Simulation of a retry policy delay timeline.

    The simulation does not call user code. It only estimates the delay behavior
    of the configured policy.
    """

    attempts: tuple[RetrySimulationAttempt, ...]

    @property
    def total_sleep(self) -> float:
        """Return the total simulated sleep time."""
        return sum(attempt.delay_before_next_attempt for attempt in self.attempts)

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-friendly representation."""
        return {
            "total_sleep": self.total_sleep,
            "attempts": [
                {
                    "attempt_number": attempt.attempt_number,
                    "delay_before_next_attempt": attempt.delay_before_next_attempt,
                    "stops_after_attempt": attempt.stops_after_attempt,
                }
                for attempt in self.attempts
            ],
        }

    def describe(self) -> str:
        """Return a readable simulation report."""
        lines = ["RetryFlow simulation", "", f"Total simulated sleep: {self.total_sleep:.4f}s", ""]
        for attempt in self.attempts:
            stop_marker = " stop" if attempt.stops_after_attempt else ""
            lines.append(
                "Attempt "
                f"{attempt.attempt_number}: wait "
                f"{attempt.delay_before_next_attempt:.4f}s before next attempt{stop_marker}"
            )
        return "\n".join(lines)
