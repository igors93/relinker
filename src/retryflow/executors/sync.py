"""Synchronous retry executor."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from retryflow.attempt import AttemptRecord
from retryflow.event import RetryEvent
from retryflow.exceptions import RetryExhaustedError
from retryflow.internal.clock import now
from retryflow.result import RetryResult

if TYPE_CHECKING:
    from collections.abc import Callable

    from retryflow.policy import RetryPolicy


def _function_name(function: Callable[..., Any]) -> str:
    """Return a readable function name for events and debug output."""
    return getattr(function, "__name__", function.__class__.__name__)


def execute_sync(
    policy: RetryPolicy[Any],
    function: Callable[..., Any],
    *args: Any,
    **kwargs: Any,
) -> Any:
    """
    Execute a synchronous function using a RetryPolicy.

    The executor never catches BaseException directly. This prevents RetryFlow
    from swallowing interpreter-level signals such as KeyboardInterrupt and
    SystemExit.
    """
    attempts: list[AttemptRecord] = []
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
            )
        )

        attempt_started_at = now()

        try:
            value = function(*args, **kwargs)
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

            policy.emit(
                RetryEvent(
                    name="after_failure",
                    attempt_number=attempt_number,
                    function_name=function_name,
                    error=error,
                )
            )

            elapsed = attempt_ended_at - execution_started_at
            should_retry = policy.condition.should_retry_exception(error)
            should_stop = policy.stop_strategy.should_stop(attempt_number, elapsed)

            if not should_retry or should_stop:
                result: RetryResult[Any] = RetryResult(
                    attempts=tuple(attempts),
                    error=error,
                    started_at=execution_started_at,
                    ended_at=now(),
                    exhausted=should_retry and should_stop,
                    retry_cause="exception" if should_retry and should_stop else None,
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

            delay = policy.delay_strategy.next_delay(attempt_number)
            policy.emit(
                RetryEvent(
                    name="before_sleep",
                    attempt_number=attempt_number,
                    function_name=function_name,
                    delay=delay,
                    error=error,
                )
            )
            policy.sleep(delay)
            continue

        attempt_ended_at = now()
        attempts.append(
            AttemptRecord(
                number=attempt_number,
                started_at=attempt_started_at,
                ended_at=attempt_ended_at,
                value=value,
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
            )
            policy.emit(
                RetryEvent(
                    name="after_success",
                    attempt_number=attempt_number,
                    function_name=function_name,
                    value=value,
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
            )
            policy.emit(
                RetryEvent(
                    name="after_giveup",
                    attempt_number=attempt_number,
                    function_name=function_name,
                    value=value,
                )
            )
            if policy.should_return_result:
                return result
            if policy.result_exhausted_behavior == "raise":
                raise RetryExhaustedError(
                    "Retry attempts were exhausted by rejected return values.",
                    result=result,
                )
            return value

        delay = policy.delay_strategy.next_delay(attempt_number)
        policy.emit(
            RetryEvent(
                name="before_sleep",
                attempt_number=attempt_number,
                function_name=function_name,
                delay=delay,
                value=value,
            )
        )
        policy.sleep(delay)
