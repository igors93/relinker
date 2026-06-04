"""
Policy diagnostics implementation.

Contains the warnings() and doctor() logic extracted from RetryPolicy. This is
internal; the public API remains RetryPolicy.warnings() and RetryPolicy.doctor().
"""

from __future__ import annotations

from typing import Any

from retryflow.conditions.composite import AllCondition, AnyCondition
from retryflow.conditions.result import ResultCondition
from retryflow.diagnostics import PolicyHealthReport, PolicyWarning
from retryflow.stop.attempts import StopAfterAttempt


def _has_result_condition(condition: Any) -> bool:
    """Return True when the condition tree includes at least one ResultCondition."""
    if isinstance(condition, ResultCondition):
        return True
    if isinstance(condition, (AnyCondition, AllCondition)):
        return any(_has_result_condition(c) for c in condition.conditions)
    return False


def _is_no_delay(policy: Any) -> bool:
    return (
        policy.delay_strategy.__class__.__name__ == "FixedDelay"
        and getattr(policy.delay_strategy, "seconds", None) == 0
    )


def compute_warnings(policy: Any) -> tuple[PolicyWarning, ...]:
    """
    Compute advisory warnings for the given policy.

    Accepts Any to avoid a circular import; the caller is always RetryPolicy.
    """
    warnings: list[PolicyWarning] = []

    stop_name = policy.stop_strategy.__class__.__name__
    condition_name = policy.condition.__class__.__name__

    is_forever = stop_name == "StopForever"
    is_no_delay = _is_no_delay(policy)

    if is_forever:
        warnings.append(
            PolicyWarning(
                code="forever",
                message="This policy can retry forever.",
                hint="Use forever() only when the caller controls cancellation or shutdown.",
            )
        )

    if is_no_delay:
        warnings.append(
            PolicyWarning(
                code="no_delay",
                message="This policy has no delay between attempts.",
                hint="Consider jitter or backoff for external services.",
            )
        )

    if is_forever and is_no_delay:
        warnings.append(
            PolicyWarning(
                code="tight_loop_risk",
                message="This policy can retry forever without sleeping.",
                hint=(
                    "A tight retry loop can consume CPU and overload downstream services. "
                    "Add a delay, max_time(), or a cancellation-aware caller."
                ),
            )
        )

    is_broad_exception = False
    if condition_name == "ExceptionCondition":
        exception_types = getattr(policy.condition, "exception_types", ())
        if exception_types == (Exception,):
            is_broad_exception = True
            warnings.append(
                PolicyWarning(
                    code="broad_exception",
                    message="This policy retries all Exception subclasses.",
                    hint="Prefer specific exception types when possible.",
                )
            )

    if isinstance(policy.stop_strategy, StopAfterAttempt) and policy.stop_strategy.maximum > 10:
        warnings.append(
            PolicyWarning(
                code="many_attempts",
                message=f"This policy uses {policy.stop_strategy.maximum} attempts.",
                hint="High attempt counts increase load on downstream services during incidents.",
            )
        )

    if not is_forever:
        try:
            sim_count = (
                policy.stop_strategy.maximum
                if isinstance(policy.stop_strategy, StopAfterAttempt)
                else 10
            )
            simulation = policy.simulate(attempts=sim_count)
            if simulation.total_sleep > 300:
                warnings.append(
                    PolicyWarning(
                        code="high_total_sleep",
                        message=(
                            f"Simulated total sleep is {simulation.total_sleep:.1f}s "
                            f"across {sim_count} attempts."
                        ),
                        hint=(
                            "Verify that upstream services and callers can wait this long "
                            "before adding a stricter time limit."
                        ),
                    )
                )
        except Exception:  # noqa: BLE001
            pass

    if policy.should_return_result and (
        policy.exhausted_callback is not None or policy.exhausted_exception_factory is not None
    ):
        warnings.append(
            PolicyWarning(
                code="return_result_precedence",
                message="return_result() takes precedence over fallback and exhausted errors.",
                hint=(
                    "Configure fallback/on_exhausted_raise after deciding "
                    "whether to return RetryResult."
                ),
            )
        )

    if (
        _has_result_condition(policy.condition)
        and not policy.should_return_result
        and policy.exhausted_callback is None
        and policy.exhausted_exception_factory is None
        and policy.result_exhausted_behavior != "raise"
    ):
        warnings.append(
            PolicyWarning(
                code="result_retry_without_observation",
                message=(
                    "Result-based retry is configured without return_result(), "
                    "fallback, or raise-on-exhausted behavior."
                ),
                hint=(
                    "Add .return_result(), .fallback(...), or "
                    ".raise_on_result_exhausted() to observe when "
                    "result retry is exhausted."
                ),
            )
        )

    is_high_attempt = (
        isinstance(policy.stop_strategy, StopAfterAttempt) and policy.stop_strategy.maximum >= 10
    )
    if is_broad_exception and (is_forever or is_high_attempt):
        warnings.append(
            PolicyWarning(
                code="background_broad_exception",
                message="Broad exception handling is combined with many attempts or forever retry.",
                hint=(
                    "Background jobs catching all exceptions can mask bugs and amplify load. "
                    "Consider narrowing the exception types or adding a circuit breaker."
                ),
            )
        )

    return tuple(warnings)


def doctor_policy(policy: Any) -> PolicyHealthReport:
    """Return a human-friendly policy health report."""
    return PolicyHealthReport(compute_warnings(policy))
