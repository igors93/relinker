"""
Policy diagnostics implementation.

Contains the warnings() and doctor() logic extracted from RetryPolicy. This is
internal; the public API remains RetryPolicy.warnings() and RetryPolicy.doctor().
"""

from __future__ import annotations

from typing import Any

from relinker.conditions.composite import AllCondition, AnyCondition
from relinker.conditions.result import ResultCondition
from relinker.delays.composite import AdditiveDelay
from relinker.delays.exponential import ExponentialDelay
from relinker.delays.fixed import FixedDelay
from relinker.delays.linear import LinearDelay
from relinker.delays.random_delay import RandomDelay
from relinker.delays.random_exponential import RandomExponentialDelay
from relinker.diagnostics import PolicyHealthReport, PolicyWarning
from relinker.stop.attempts import StopAfterAttempt
from relinker.stop.composite import AllStopStrategy, AnyStopStrategy
from relinker.stop.forever import StopForever
from relinker.stop.max_time import StopAfterDelay


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


def _has_random_delay(strategy: Any) -> bool:
    if isinstance(strategy, (RandomDelay, RandomExponentialDelay)):
        return True
    if isinstance(strategy, AdditiveDelay):
        return any(_has_random_delay(item) for item in strategy.strategies)
    return False


def _has_positive_deterministic_delay(strategy: Any) -> bool:
    if isinstance(strategy, FixedDelay):
        return strategy.seconds > 0
    if isinstance(strategy, LinearDelay):
        maximum = float("inf") if strategy.maximum is None else strategy.maximum
        return maximum > 0 and (strategy.start > 0 or strategy.step > 0)
    if isinstance(strategy, ExponentialDelay):
        maximum = float("inf") if strategy.maximum is None else strategy.maximum
        return maximum > 0 and strategy.base > 0
    if isinstance(strategy, AdditiveDelay):
        return any(_has_positive_deterministic_delay(item) for item in strategy.strategies)
    return False


def _high_attempt_count(policy: Any) -> bool:
    return isinstance(policy.stop_strategy, StopAfterAttempt) and policy.stop_strategy.maximum >= 10


def _is_forever(policy: Any) -> bool:
    return isinstance(policy.stop_strategy, StopForever)


def _has_max_time(strategy: Any) -> bool:
    if isinstance(strategy, StopAfterDelay):
        return True
    if isinstance(strategy, (AnyStopStrategy, AllStopStrategy)):
        return any(_has_max_time(item) for item in strategy.strategies)
    return False


def _has_giveup_observer(policy: Any) -> bool:
    return any(name == "after_giveup" for name, _handler in policy.event_handlers)


def compute_warnings(policy: Any) -> tuple[PolicyWarning, ...]:
    """
    Compute advisory warnings for the given policy.

    Accepts Any to avoid a circular import; the caller is always RetryPolicy.
    """
    warnings: list[PolicyWarning] = []

    condition_name = policy.condition.__class__.__name__

    is_forever = _is_forever(policy)
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

    if (
        _high_attempt_count(policy)
        and _has_positive_deterministic_delay(policy.delay_strategy)
        and not _has_random_delay(policy.delay_strategy)
    ):
        warnings.append(
            PolicyWarning(
                code="missing_jitter",
                message="This policy may synchronize retries across concurrent executions.",
                hint="Consider adding jitter.",
            )
        )

    if (is_forever or _high_attempt_count(policy)) and policy.retry_budget is None:
        warnings.append(
            PolicyWarning(
                code="missing_retry_budget",
                message=(
                    "Under high concurrency, this policy may multiply load on a degraded service."
                ),
                hint="Consider a Retry Budget.",
            )
        )

    if (
        policy.exhausted_callback is not None
        and not _has_giveup_observer(policy)
        and not policy.should_return_result
    ):
        warnings.append(
            PolicyWarning(
                code="silent_fallback",
                message=(
                    "The fallback may hide repeated failures because no give-up observer "
                    "is configured."
                ),
                hint="Add on_giveup(), logging, or return_result() when you need visibility.",
            )
        )

    if is_forever and policy.retry_budget is not None:
        warnings.append(
            PolicyWarning(
                code="infinite_retry_with_budget",
                message=(
                    "Retry Budget controls retry rate, but does not limit total operation duration."
                ),
                hint="Add a time or attempt limit if the operation must eventually stop.",
            )
        )

    if getattr(policy, "testing_mode", False) and _has_max_time(policy.stop_strategy):
        warnings.append(
            PolicyWarning(
                code="for_testing_with_max_time",
                message="for_testing() removes real sleeps but does not advance time.",
                hint="max_time() behavior may differ from production.",
            )
        )

    is_high_attempt = _high_attempt_count(policy)
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
