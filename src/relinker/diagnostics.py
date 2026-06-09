"""
Policy diagnostics and simulation.

Diagnostics are advisory. Relinker does not block application-level decisions,
but it can help users understand risky or surprising retry configurations.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Literal

Severity = Literal["advisory", "warning", "critical"]


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
    severity: Severity = "warning"

    def to_dict(self) -> dict[str, str | None]:
        """Return this warning as a JSON-friendly dictionary."""
        return {
            "code": self.code,
            "message": self.message,
            "hint": self.hint,
            "severity": self.severity,
        }


@dataclass(frozen=True, slots=True)
class PolicyHealthReport:
    """
    Human-friendly health report for a retry policy.

    The report does not block execution. It groups the advisory warnings into a
    small risk level so users can decide whether a policy is ready for production.
    """

    warnings: tuple[PolicyWarning, ...]
    complete: bool = True
    skipped_checks: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        """Return True when the report is complete and has no warnings."""
        return self.complete and not self.warnings

    @property
    def has_warnings(self) -> bool:
        """Return True when the policy has at least one warning."""
        return bool(self.warnings)

    @property
    def has_critical(self) -> bool:
        """Return True when at least one warning has critical severity."""
        return any(w.severity == "critical" for w in self.warnings)

    @property
    def critical_count(self) -> int:
        """Return the number of warnings with critical severity."""
        return sum(1 for w in self.warnings if w.severity == "critical")

    @property
    def risk_level(self) -> Literal["ok", "warning", "risky"]:
        """Return a compact risk level derived from warning severity and completeness."""
        if self.has_critical:
            return "risky"
        if self.warnings or not self.complete:
            return "warning"
        return "ok"

    def to_dict(self) -> dict[str, object]:
        """Return this report as a JSON-friendly dictionary."""
        return {
            "ok": self.ok,
            "risk_level": self.risk_level,
            "warning_count": len(self.warnings),
            "warnings": [warning.to_dict() for warning in self.warnings],
            "complete": self.complete,
            "skipped_checks": list(self.skipped_checks),
        }

    def to_json(self, indent: int | None = None) -> str:
        """Return this report as JSON."""
        return json.dumps(self.to_dict(), indent=indent)

    def describe(self) -> str:
        """Return a readable policy health report."""
        lines = ["Relinker policy health", "", f"Risk level: {self.risk_level}"]
        if not self.warnings:
            lines.extend(["", "No warnings found."])
        else:
            lines.extend(["", "Warnings:"])
            for warning in self.warnings:
                lines.append(f"- {warning.code}: {warning.message}")
                if warning.hint:
                    lines.append(f"  Hint: {warning.hint}")

        if not self.complete:
            lines.extend(["", "Diagnostics complete: no", "Skipped checks:"])
            for check in self.skipped_checks:
                lines.append(f"- {check}")

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
            "Relinker simulation",
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


@dataclass(frozen=True, slots=True)
class RetryLoadEstimate:
    """Worst-case estimate of calls produced by concurrent retry executions."""

    concurrent_executions: int
    maximum_attempts_per_execution: int | None
    original_calls: int
    maximum_additional_retries: int | None
    maximum_total_calls: int | None
    unbounded: bool
    retry_budget_configured: bool
    retry_budget_capacity: int | None
    retry_budget_period: float | None
    partial: bool = False

    def to_dict(self) -> dict[str, object]:
        """Return this estimate as a JSON-friendly dictionary."""
        return {
            "concurrent_executions": self.concurrent_executions,
            "maximum_attempts_per_execution": self.maximum_attempts_per_execution,
            "original_calls": self.original_calls,
            "maximum_additional_retries": self.maximum_additional_retries,
            "maximum_total_calls": self.maximum_total_calls,
            "unbounded": self.unbounded,
            "retry_budget_configured": self.retry_budget_configured,
            "retry_budget_capacity": self.retry_budget_capacity,
            "retry_budget_period": self.retry_budget_period,
            "partial": self.partial,
        }

    def describe(self) -> str:
        """Return a readable load estimate."""
        lines = [
            "Relinker load worst-case estimate",
            "",
            f"Concurrent executions: {self.concurrent_executions}",
            f"Original calls: {self.original_calls}",
        ]
        if self.unbounded:
            lines.append("Maximum total calls: unbounded")
        elif self.partial:
            lines.append("Maximum total calls: unknown (partial estimate)")
        else:
            lines.extend(
                [
                    f"Maximum attempts per execution: {self.maximum_attempts_per_execution}",
                    f"Maximum additional retries: {self.maximum_additional_retries}",
                    f"Maximum total calls: {self.maximum_total_calls}",
                ]
            )
        if self.retry_budget_configured:
            lines.append(
                "Retry Budget configured: "
                f"{self.retry_budget_capacity} retries per {self.retry_budget_period:g} seconds"
            )
        return "\n".join(lines)
