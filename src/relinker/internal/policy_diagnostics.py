"""
Policy diagnostics implementation.

Contains the warnings() and doctor() logic extracted from RetryPolicy. This is
internal; the public API remains RetryPolicy.warnings() and RetryPolicy.doctor().
"""

from __future__ import annotations

from typing import Any

from relinker.conditions.composite import AllCondition, AnyCondition
from relinker.conditions.exception import ExceptionCondition
from relinker.conditions.result import ResultCondition
from relinker.delays.chain import ChainDelay
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


def _delay_is_always_zero(strategy: Any) -> bool:
    """Return True when a known delay strategy always produces zero."""
    stack = [strategy]
    while stack:
        current = stack.pop()

        if isinstance(current, AdditiveDelay):
            stack.extend(current.strategies)
            continue

        if isinstance(current, FixedDelay):
            if current.seconds != 0:
                return False
            continue

        if isinstance(current, LinearDelay):
            if not (current.maximum == 0 or (current.start == 0 and current.step == 0)):
                return False
            continue

        if isinstance(current, ExponentialDelay):
            if not (current.base == 0 or current.maximum == 0):
                return False
            continue

        if isinstance(current, ChainDelay):
            if not all(delay == 0 for delay in current.delays):
                return False
            continue

        if isinstance(current, RandomDelay):
            if not (current.minimum == 0 and current.maximum == 0):
                return False
            continue

        if isinstance(current, RandomExponentialDelay):
            if not (current.minimum == 0 and (current.base == 0 or current.maximum == 0)):
                return False
            continue

        return False

    return True


def _is_no_delay(policy: Any) -> bool:
    return _delay_is_always_zero(policy.delay_strategy)


def _uses_implicit_default_policy(policy: Any) -> bool:
    return (
        isinstance(policy.stop_strategy, StopAfterAttempt)
        and policy.stop_strategy.maximum == 3
        and isinstance(policy.delay_strategy, FixedDelay)
        and policy.delay_strategy.seconds == 0
        and isinstance(policy.condition, ExceptionCondition)
        and policy.condition.exception_types == (Exception,)
    )


def _random_exponential_can_vary(
    strategy: RandomExponentialDelay,
    maximum_delay_attempts: int | None,
) -> bool:
    """Return True when a reachable retry can draw from a non-empty range."""
    if maximum_delay_attempts == 0 or strategy.base <= 0:
        return False
    if strategy.maximum is not None and strategy.maximum <= strategy.minimum:
        return False

    if strategy.factor <= 1 or maximum_delay_attempts == 1:
        largest_cap = strategy.base
    elif maximum_delay_attempts is None:
        largest_cap = float("inf")
    else:
        try:
            largest_cap = strategy.base * (strategy.factor ** (maximum_delay_attempts - 1))
        except OverflowError:
            largest_cap = float("inf")

    if strategy.maximum is not None:
        largest_cap = min(largest_cap, strategy.maximum)
    return largest_cap > strategy.minimum


def _has_effective_random_delay(
    strategy: Any,
    *,
    maximum_delay_attempts: int | None,
    seeded: bool | None = None,
) -> bool:
    """Return True when the delay tree has reachable, variable randomness."""
    if maximum_delay_attempts == 0:
        return False

    stack = [strategy]
    while stack:
        current = stack.pop()
        can_vary = False
        current_seed: int | None = None

        if isinstance(current, RandomDelay):
            can_vary = current.maximum > current.minimum
            current_seed = current.seed
        elif isinstance(current, RandomExponentialDelay):
            can_vary = _random_exponential_can_vary(current, maximum_delay_attempts)
            current_seed = current.seed
        elif isinstance(current, AdditiveDelay):
            stack.extend(current.strategies)
            continue

        if can_vary and (seeded is None or (current_seed is not None) is seeded):
            return True

    return False


def _has_positive_deterministic_delay(strategy: Any) -> bool:
    stack = [strategy]
    while stack:
        current = stack.pop()
        if isinstance(current, FixedDelay):
            if current.seconds > 0:
                return True
            continue
        if isinstance(current, LinearDelay):
            maximum = float("inf") if current.maximum is None else current.maximum
            if maximum > 0 and (current.start > 0 or current.step > 0):
                return True
            continue
        if isinstance(current, ExponentialDelay):
            maximum = float("inf") if current.maximum is None else current.maximum
            if maximum > 0 and current.base > 0:
                return True
            continue
        if isinstance(current, AdditiveDelay):
            stack.extend(current.strategies)
    return False


def _stop_is_infinite(strategy: Any) -> bool:
    if isinstance(strategy, StopForever):
        return True
    if isinstance(strategy, (StopAfterAttempt, StopAfterDelay)):
        return False
    if isinstance(strategy, AllStopStrategy):
        return any(_stop_is_infinite(item) for item in strategy.strategies)
    if isinstance(strategy, AnyStopStrategy):
        return all(_stop_is_infinite(item) for item in strategy.strategies)
    return False


def _is_forever(policy: Any) -> bool:
    return _stop_is_infinite(policy.stop_strategy)


def _stops_after_first_attempt(strategy: Any) -> bool:
    """Return True when a known stop strategy guarantees no retry."""
    if isinstance(strategy, StopAfterAttempt):
        return strategy.maximum <= 1
    if isinstance(strategy, StopAfterDelay):
        return strategy.seconds <= 0
    if isinstance(strategy, StopForever):
        return False
    if isinstance(strategy, AnyStopStrategy):
        return any(_stops_after_first_attempt(item) for item in strategy.strategies)
    if isinstance(strategy, AllStopStrategy):
        return all(_stops_after_first_attempt(item) for item in strategy.strategies)
    return False


def _known_attempt_limit(strategy: Any) -> int | None:
    if isinstance(strategy, StopAfterAttempt):
        return strategy.maximum
    if isinstance(strategy, (StopForever, StopAfterDelay)):
        return None
    if isinstance(strategy, AnyStopStrategy):
        limits = [_known_attempt_limit(item) for item in strategy.strategies]
        known = [limit for limit in limits if limit is not None]
        return min(known) if known else None
    if isinstance(strategy, AllStopStrategy):
        if any(_stop_is_infinite(item) for item in strategy.strategies):
            return None
        limits = [_known_attempt_limit(item) for item in strategy.strategies]
        if all(limit is not None for limit in limits):
            return max(limit for limit in limits if limit is not None)
    return None


def _high_attempt_count(policy: Any) -> bool:
    limit = _known_attempt_limit(policy.stop_strategy)
    return limit is not None and limit >= 10


def _many_attempts(policy: Any) -> bool:
    limit = _known_attempt_limit(policy.stop_strategy)
    return limit is not None and limit > 10


def _has_broad_exception(condition: Any) -> bool:
    if isinstance(condition, ExceptionCondition):
        return any(exception_type is Exception for exception_type in condition.exception_types)
    if isinstance(condition, AnyCondition):
        return any(_has_broad_exception(item) for item in condition.conditions)
    if isinstance(condition, AllCondition):
        return all(_has_broad_exception(item) for item in condition.conditions)
    return False


def _has_broad_os_error(condition: Any) -> bool:
    """Return True when the effective condition retries a plain OSError."""
    if isinstance(condition, ExceptionCondition):
        return any(
            exception_type is OSError or exception_type is Exception
            for exception_type in condition.exception_types
        )
    if isinstance(condition, AnyCondition):
        return any(_has_broad_os_error(item) for item in condition.conditions)
    if isinstance(condition, AllCondition):
        return all(_has_broad_os_error(item) for item in condition.conditions)
    return False


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

    is_forever = _is_forever(policy)
    is_no_delay = _is_no_delay(policy)
    known_attempt_limit = _known_attempt_limit(policy.stop_strategy)
    if _stops_after_first_attempt(policy.stop_strategy):
        maximum_delay_attempts = 0
    elif known_attempt_limit is None:
        maximum_delay_attempts = None
    else:
        maximum_delay_attempts = max(0, known_attempt_limit - 1)
    has_effective_random = _has_effective_random_delay(
        policy.delay_strategy,
        maximum_delay_attempts=maximum_delay_attempts,
    )
    has_seeded_random = _has_effective_random_delay(
        policy.delay_strategy,
        maximum_delay_attempts=maximum_delay_attempts,
        seeded=True,
    )
    has_unseeded_random = _has_effective_random_delay(
        policy.delay_strategy,
        maximum_delay_attempts=maximum_delay_attempts,
        seeded=False,
    )

    if _uses_implicit_default_policy(policy):
        warnings.append(
            PolicyWarning(
                code="implicit_default_policy",
                message=(
                    "This policy uses the implicit retry defaults: all Exception subclasses, "
                    "three attempts, and no delay."
                ),
                hint="Specify exception types and a delay explicitly, or use a preset.",
            )
        )

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

    if is_forever and policy.history_limit is None:
        warnings.append(
            PolicyWarning(
                code="unbounded_history",
                message=(
                    "This policy can retry indefinitely while retaining every attempt record."
                ),
                hint=(
                    "Use keep_history(n) to bound memory, or keep unlimited history only "
                    "when the caller guarantees prompt cancellation."
                ),
            )
        )

    is_broad_exception = _has_broad_exception(policy.condition)
    if is_broad_exception:
        warnings.append(
            PolicyWarning(
                code="broad_exception",
                message="This policy retries all Exception subclasses.",
                hint="Prefer specific exception types when possible.",
            )
        )

    elif _has_broad_os_error(policy.condition):
        warnings.append(
            PolicyWarning(
                code="broad_os_error",
                message=(
                    "This policy explicitly retries OSError, which includes "
                    "non-transport operating-system failures."
                ),
                hint=(
                    "Prefer the dependency's documented transient exceptions, or use "
                    "TimeoutError and ConnectionError when appropriate."
                ),
            )
        )

    if _many_attempts(policy):
        attempt_limit = _known_attempt_limit(policy.stop_strategy)
        warnings.append(
            PolicyWarning(
                code="many_attempts",
                message=f"This policy uses {attempt_limit} attempts.",
                hint="High attempt counts increase load on downstream services during incidents.",
            )
        )

    if not is_forever:
        try:
            sim_count = known_attempt_limit if known_attempt_limit is not None else 10
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
        and not has_effective_random
    ):
        warnings.append(
            PolicyWarning(
                code="missing_jitter",
                message="This policy may synchronize retries across concurrent executions.",
                hint="Consider adding jitter.",
            )
        )

    if not getattr(policy, "testing_mode", False) and has_seeded_random and not has_unseeded_random:
        warnings.append(
            PolicyWarning(
                code="seeded_random_delay",
                message=(
                    "This policy uses a seeded random delay, so executions that reuse "
                    "the same seed receive the same per-attempt delays."
                ),
                hint=(
                    "Use seed=None when randomness should spread production retries; "
                    "keep fixed seeds for reproducible tests and simulations."
                ),
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
