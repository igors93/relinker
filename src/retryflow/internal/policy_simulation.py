"""
Policy simulation implementation.

Implements simulate() and explain() for RetryPolicy. This is internal;
the public API is RetryPolicy.simulate(), RetryPolicy.timeline(), and
RetryPolicy.explain().
"""

from __future__ import annotations

from typing import Any

from retryflow.diagnostics import RetrySimulation, RetrySimulationAttempt
from retryflow.exceptions import InvalidRetryConfigError


def simulate_policy(policy: Any, attempts: int) -> RetrySimulation:
    """
    Compute the delay timeline for a policy without executing user code.

    Accepts Any to avoid a circular import; the caller is always RetryPolicy.
    """
    if attempts <= 0:
        raise InvalidRetryConfigError("attempts must be greater than zero")

    simulated_attempts: list[RetrySimulationAttempt] = []
    elapsed = 0.0
    cumulative = 0.0

    for attempt_number in range(1, attempts + 1):
        should_stop = policy.stop_strategy.should_stop(attempt_number, elapsed)
        delay = 0.0 if should_stop else policy.delay_strategy.next_delay(attempt_number)
        cumulative += delay
        simulated_attempts.append(
            RetrySimulationAttempt(
                attempt_number=attempt_number,
                delay_before_next_attempt=delay,
                stops_after_attempt=should_stop,
                cumulative_sleep=cumulative,
            )
        )
        elapsed += delay
        if should_stop:
            break

    return RetrySimulation(tuple(simulated_attempts))


def explain_policy(policy: Any) -> str:
    """
    Return a human-readable explanation of the policy including warnings.

    Accepts Any to avoid a circular import; the caller is always RetryPolicy.
    """
    lines = [
        "RetryFlow policy",
        "",
        f"Stop strategy: {policy.stop_strategy.__class__.__name__}",
        f"Delay strategy: {policy.delay_strategy.__class__.__name__}",
        f"Condition: {policy.condition.__class__.__name__}",
        f"Raise last exception: {policy.should_raise_last}",
        f"Return RetryResult: {policy.should_return_result}",
        f"Result exhausted behavior: {policy.result_exhausted_behavior}",
        f"Has exhausted callback: {policy.exhausted_callback is not None}",
        f"Has exhausted exception factory: {policy.exhausted_exception_factory is not None}",
        f"Event handlers: {len(policy.event_handlers)}",
    ]

    policy_warnings = policy.warnings()
    if policy_warnings:
        lines.extend(["", "Warnings:"])
        for warning in policy_warnings:
            lines.append(f"- {warning.code}: {warning.message}")

    return "\n".join(lines)
