"""
Exhausted retry behavior.

When the stop strategy fires while the condition would still retry, the
execution is exhausted. This module applies whatever final behavior the
policy configures (fallback, raise, return result, etc.).

Used by both executors and the decorator wrapper.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from relinker.exceptions import RetryExhaustedError

if TYPE_CHECKING:
    from relinker.policy import RetryPolicy
    from relinker.result import RetryResult


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
        raise policy.exhausted_exception_factory(result)

    if result.error is not None and policy.should_raise_last:
        raise result.error

    if result.exhausted_by_result and policy.result_exhausted_behavior == "raise":
        raise RetryExhaustedError(
            "Retry attempts were exhausted by rejected return values.",
            result=result,
        )

    return result.value


def resolve_tracked_result(policy: RetryPolicy[Any], result: RetryResult[Any]) -> Any:
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
        if policy.should_raise_last:
            raise result.error
        return None

    return result.value
