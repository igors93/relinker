"""Synchronous retry executor."""

from __future__ import annotations

import inspect
from typing import TYPE_CHECKING, Any

from relinker.exceptions import InvalidRetryConfigError
from relinker.internal.executor_flow import FinalDecision, RetryFlow
from relinker.internal.executor_helpers import function_name as _function_name
from relinker.internal.exhaustion import finish_exhausted
from relinker.internal.retry_wait import RetryWaitPlan, release_retry_wait

if TYPE_CHECKING:
    from collections.abc import Callable

    from relinker.policy import RetryPolicy


def _invoke_sync_sleep(sleep_fn: Any, seconds: float) -> None:
    """Call the sync sleeper and close any accidentally created coroutine."""
    result = sleep_fn(seconds)
    if inspect.iscoroutine(result):
        result.close()
        raise InvalidRetryConfigError(
            "sync sleep returned a coroutine; "
            "pass an async sleep function as the second argument to with_sleep()"
        )


def sleep_before_retry(policy: RetryPolicy[Any], plan: RetryWaitPlan) -> None:
    """Sleep for ``plan`` and release its budget reservation if sleeping fails."""
    try:
        _invoke_sync_sleep(policy.sleep, plan.total_delay)
    except BaseException:
        release_retry_wait(plan)
        raise


def execute_sync(
    policy: RetryPolicy[Any],
    function: Callable[..., Any],
    *args: Any,
    **kwargs: Any,
) -> Any:
    """Execute a synchronous function using a ``RetryPolicy``."""
    flow = RetryFlow(policy, function_name=_function_name(function))

    while True:
        flow.next_attempt()
        flow.enter_attempt()
        decision: RetryWaitPlan | FinalDecision

        try:
            value = function(*args, **kwargs)
        except Exception as error:
            decision = flow.after_exception(error)
        else:
            decision = flow.after_value(value)

        if isinstance(decision, RetryWaitPlan):
            sleep_before_retry(policy, decision)
            continue

        result = decision.result
        if decision.kind == "exhaust":
            return finish_exhausted(policy, result)
        if policy.should_return_result:
            return result
        if decision.kind == "reject" and result.error is not None:
            raise result.error
        return result.value
