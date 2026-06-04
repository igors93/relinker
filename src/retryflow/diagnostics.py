"""
Policy diagnostics and simulation.

Diagnostics are advisory. RetryFlow does not block application-level decisions,
but it can help users understand risky or surprising retry configurations.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Literal


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

    def to_dict(self) -> dict[str, str | None]:
        """Return this warning as a JSON-friendly dictionary."""
        return {"code": self.code, "message": self.message, "hint": self.hint}


@dataclass(frozen=True, slots=True)
class PolicyHealthReport:
    """
    Human-friendly health report for a retry policy.

    The report does not block execution. It groups the advisory warnings into a
    small risk level so users can decide whether a policy is ready for production.
    """

    warnings: tuple[PolicyWarning, ...]

    @property
    def ok(self) -> bool:
        """Return True when the policy has no warnings."""
        return not self.warnings

    @property
    def has_warnings(self) -> bool:
        """Return True when the policy has at least one warning."""
        return bool(self.warnings)

    @property
    def risk_level(self) -> Literal["ok", "warning", "risky"]:
        """Return a compact risk level derived from warning codes."""
        risky_codes = {
            "forever",
            "tight_loop_risk",
            "background_broad_exception",
        }
        if any(warning.code in risky_codes for warning in self.warnings):
            return "risky"
        if self.warnings:
            return "warning"
        return "ok"

    def to_dict(self) -> dict[str, object]:
        """Return this report as a JSON-friendly dictionary."""
        return {
            "ok": self.ok,
            "risk_level": self.risk_level,
            "warning_count": len(self.warnings),
            "warnings": [warning.to_dict() for warning in self.warnings],
        }

    def to_json(self, indent: int | None = None) -> str:
        """Return this report as JSON."""
        return json.dumps(self.to_dict(), indent=indent)

    def describe(self) -> str:
        """Return a readable policy health report."""
        lines = ["RetryFlow policy health", "", f"Risk level: {self.risk_level}"]
        if not self.warnings:
            lines.extend(["", "No warnings found."])
            return "\n".join(lines)

        lines.extend(["", "Warnings:"])
        for warning in self.warnings:
            lines.append(f"- {warning.code}: {warning.message}")
            if warning.hint:
                lines.append(f"  Hint: {warning.hint}")
        return "\n".join(lines)


@dataclass(frozen=True, slots=True)
class RetrySimulationAttempt:
    """One simulated retry attempt."""

    attempt_number: int
    delay_before_next_attempt: float
    stops_after_attempt: bool
    cumulative_sleep: float = 0.0


@dataclass(frozen=True, slots=True)
class RetrySimulation:
    """
    Simulation of a retry policy delay timeline.

    The simulation does not call user code. It only estimates the delay behavior
    of the configured policy.
    """

    attempts: tuple[RetrySimulationAttempt, ...]

    @property
    def attempt_count(self) -> int:
        """Return the number of simulated attempts."""
        return len(self.attempts)

    @property
    def total_sleep(self) -> float:
        """Return the total simulated sleep time."""
        return sum(attempt.delay_before_next_attempt for attempt in self.attempts)

    @property
    def max_delay(self) -> float:
        """Return the largest single delay across all simulated attempts."""
        if not self.attempts:
            return 0.0
        return max(attempt.delay_before_next_attempt for attempt in self.attempts)

    @property
    def stops_early(self) -> bool:
        """Return True if any attempt triggers an early stop."""
        return any(attempt.stops_after_attempt for attempt in self.attempts)

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-friendly representation."""
        return {
            "attempt_count": self.attempt_count,
            "total_sleep": self.total_sleep,
            "max_delay": self.max_delay,
            "stops_early": self.stops_early,
            "attempts": [
                {
                    "attempt_number": attempt.attempt_number,
                    "delay_before_next_attempt": attempt.delay_before_next_attempt,
                    "cumulative_sleep": attempt.cumulative_sleep,
                    "stops_after_attempt": attempt.stops_after_attempt,
                }
                for attempt in self.attempts
            ],
        }

    def to_json(self, indent: int | None = None) -> str:
        """Return this simulation as JSON."""
        return json.dumps(self.to_dict(), indent=indent)

    def describe(self) -> str:
        """Return a readable simulation report."""
        lines = [
            "RetryFlow simulation",
            "",
            f"Attempts simulated: {self.attempt_count}",
            f"Total simulated sleep: {self.total_sleep:.4f}s",
            f"Max single delay: {self.max_delay:.4f}s",
            "",
        ]
        for attempt in self.attempts:
            stop_marker = " [stop]" if attempt.stops_after_attempt else ""
            lines.append(
                f"Attempt {attempt.attempt_number}: "
                f"wait {attempt.delay_before_next_attempt:.4f}s "
                f"(cumulative: {attempt.cumulative_sleep:.4f}s)"
                f"{stop_marker}"
            )
        return "\n".join(lines)
