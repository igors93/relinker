"""Asynchronous retry executor."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from retryflow.attempt import AttemptRecord
from retryflow.event import RetryEvent
from retryflow.exceptions import RetryExhaustedError
from retryflow.internal.clock import now
from retryflow.result import RetryResult
from retryflow.state import RetryCause, RetryState

if TYPE_CHECKING:
    from collections.abc import Callable

    from retryflow.policy import RetryPolicy


def _function_name(function: Callable[..., Any]) -> str:
    """Return a readable function name for events and debug output."""
    return getattr(function, "__name__", function.__class__.__name__)


def _normalize_retry_cause(retry_cause: str | None) -> RetryCause | None:
    """Return a RetryCause literal value accepted by type checkers."""
    if retry_cause == "exception":
        return "exception"
    if retry_cause == "result":
        return "result"
    return None


def _state(
    *,
    function_name: str,
    attempt_number: int,
    execution_started_at: float,
    attempts: list[AttemptRecord],
    last_value: Any = None,
    last_error: BaseException | None = None,
    next_delay: float | None = None,
    retry_cause: str | None = None,
    will_retry: bool = False,
    will_stop: bool = False,
) -> RetryState:
    """Build an immutable state snapshot for events."""
    return RetryState(
        function_name=function_name,
        attempt_number=attempt_number,
        started_at=execution_started_at,
        elapsed=now() - execution_started_at,
        attempts=tuple(attempts),
        last_value=last_value,
        last_error=last_error,
        next_delay=next_delay,
        retry_cause=_normalize_retry_cause(retry_cause),
        will_retry=will_retry,
        will_stop=will_stop,
    )


def _finish_exhausted(policy: RetryPolicy[Any], result: RetryResult[Any]) -> Any:
    """Apply final exhausted behavior configured by the policy."""
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


async def execute_async(
    policy: RetryPolicy[Any],
    function: Callable[..., Any],
    *args: Any,
    **kwargs: Any,
) -> Any:
    """
    Execute an async function using a RetryPolicy.

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
                result: RetryResult[Any] = RetryResult(
                    attempts=tuple(attempts),
                    error=error,
                    started_at=execution_started_at,
                    ended_at=now(),
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
                return _finish_exhausted(policy, result)

            delay = policy.delay_strategy.next_delay(attempt_number)
            policy.emit(
                RetryEvent(
                    name="before_sleep",
                    attempt_number=attempt_number,
                    function_name=function_name,
                    delay=delay,
                    error=error,
                    state=_state(
                        function_name=function_name,
                        attempt_number=attempt_number,
                        execution_started_at=execution_started_at,
                        attempts=attempts,
                        last_error=error,
                        next_delay=delay,
                        retry_cause="exception",
                        will_retry=True,
                    ),
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
                    state=_state(
                        function_name=function_name,
                        attempt_number=attempt_number,
                        execution_started_at=execution_started_at,
                        attempts=attempts,
                        last_value=value,
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
                        retry_cause="result",
                        will_stop=True,
                    ),
                )
            )
            return _finish_exhausted(policy, result)

        delay = policy.delay_strategy.next_delay(attempt_number)
        policy.emit(
            RetryEvent(
                name="before_sleep",
                attempt_number=attempt_number,
                function_name=function_name,
                delay=delay,
                value=value,
                state=_state(
                    function_name=function_name,
                    attempt_number=attempt_number,
                    execution_started_at=execution_started_at,
                    attempts=attempts,
                    last_value=value,
                    next_delay=delay,
                    retry_cause="result",
                    will_retry=True,
                ),
            )
        )
        await policy.async_sleep(delay)
