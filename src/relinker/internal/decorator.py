"""
Decorator wrapping for RetryPolicy.__call__.

Creates sync and async wrappers that attach retry statistics and the three
standard attributes (retry_stats, retry_policy, with_policy). This is internal;
the public API is the RetryPolicy()(function) call.
"""

from __future__ import annotations

import inspect
from collections.abc import Callable
from functools import wraps
from typing import TYPE_CHECKING, Any, cast

from relinker.internal.exhaustion import resolve_tracked_result
from relinker.stats import RetryStats

if TYPE_CHECKING:
    from relinker.policy import RetryPolicy


def make_decorated(
    policy: RetryPolicy[Any],
    function: Callable[..., Any],
) -> Callable[..., Any]:
    """
    Wrap function with retry logic and attach statistics attributes.

    Returns an async wrapper for coroutine functions, sync wrapper otherwise.
    Both wrappers preserve the original function's __name__, __doc__, and
    other attributes via functools.wraps.
    """
    stats = RetryStats()

    def with_policy(new_policy: RetryPolicy[Any]) -> Callable[..., Any]:
        return new_policy(function)

    if inspect.iscoroutinefunction(function) or inspect.iscoroutinefunction(
        getattr(type(function), "__call__", None)
    ):

        @wraps(function)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            tracking_policy = policy.return_result()
            result = await tracking_policy.run_async(function, *args, **kwargs)
            stats.record(result)
            return resolve_tracked_result(policy, result)

        wrapper_any = cast(Any, async_wrapper)
        wrapper_any.retry_stats = stats
        wrapper_any.retry_policy = policy
        wrapper_any.with_policy = with_policy
        return async_wrapper

    @wraps(function)
    def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
        tracking_policy = policy.return_result()
        result = tracking_policy.run(function, *args, **kwargs)
        stats.record(result)
        return resolve_tracked_result(policy, result)

    wrapper_any = cast(Any, sync_wrapper)
    wrapper_any.retry_stats = stats
    wrapper_any.retry_policy = policy
    wrapper_any.with_policy = with_policy
    return sync_wrapper
