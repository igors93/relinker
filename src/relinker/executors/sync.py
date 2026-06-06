"""Synchronous retry executor."""

from __future__ import annotations

from dataclasses import replace as _dc_replace
from typing import TYPE_CHECKING, Any

from relinker.event import RetryEvent
from relinker.exceptions import TryAgain
from relinker.internal.clock import now
from relinker.internal.executor_helpers import function_name as _function_name
from relinker.internal.exhaustion import finish_exhausted, should_stop_before_sleep
from relinker.internal.retry_wait import plan_retry_wait, release_retry_wait
from relinker.internal.runtime import RetryRuntime

if TYPE_CHECKING:
    from collections.abc import Callable

    from relinker.policy import RetryPolicy


def execute_sync(
    policy: RetryPolicy[Any],
    function: Callable[..., Any],
    *args: Any,
    **kwargs: Any,
) -> Any:
    """Execute a synchronous function using a ``RetryPolicy``."""
    runtime = RetryRuntime(
        function_name=_function_name(function),
        started_at=now(),
        history_limit=policy.history_limit,
    )

    while True:
        attempt_number = runtime.begin_attempt()
        policy.emit(
            RetryEvent(
                name="before_attempt",
                attempt_number=attempt_number,
                function_name=runtime.function_name,
                state=runtime.state(),
            )
        )
        attempt_started_at = now()
        error: Exception

        try:
            value = function(*args, **kwargs)
        except TryAgain as caught_error:
            error = caught_error
            should_retry = True
        except Exception as caught_error:
            error = caught_error
            should_retry = policy.condition.should_retry_exception(error)
        else:
            attempt_ended_at = now()
            runtime.record_success(
                started_at=attempt_started_at,
                ended_at=attempt_ended_at,
                value=value,
                has_value=True,
            )
            should_retry_result = policy.condition.should_retry_result(value)
            elapsed = attempt_ended_at - runtime.started_at
            should_stop = policy.stop_strategy.should_stop(attempt_number, elapsed)

            if not should_retry_result:
                result = runtime.result(
                    ended_at=now(),
                    value=value,
                )
                policy.emit(
                    RetryEvent(
                        name="after_success",
                        attempt_number=attempt_number,
                        function_name=runtime.function_name,
                        value=value,
                        state=runtime.state(
                            last_value=value,
                            has_value=True,
                        ),
                    )
                )
                return result if policy.should_return_result else value

            if should_stop:
                result = runtime.result(
                    ended_at=now(),
                    value=value,
                    exhausted=True,
                    retry_cause="result",
                )
                policy.emit(
                    RetryEvent(
                        name="after_giveup",
                        attempt_number=attempt_number,
                        function_name=runtime.function_name,
                        value=value,
                        state=runtime.state(
                            last_value=value,
                            has_value=True,
                            retry_cause="result",
                            will_stop=True,
                        ),
                    )
                )
                return finish_exhausted(policy, result)

            pre_sleep_state = runtime.state(
                last_value=value,
                has_value=True,
                retry_cause="result",
                will_retry=True,
            )
            plan = plan_retry_wait(policy, attempt_number, pre_sleep_state)
            if should_stop_before_sleep(
                policy.stop_strategy,
                attempt_number,
                elapsed,
                plan.total_delay,
            ):
                release_retry_wait(plan)
                result = runtime.result(
                    ended_at=now(),
                    value=value,
                    exhausted=True,
                    retry_cause="result",
                )
                policy.emit(
                    RetryEvent(
                        name="after_giveup",
                        attempt_number=attempt_number,
                        function_name=runtime.function_name,
                        value=value,
                        state=runtime.state(
                            last_value=value,
                            has_value=True,
                            retry_cause="result",
                            will_stop=True,
                        ),
                    )
                )
                return finish_exhausted(policy, result)

            try:
                policy.emit(
                    RetryEvent(
                        name="before_sleep",
                        attempt_number=attempt_number,
                        function_name=runtime.function_name,
                        delay=plan.total_delay,
                        value=value,
                        state=_dc_replace(
                            pre_sleep_state,
                            next_delay=plan.total_delay,
                            policy_delay=plan.policy_delay,
                            budget_delay=plan.budget_delay,
                        ),
                    )
                )
                policy.sleep(plan.total_delay)
            except BaseException:
                release_retry_wait(plan)
                raise
            continue

        attempt_ended_at = now()
        runtime.record_failure(
            started_at=attempt_started_at,
            ended_at=attempt_ended_at,
            error=error,
        )
        elapsed = attempt_ended_at - runtime.started_at
        should_stop = policy.stop_strategy.should_stop(attempt_number, elapsed)

        policy.emit(
            RetryEvent(
                name="after_failure",
                attempt_number=attempt_number,
                function_name=runtime.function_name,
                error=error,
                state=runtime.state(
                    last_error=error,
                    retry_cause="exception",
                    will_retry=should_retry and not should_stop,
                    will_stop=should_stop,
                ),
            )
        )

        if not should_retry:
            result = runtime.result(
                ended_at=now(),
                error=error,
            )
            policy.emit(
                RetryEvent(
                    name="after_giveup",
                    attempt_number=attempt_number,
                    function_name=runtime.function_name,
                    error=error,
                )
            )
            if policy.should_return_result:
                return result
            if policy.should_raise_last:
                raise error
            return None

        if should_stop:
            result = runtime.result(
                ended_at=now(),
                error=error,
                exhausted=True,
                retry_cause="exception",
            )
            policy.emit(
                RetryEvent(
                    name="after_giveup",
                    attempt_number=attempt_number,
                    function_name=runtime.function_name,
                    error=error,
                    state=runtime.state(
                        last_error=error,
                        retry_cause="exception",
                        will_stop=True,
                    ),
                )
            )
            return finish_exhausted(policy, result)

        pre_sleep_state = runtime.state(
            last_error=error,
            retry_cause="exception",
            will_retry=True,
        )
        plan = plan_retry_wait(policy, attempt_number, pre_sleep_state)
        if should_stop_before_sleep(
            policy.stop_strategy,
            attempt_number,
            now() - runtime.started_at,
            plan.total_delay,
        ):
            release_retry_wait(plan)
            result = runtime.result(
                ended_at=now(),
                error=error,
                exhausted=True,
                retry_cause="exception",
            )
            policy.emit(
                RetryEvent(
                    name="after_giveup",
                    attempt_number=attempt_number,
                    function_name=runtime.function_name,
                    error=error,
                    state=runtime.state(
                        last_error=error,
                        retry_cause="exception",
                        will_stop=True,
                    ),
                )
            )
            return finish_exhausted(policy, result)

        try:
            policy.emit(
                RetryEvent(
                    name="before_sleep",
                    attempt_number=attempt_number,
                    function_name=runtime.function_name,
                    delay=plan.total_delay,
                    error=error,
                    state=_dc_replace(
                        pre_sleep_state,
                        next_delay=plan.total_delay,
                        policy_delay=plan.policy_delay,
                        budget_delay=plan.budget_delay,
                    ),
                )
            )
            policy.sleep(plan.total_delay)
        except BaseException:
            release_retry_wait(plan)
            raise
