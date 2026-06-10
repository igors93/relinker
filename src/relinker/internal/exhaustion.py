"""
Exhausted retry behavior.

When the stop strategy fires while the condition would still retry, the
execution is exhausted. This module applies whatever final behavior the
policy configures (fallback, raise, return result, etc.).

Used by executors, context managers, and the decorator wrapper.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from relinker.exceptions import InvalidRetryConfigError, RetryExhaustedError, TryAgain

if TYPE_CHECKING:
    from relinker.policy import RetryPolicy
    from relinker.result import RetryResult
    from relinker.stop.base import StopStrategy


def should_stop_before_sleep(
    stop_strategy: StopStrategy,
    attempt_number: int,
    elapsed: float,
    delay: float,
) -> bool:
    """Return True when sleeping for delay would exceed the stop strategy budget.

    This prevents a sleep that is longer than the remaining time budget. It is
    only meaningful for time-based stop strategies; attempt-only strategies will
    not trigger early because they do not depend on elapsed time.
    """
    return stop_strategy.should_stop(attempt_number, elapsed + delay)


def resolve_final_error(error: BaseException | None) -> BaseException | None:
    """Return the operational final error represented by a retry signal."""
    if not isinstance(error, TryAgain):
        return error

    cause = error.__cause__
    if isinstance(cause, Exception) and not isinstance(cause, TryAgain):
        return cause

    context = error.__context__
    if (
        context is not None
        and not error.__suppress_context__
        and isinstance(context, Exception)
        and not isinstance(context, TryAgain)
    ):
        return context

    return error


def finish_exhausted(policy: RetryPolicy[Any], result: RetryResult[Any]) -> Any:
    """
    Apply the final exhausted behavior configured by the policy.

    Called by executors when the stop strategy fires while the condition
    would still retry. Applies return_result, fallback, raise, or default
    behaviors in the correct precedence order.
    """
    if policy.should_return_result:
        return result

    if policy.exhausted_callback is not None:
        return policy.exhausted_callback(result)

    if policy.exhausted_exception_factory is not None:
        exception = policy.exhausted_exception_factory(result)
        if not isinstance(exception, BaseException):
            raise InvalidRetryConfigError("exception factory must return a BaseException instance")
        raise exception

    if result.error is not None and policy.should_raise_last:
        raise result.error

    if result.exhausted_by_result and policy.result_exhausted_behavior == "raise":
        raise RetryExhaustedError(
            "Retry attempts were exhausted by rejected return values.",
            result=result,
        )

    return result.value


def resolve_tracked_result(
    policy: RetryPolicy[Any],
    result: RetryResult[Any],
) -> Any:
    """
    Convert a tracked RetryResult to the behavior configured by the policy.

    Decorated functions always run in return_result() mode so statistics can
    be collected. This function re-applies the original policy's behavior to
    that result.
    """
    if policy.should_return_result:
        return result

    if result.exhausted:
        return finish_exhausted(policy, result)

    if result.error is not None:
        raise result.error

    return result.value
