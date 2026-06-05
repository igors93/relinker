"""Asynchronous retry executor."""

from __future__ import annotations

from collections import deque
from dataclasses import replace as _dc_replace
from typing import TYPE_CHECKING, Any

from relinker.attempt import AttemptRecord
from relinker.delays.stateful import resolve_delay
from relinker.event import RetryEvent
from relinker.exceptions import TryAgain
from relinker.internal.clock import now
from relinker.internal.executor_helpers import build_state
from relinker.internal.executor_helpers import function_name as _function_name
from relinker.internal.exhaustion import finish_exhausted, should_stop_before_sleep
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
    )


async def execute_async(
    policy: RetryPolicy[Any],
    function: Callable[..., Any],
    *args: Any,
    **kwargs: Any,
) -> Any:
    """
    Execute an async function using a RetryPolicy.

    The executor never catches BaseException directly. This prevents Relinker
    from swallowing interpreter-level signals such as KeyboardInterrupt and
    SystemExit.
    """
    limit = policy.history_limit
    attempts: deque[AttemptRecord] = deque(maxlen=limit)
    execution_started_at = now()
    function_name = _function_name(function)
    attempt_number = 0

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

        try:
            value = await function(*args, **kwargs)
        except TryAgain as error:
            # TryAgain is an explicit user retry signal — bypass the condition check.
            attempt_ended_at = now()
            attempts.append(
                AttemptRecord(
                    number=attempt_number,
                    started_at=attempt_started_at,
                    ended_at=attempt_ended_at,
                    error=error,
                )
            )
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
                        will_retry=not should_stop,
                        will_stop=should_stop,
                    ),
                )
            )
            if should_stop:
                result: RetryResult[Any] = RetryResult(
                    attempts=tuple(attempts),
                    error=error,
                    started_at=execution_started_at,
                    ended_at=now(),
                    exhausted=True,
                    retry_cause="exception",
                    total_attempts=attempt_number,
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
            delay = resolve_delay(policy.delay_strategy, attempt_number, pre_sleep_state)
            if should_stop_before_sleep(policy.stop_strategy, attempt_number, elapsed, delay):
                result = RetryResult(
                    attempts=tuple(attempts),
                    error=error,
                    started_at=execution_started_at,
                    ended_at=now(),
                    exhausted=True,
                    retry_cause="exception",
                    total_attempts=attempt_number,
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
                    delay=delay,
                    error=error,
                    state=_dc_replace(pre_sleep_state, next_delay=delay),
                )
            )
            await policy.async_sleep(delay)
            continue
        except Exception as error:
            attempt_ended_at = now()
            attempts.append(
                AttemptRecord(
                    number=attempt_number,
                    started_at=attempt_started_at,
                    ended_at=attempt_ended_at,
                    error=error,
                )
            )

            elapsed = attempt_ended_at - execution_started_at
            should_retry = policy.condition.should_retry_exception(error)
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
                result = RetryResult(
                    attempts=tuple(attempts),
                    error=error,
                    started_at=execution_started_at,
                    ended_at=now(),
                    total_attempts=attempt_number,
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
                result = RetryResult(
                    attempts=tuple(attempts),
                    error=error,
                    started_at=execution_started_at,
                    ended_at=now(),
                    exhausted=True,
                    retry_cause="exception",
                    total_attempts=attempt_number,
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
            delay = resolve_delay(policy.delay_strategy, attempt_number, pre_sleep_state)
            if should_stop_before_sleep(policy.stop_strategy, attempt_number, elapsed, delay):
                result = RetryResult(
                    attempts=tuple(attempts),
                    error=error,
                    started_at=execution_started_at,
                    ended_at=now(),
                    exhausted=True,
                    retry_cause="exception",
                    total_attempts=attempt_number,
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
                    delay=delay,
                    error=error,
                    state=_dc_replace(pre_sleep_state, next_delay=delay),
                )
            )
            await policy.async_sleep(delay)
            continue

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

        should_retry = policy.condition.should_retry_result(value)
        elapsed = attempt_ended_at - execution_started_at
        should_stop = policy.stop_strategy.should_stop(attempt_number, elapsed)

        if not should_retry:
            result = RetryResult(
                attempts=tuple(attempts),
                value=value,
                started_at=execution_started_at,
                ended_at=now(),
                total_attempts=attempt_number,
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
            if policy.should_return_result:
                return result
            return value

        if should_stop:
            result = RetryResult(
                attempts=tuple(attempts),
                value=value,
                started_at=execution_started_at,
                ended_at=now(),
                exhausted=True,
                retry_cause="result",
                total_attempts=attempt_number,
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
        delay = resolve_delay(policy.delay_strategy, attempt_number, pre_sleep_state)
        if should_stop_before_sleep(policy.stop_strategy, attempt_number, elapsed, delay):
            result = RetryResult(
                attempts=tuple(attempts),
                value=value,
                started_at=execution_started_at,
                ended_at=now(),
                exhausted=True,
                retry_cause="result",
                total_attempts=attempt_number,
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
                delay=delay,
                value=value,
                state=_dc_replace(pre_sleep_state, next_delay=delay),
            )
        )
        await policy.async_sleep(delay)
