"""Asynchronous retry executor."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from relinker.internal.callables import ensure_awaitable_result, ensure_awaitable_sleep_result
from relinker.internal.executor_flow import FinalDecision, RetryFlow
from relinker.internal.executor_helpers import function_name as _function_name
from relinker.internal.exhaustion import finish_exhausted
from relinker.internal.retry_wait import RetryWaitPlan, release_retry_wait

if TYPE_CHECKING:
    from collections.abc import Callable

    from relinker.policy import RetryPolicy


async def async_sleep_before_retry(policy: RetryPolicy[Any], plan: RetryWaitPlan) -> None:
    """Await the async sleeper for ``plan`` and release its reservation on failure."""
    try:
        await ensure_awaitable_sleep_result(policy.async_sleep(plan.total_delay), plan.total_delay)
    except BaseException:
        release_retry_wait(plan)
        raise


async def execute_async(
    policy: RetryPolicy[Any],
    function: Callable[..., Any],
    *args: Any,
    **kwargs: Any,
) -> Any:
    """Execute an asynchronous function using a ``RetryPolicy``."""
    flow = RetryFlow(policy, function_name=_function_name(function))

    while True:
        flow.next_attempt()
        flow.enter_attempt()
        decision: RetryWaitPlan | FinalDecision

        try:
            candidate = function(*args, **kwargs)
        except Exception as error:
            decision = flow.after_exception(error)
        else:
            # Outside the try: a non-awaitable return value is a contract error,
            # never a retryable failure.
            awaitable = ensure_awaitable_result(candidate)
            try:
                value = await awaitable
            except Exception as error:
                decision = flow.after_exception(error)
            else:
                decision = flow.after_value(value)

        if isinstance(decision, RetryWaitPlan):
            await async_sleep_before_retry(policy, decision)
            continue

        result = decision.result
        if decision.kind == "exhaust":
            return finish_exhausted(policy, result)
        if policy.should_return_result:
            return result
        if decision.kind == "reject" and result.error is not None:
            raise result.error
        return result.value
