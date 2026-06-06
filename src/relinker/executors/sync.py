"""Synchronous retry executor."""

from __future__ import annotations

from collections import deque
from dataclasses import replace as _dc_replace
from typing import TYPE_CHECKING, Any

from relinker.attempt import AttemptRecord
from relinker.event import RetryEvent
from relinker.exceptions import TryAgain
from relinker.internal.clock import now
from relinker.internal.executor_helpers import build_state
from relinker.internal.executor_helpers import function_name as _function_name
from relinker.internal.exhaustion import finish_exhausted, should_stop_before_sleep
from relinker.internal.retry_wait import plan_retry_wait, release_retry_wait
from relinker.result import RetryResult

if TYPE_CHECKING:
    from collections.abc import Callable

    from relinker.policy import RetryPolicy


def _state(
    *,
    function_name: str,
    attempt_number: int,
    execution_started_at: float,
    attempts: deque[AttemptRecord],
    last_value: Any = None,
    last_error: BaseException | None = None,
    has_value: bool = False,
    next_delay: float | None = None,
    retry_cause: str | None = None,
    will_retry: bool = False,
    will_stop: bool = False,
    policy_delay: float | None = None,
    budget_delay: float | None = None,
) -> Any:
    return build_state(
        function_name=function_name,
        attempt_number=attempt_number,
        started_at=execution_started_at,
        attempts=attempts,
        last_value=last_value,
        last_error=last_error,
        has_value=has_value,
        next_delay=next_delay,
        retry_cause=retry_cause,
        will_retry=will_retry,
        will_stop=will_stop,
        policy_delay=policy_delay,
        budget_delay=budget_delay,
    )


def _make_result(
    *,
    attempts: deque[AttemptRecord],
    started_at: float,
    attempt_number: int,
    failed_count: int,
    success_count: int,
    value: Any = None,
    error: BaseException | None = None,
    exhausted: bool = False,
    retry_cause: str | None = None,
) -> RetryResult[Any]:
    cause = retry_cause if retry_cause in {"exception", "result"} else None
    return RetryResult(
        attempts=tuple(attempts),
        value=value,
        error=error,
        started_at=started_at,
        ended_at=now(),
        exhausted=exhausted,
        retry_cause=cause,  # type: ignore[arg-type]
        total_attempts=attempt_number,
        total_failed_attempts=failed_count,
        total_successful_attempts=success_count,
    )


def execute_sync(
    policy: RetryPolicy[Any],
    function: Callable[..., Any],
    *args: Any,
    **kwargs: Any,
) -> Any:
    """Execute a synchronous function using a ``RetryPolicy``."""
    attempts: deque[AttemptRecord] = deque(maxlen=policy.history_limit)
    execution_started_at = now()
    function_name = _function_name(function)
    attempt_number = 0
    failed_count = 0
    success_count = 0

    while True:
        attempt_number += 1
        policy.emit(
            RetryEvent(
                name="before_attempt",
                attempt_number=attempt_number,
                function_name=function_name,
                state=_state(
                    function_name=function_name,
                    attempt_number=attempt_number,
                    execution_started_at=execution_started_at,
                    attempts=attempts,
                ),
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
            attempts.append(
                AttemptRecord(
                    number=attempt_number,
                    started_at=attempt_started_at,
                    ended_at=attempt_ended_at,
                    value=value,
                    has_value=True,
                )
            )
            success_count += 1
            should_retry_result = policy.condition.should_retry_result(value)
            elapsed = attempt_ended_at - execution_started_at
            should_stop = policy.stop_strategy.should_stop(attempt_number, elapsed)

            if not should_retry_result:
                result = _make_result(
                    attempts=attempts,
                    started_at=execution_started_at,
                    attempt_number=attempt_number,
                    failed_count=failed_count,
                    success_count=success_count,
                    value=value,
                )
                policy.emit(
                    RetryEvent(
                        name="after_success",
                        attempt_number=attempt_number,
                        function_name=function_name,
                        value=value,
                        state=_state(
                            function_name=function_name,
                            attempt_number=attempt_number,
                            execution_started_at=execution_started_at,
                            attempts=attempts,
                            last_value=value,
                            has_value=True,
                        ),
                    )
                )
                return result if policy.should_return_result else value

            if should_stop:
                result = _make_result(
                    attempts=attempts,
                    started_at=execution_started_at,
                    attempt_number=attempt_number,
                    failed_count=failed_count,
                    success_count=success_count,
                    value=value,
                    exhausted=True,
                    retry_cause="result",
                )
                policy.emit(
                    RetryEvent(
                        name="after_giveup",
                        attempt_number=attempt_number,
                        function_name=function_name,
                        value=value,
                        state=_state(
                            function_name=function_name,
                            attempt_number=attempt_number,
                            execution_started_at=execution_started_at,
                            attempts=attempts,
                            last_value=value,
                            has_value=True,
                            retry_cause="result",
                            will_stop=True,
                        ),
                    )
                )
                return finish_exhausted(policy, result)

            pre_sleep_state = _state(
                function_name=function_name,
                attempt_number=attempt_number,
                execution_started_at=execution_started_at,
                attempts=attempts,
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
                result = _make_result(
                    attempts=attempts,
                    started_at=execution_started_at,
                    attempt_number=attempt_number,
                    failed_count=failed_count,
                    success_count=success_count,
                    value=value,
                    exhausted=True,
                    retry_cause="result",
                )
                policy.emit(
                    RetryEvent(
                        name="after_giveup",
                        attempt_number=attempt_number,
                        function_name=function_name,
                        value=value,
                        state=_state(
                            function_name=function_name,
                            attempt_number=attempt_number,
                            execution_started_at=execution_started_at,
                            attempts=attempts,
                            last_value=value,
                            has_value=True,
                            retry_cause="result",
                            will_stop=True,
                        ),
                    )
                )
                return finish_exhausted(policy, result)

            policy.emit(
                RetryEvent(
                    name="before_sleep",
                    attempt_number=attempt_number,
                    function_name=function_name,
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
            try:
                policy.sleep(plan.total_delay)
            except BaseException:
                release_retry_wait(plan)
                raise
            continue

        attempt_ended_at = now()
        attempts.append(
            AttemptRecord(
                number=attempt_number,
                started_at=attempt_started_at,
                ended_at=attempt_ended_at,
                error=error,
            )
        )
        failed_count += 1
        elapsed = attempt_ended_at - execution_started_at
        should_stop = policy.stop_strategy.should_stop(attempt_number, elapsed)

        policy.emit(
            RetryEvent(
                name="after_failure",
                attempt_number=attempt_number,
                function_name=function_name,
                error=error,
                state=_state(
                    function_name=function_name,
                    attempt_number=attempt_number,
                    execution_started_at=execution_started_at,
                    attempts=attempts,
                    last_error=error,
                    retry_cause="exception",
                    will_retry=should_retry and not should_stop,
                    will_stop=should_stop,
                ),
            )
        )

        if not should_retry:
            result = _make_result(
                attempts=attempts,
                started_at=execution_started_at,
                attempt_number=attempt_number,
                failed_count=failed_count,
                success_count=success_count,
                error=error,
            )
            policy.emit(
                RetryEvent(
                    name="after_giveup",
                    attempt_number=attempt_number,
                    function_name=function_name,
                    error=error,
                )
            )
            if policy.should_return_result:
                return result
            if policy.should_raise_last:
                raise error
            return None

        if should_stop:
            result = _make_result(
                attempts=attempts,
                started_at=execution_started_at,
                attempt_number=attempt_number,
                failed_count=failed_count,
                success_count=success_count,
                error=error,
                exhausted=True,
                retry_cause="exception",
            )
            policy.emit(
                RetryEvent(
                    name="after_giveup",
                    attempt_number=attempt_number,
                    function_name=function_name,
                    error=error,
                    state=_state(
                        function_name=function_name,
                        attempt_number=attempt_number,
                        execution_started_at=execution_started_at,
                        attempts=attempts,
                        last_error=error,
                        retry_cause="exception",
                        will_stop=True,
                    ),
                )
            )
            return finish_exhausted(policy, result)

        pre_sleep_state = _state(
            function_name=function_name,
            attempt_number=attempt_number,
            execution_started_at=execution_started_at,
            attempts=attempts,
            last_error=error,
            retry_cause="exception",
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
            result = _make_result(
                attempts=attempts,
                started_at=execution_started_at,
                attempt_number=attempt_number,
                failed_count=failed_count,
                success_count=success_count,
                error=error,
                exhausted=True,
                retry_cause="exception",
            )
            policy.emit(
                RetryEvent(
                    name="after_giveup",
                    attempt_number=attempt_number,
                    function_name=function_name,
                    error=error,
                    state=_state(
                        function_name=function_name,
                        attempt_number=attempt_number,
                        execution_started_at=execution_started_at,
                        attempts=attempts,
                        last_error=error,
                        retry_cause="exception",
                        will_stop=True,
                    ),
                )
            )
            return finish_exhausted(policy, result)

        policy.emit(
            RetryEvent(
                name="before_sleep",
                attempt_number=attempt_number,
                function_name=function_name,
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
        try:
            policy.sleep(plan.total_delay)
        except BaseException:
            release_retry_wait(plan)
            raise
