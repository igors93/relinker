"""
Policy simulation and explanation implementation.

Implements simulate(), preview(), and explain() for RetryPolicy. This is internal;
the public API is RetryPolicy.simulate(), RetryPolicy.timeline(),
RetryPolicy.preview(), and RetryPolicy.explain().
"""

from __future__ import annotations

from typing import Any

from relinker.diagnostics import RetrySimulation, RetrySimulationAttempt
from relinker.exceptions import InvalidRetryConfigError


def _format_seconds(value: float | None) -> str:
    if value is None:
        return "unlimited"
    if value == int(value):
        return f"{int(value)}s"
    return f"{value:g}s"


def _class_name(value: object) -> str:
    return value.__class__.__name__


def _safe_next_delay(policy: Any, attempt_number: int) -> float:
    """Return next delay without executing user-provided callbacks.

    Raises InvalidRetryConfigError for custom or stateful delay strategies so
    that simulate() and warnings() never cause application side effects.
    """
    name = _class_name(policy.delay_strategy)
    if name in {"CustomDelay", "StatefulCustomDelay"}:
        raise InvalidRetryConfigError(
            "Simulation is not supported for policies with custom delay callbacks"
        )
    return policy.delay_strategy.next_delay(attempt_number)


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
        if not should_stop:
            delay = _safe_next_delay(policy, attempt_number)
            if policy.stop_strategy.should_stop(attempt_number, elapsed + delay):
                should_stop = True
                delay = 0.0
        else:
            delay = 0.0
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


def _describe_stop(policy: Any) -> str:
    strategy = policy.stop_strategy
    name = _class_name(strategy)
    if name == "StopAfterAttempt":
        return f"try up to {strategy.maximum} times"
    if name == "StopAfterDelay":
        return f"keep trying until {_format_seconds(strategy.seconds)} has elapsed"
    if name == "StopForever":
        return "keep trying until the caller stops it"
    if name in {"AnyStopStrategy", "AllStopStrategy"}:
        mode = "any" if name == "AnyStopStrategy" else "all"
        return f"stop using a composed strategy ({mode} stop conditions)"
    return f"stop using {name}"


def _describe_condition(policy: Any) -> str:
    condition = policy.condition
    name = _class_name(condition)
    if name == "ExceptionCondition":
        exception_types = getattr(condition, "exception_types", ())
        labels = ", ".join(t.__name__ for t in exception_types) or "configured exceptions"
        return f"retry on {labels}"
    if name == "ResultCondition":
        return "retry when a returned value is rejected by the configured predicate"
    if name == "CustomCondition":
        return "retry using a custom condition callback"
    if name == "AnyCondition":
        return "retry when any configured condition matches"
    if name == "AllCondition":
        return "retry only when all configured conditions match"
    return f"retry using {name}"


def _describe_delay(policy: Any) -> str:
    delay = policy.delay_strategy
    name = _class_name(delay)
    if name == "FixedDelay":
        return f"wait {_format_seconds(delay.seconds)} between attempts"
    if name == "LinearDelay":
        maximum = getattr(delay, "maximum", None)
        capped = f", capped at {_format_seconds(maximum)}" if maximum is not None else ""
        return f"wait with linear delay starting at {_format_seconds(delay.start)}{capped}"
    if name == "ExponentialDelay":
        maximum = getattr(delay, "maximum", None)
        capped = f", capped at {_format_seconds(maximum)}" if maximum is not None else ""
        return f"wait with exponential backoff from {_format_seconds(delay.base)}{capped}"
    if name == "RandomDelay":
        return (
            "wait using a random delay between "
            f"{_format_seconds(delay.minimum)} and {_format_seconds(delay.maximum)}"
        )
    if name == "RandomExponentialDelay":
        maximum = getattr(delay, "maximum", None)
        capped = f", capped at {_format_seconds(maximum)}" if maximum is not None else ""
        return (
            f"wait using randomized exponential backoff from {_format_seconds(delay.base)}{capped}"
        )
    if name == "ChainDelay":
        return "wait using a predefined delay chain"
    if name == "AdditiveDelay":
        return "wait using composed delay strategies"
    if name == "StatefulCustomDelay":
        return "wait using a state-aware delay callback"
    if name == "CustomDelay":
        return "wait using a custom delay callback"
    return f"wait using {name}"


def _describe_exhaustion(policy: Any) -> str:
    if policy.should_return_result:
        return "return a RetryResult object instead of raising or returning the raw value"
    if policy.exhausted_callback is not None:
        return "call a fallback when retry attempts are exhausted"
    if policy.exhausted_exception_factory is not None:
        return "raise a custom exception when retry attempts are exhausted"
    if policy.should_raise_last:
        return "raise the last exception when retry attempts are exhausted"
    return "return None when an unaccepted exception is not re-raised"


def explain_policy(policy: Any) -> str:
    """Return a human-readable explanation of the policy including warnings."""
    lines = [
        "Relinker policy",
        "",
        "This policy will:",
        f"- {_describe_stop(policy)}",
        f"- {_describe_condition(policy)}",
        f"- {_describe_delay(policy)}",
        f"- {_describe_exhaustion(policy)}",
    ]

    lines.extend(
        [
            "",
            "Technical details:",
            f"- Stop strategy: {_class_name(policy.stop_strategy)}",
            f"- Delay strategy: {_class_name(policy.delay_strategy)}",
            f"- Condition: {_class_name(policy.condition)}",
        ]
    )

    policy_warnings = policy.warnings()
    if policy_warnings:
        lines.extend(["", "Warnings:"])
        for warning in policy_warnings:
            lines.append(f"- {warning.code}: {warning.message}")
            if warning.hint:
                lines.append(f"  Hint: {warning.hint}")

    return "\n".join(lines)


def preview_policy(policy: Any, attempts: int = 5) -> str:
    """Return a concise preview of the delay timeline and warnings."""
    simulation = simulate_policy(policy, attempts)
    lines = [
        "Relinker preview",
        "",
        f"Attempts previewed: {simulation.attempt_count}",
        f"Estimated total sleep: {simulation.total_sleep:.4f}s",
        "",
        "Timeline:",
    ]

    for attempt in simulation.attempts:
        marker = " -> stop" if attempt.stops_after_attempt else ""
        lines.append(
            f"- Attempt {attempt.attempt_number}: "
            f"wait {attempt.delay_before_next_attempt:.4f}s{marker}"
        )

    warnings = policy.warnings()
    if warnings:
        lines.extend(["", "Warnings:"])
        for warning in warnings:
            lines.append(f"- {warning.code}: {warning.message}")

    return "\n".join(lines)
