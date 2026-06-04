"""
Context manager support for RetryFlow.

The decorator API is the easiest way to retry a function. The context manager
API is useful when users want to retry a block of code without extracting that
block into a separate function.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from retryflow.attempt import AttemptRecord
from retryflow.event import RetryEvent
from retryflow.exceptions import RetryExhaustedError, TryAgain
from retryflow.internal.clock import now
from retryflow.result import RetryResult
from retryflow.state import RetryCause, RetryState

if TYPE_CHECKING:
    from types import TracebackType

    from retryflow.policy import RetryPolicy


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
    started_at: float,
    attempts: list[AttemptRecord],
    last_value: Any = None,
    last_error: BaseException | None = None,
    next_delay: float | None = None,
    retry_cause: str | None = None,
    will_retry: bool = False,
    will_stop: bool = False,
) -> RetryState:
    """Build an immutable state snapshot for context manager events."""
    return RetryState(
        function_name=function_name,
        attempt_number=attempt_number,
        started_at=started_at,
        elapsed=now() - started_at,
        attempts=tuple(attempts),
        last_value=last_value,
        last_error=last_error,
        next_delay=next_delay,
        retry_cause=_normalize_retry_cause(retry_cause),
        will_retry=will_retry,
        will_stop=will_stop,
    )


class RetryBlockIterator:
    """Synchronous iterator that yields retry attempt context managers."""

    def __init__(self, policy: RetryPolicy[Any], *, name: str = "retry_block") -> None:
        self.policy = policy
        self.name = name
        self.started_at = now()
        self.attempts: list[AttemptRecord] = []
        self.attempt_number = 0
        self.finished = False
        self.result: RetryResult[Any] | None = None

    def __iter__(self) -> RetryBlockIterator:
        """Return this iterator."""
        return self

    def __next__(self) -> RetryAttemptContext:
        """Return the next attempt context manager."""
        if self.finished:
            raise StopIteration

        self.attempt_number += 1
        return RetryAttemptContext(self.policy, self)


class RetryAttemptContext:
    """
    Context manager representing one retry attempt.

    Use `set_result(value)` when you want result-based retry inside a block.
    """

    def __init__(self, policy: RetryPolicy[Any], iterator: RetryBlockIterator) -> None:
        self.policy = policy
        self.iterator = iterator
        self.attempt_started_at = 0.0
        self._has_result = False
        self._result_value: Any = None

    @property
    def number(self) -> int:
        """Return the one-based attempt number."""
        return self.iterator.attempt_number

    def set_result(self, value: Any) -> Any:
        """
        Store a returned value for result-based retry decisions.

        The value is returned unchanged so users can write:

            response = attempt.set_result(call_api())
        """
        self._has_result = True
        self._result_value = value
        return value

    def __enter__(self) -> RetryAttemptContext:
        """Enter a retry attempt."""
        self.attempt_started_at = now()
        self.policy.emit(
            RetryEvent(
                name="before_attempt",
                attempt_number=self.number,
                function_name=self.iterator.name,
                state=_state(
                    function_name=self.iterator.name,
                    attempt_number=self.number,
                    started_at=self.iterator.started_at,
                    attempts=self.iterator.attempts,
                ),
            )
        )
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool:
        """Exit a retry attempt and decide whether the loop should continue."""
        if exc is not None:
            return self._handle_exception(exc)

        return self._handle_success_or_result()

    def _handle_exception(self, error: BaseException) -> bool:
        """Handle an exception raised inside the block."""
        if not isinstance(error, Exception):
            return False

        attempt_ended_at = now()
        self.iterator.attempts.append(
            AttemptRecord(
                number=self.number,
                started_at=self.attempt_started_at,
                ended_at=attempt_ended_at,
                error=error,
            )
        )

        elapsed = attempt_ended_at - self.iterator.started_at
        # TryAgain bypasses the condition check — it is always a retry signal.
        if isinstance(error, TryAgain):
            should_retry = True
        else:
            should_retry = self.policy.condition.should_retry_exception(error)
        should_stop = self.policy.stop_strategy.should_stop(self.number, elapsed)

        self.policy.emit(
            RetryEvent(
                name="after_failure",
                attempt_number=self.number,
                function_name=self.iterator.name,
                error=error,
                state=_state(
                    function_name=self.iterator.name,
                    attempt_number=self.number,
                    started_at=self.iterator.started_at,
                    attempts=self.iterator.attempts,
                    last_error=error,
                    retry_cause="exception",
                    will_retry=should_retry and not should_stop,
                    will_stop=should_stop,
                ),
            )
        )

        if not should_retry or should_stop:
            self.iterator.finished = True
            self.iterator.result = RetryResult(
                attempts=tuple(self.iterator.attempts),
                error=error,
                started_at=self.iterator.started_at,
                ended_at=now(),
                exhausted=should_retry and should_stop,
                retry_cause="exception" if should_retry and should_stop else None,
            )
            self.policy.emit(
                RetryEvent(
                    name="after_giveup",
                    attempt_number=self.number,
                    function_name=self.iterator.name,
                    error=error,
                    state=_state(
                        function_name=self.iterator.name,
                        attempt_number=self.number,
                        started_at=self.iterator.started_at,
                        attempts=self.iterator.attempts,
                        last_error=error,
                        retry_cause="exception",
                        will_stop=True,
                    ),
                )
            )
            return False

        delay = self.policy.delay_strategy.next_delay(self.number)
        self.policy.emit(
            RetryEvent(
                name="before_sleep",
                attempt_number=self.number,
                function_name=self.iterator.name,
                delay=delay,
                error=error,
                state=_state(
                    function_name=self.iterator.name,
                    attempt_number=self.number,
                    started_at=self.iterator.started_at,
                    attempts=self.iterator.attempts,
                    last_error=error,
                    next_delay=delay,
                    retry_cause="exception",
                    will_retry=True,
                ),
            )
        )
        self.policy.sleep(delay)
        return True

    def _handle_success_or_result(self) -> bool:
        """Handle a block that did not raise an exception."""
        attempt_ended_at = now()
        value = self._result_value if self._has_result else None

        self.iterator.attempts.append(
            AttemptRecord(
                number=self.number,
                started_at=self.attempt_started_at,
                ended_at=attempt_ended_at,
                value=value,
            )
        )

        should_retry = self._has_result and self.policy.condition.should_retry_result(value)
        elapsed = attempt_ended_at - self.iterator.started_at
        should_stop = self.policy.stop_strategy.should_stop(self.number, elapsed)

        if not should_retry:
            self.iterator.finished = True
            self.iterator.result = RetryResult(
                attempts=tuple(self.iterator.attempts),
                value=value,
                started_at=self.iterator.started_at,
                ended_at=now(),
            )
            self.policy.emit(
                RetryEvent(
                    name="after_success",
                    attempt_number=self.number,
                    function_name=self.iterator.name,
                    value=value,
                    state=_state(
                        function_name=self.iterator.name,
                        attempt_number=self.number,
                        started_at=self.iterator.started_at,
                        attempts=self.iterator.attempts,
                        last_value=value,
                    ),
                )
            )
            return False

        if should_stop:
            self.iterator.finished = True
            self.iterator.result = RetryResult(
                attempts=tuple(self.iterator.attempts),
                value=value,
                started_at=self.iterator.started_at,
                ended_at=now(),
                exhausted=True,
                retry_cause="result",
            )
            self.policy.emit(
                RetryEvent(
                    name="after_giveup",
                    attempt_number=self.number,
                    function_name=self.iterator.name,
                    value=value,
                    state=_state(
                        function_name=self.iterator.name,
                        attempt_number=self.number,
                        started_at=self.iterator.started_at,
                        attempts=self.iterator.attempts,
                        last_value=value,
                        retry_cause="result",
                        will_stop=True,
                    ),
                )
            )
            if self.policy.result_exhausted_behavior == "raise":
                raise RetryExhaustedError(
                    "Retry attempts were exhausted by rejected return values.",
                    result=self.iterator.result,
                )
            return False

        delay = self.policy.delay_strategy.next_delay(self.number)
        self.policy.emit(
            RetryEvent(
                name="before_sleep",
                attempt_number=self.number,
                function_name=self.iterator.name,
                delay=delay,
                value=value,
                state=_state(
                    function_name=self.iterator.name,
                    attempt_number=self.number,
                    started_at=self.iterator.started_at,
                    attempts=self.iterator.attempts,
                    last_value=value,
                    next_delay=delay,
                    retry_cause="result",
                    will_retry=True,
                ),
            )
        )
        self.policy.sleep(delay)
        return False


class AsyncRetryBlockIterator:
    """Asynchronous iterator that yields retry attempt context managers."""

    def __init__(self, policy: RetryPolicy[Any], *, name: str = "retry_block") -> None:
        self.policy = policy
        self.name = name
        self.started_at = now()
        self.attempts: list[AttemptRecord] = []
        self.attempt_number = 0
        self.finished = False
        self.result: RetryResult[Any] | None = None

    def __aiter__(self) -> AsyncRetryBlockIterator:
        """Return this async iterator."""
        return self

    async def __anext__(self) -> AsyncRetryAttemptContext:
        """Return the next async attempt context manager."""
        if self.finished:
            raise StopAsyncIteration

        self.attempt_number += 1
        return AsyncRetryAttemptContext(self.policy, self)


class AsyncRetryAttemptContext:
    """
    Async context manager representing one retry attempt.

    Use `set_result(value)` when you want result-based retry inside a block.
    """

    def __init__(self, policy: RetryPolicy[Any], iterator: AsyncRetryBlockIterator) -> None:
        self.policy = policy
        self.iterator = iterator
        self.attempt_started_at = 0.0
        self._has_result = False
        self._result_value: Any = None

    @property
    def number(self) -> int:
        """Return the one-based attempt number."""
        return self.iterator.attempt_number

    def set_result(self, value: Any) -> Any:
        """Store a returned value for result-based retry decisions."""
        self._has_result = True
        self._result_value = value
        return value

    async def __aenter__(self) -> AsyncRetryAttemptContext:
        """Enter an async retry attempt."""
        self.attempt_started_at = now()
        self.policy.emit(
            RetryEvent(
                name="before_attempt",
                attempt_number=self.number,
                function_name=self.iterator.name,
                state=_state(
                    function_name=self.iterator.name,
                    attempt_number=self.number,
                    started_at=self.iterator.started_at,
                    attempts=self.iterator.attempts,
                ),
            )
        )
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool:
        """Exit an async retry attempt and decide whether the loop should continue."""
        if exc is not None:
            return await self._handle_exception(exc)

        return await self._handle_success_or_result()

    async def _handle_exception(self, error: BaseException) -> bool:
        """Handle an exception raised inside the async block."""
        if not isinstance(error, Exception):
            return False

        attempt_ended_at = now()
        self.iterator.attempts.append(
            AttemptRecord(
                number=self.number,
                started_at=self.attempt_started_at,
                ended_at=attempt_ended_at,
                error=error,
            )
        )

        elapsed = attempt_ended_at - self.iterator.started_at
        # TryAgain bypasses the condition check — it is always a retry signal.
        if isinstance(error, TryAgain):
            should_retry = True
        else:
            should_retry = self.policy.condition.should_retry_exception(error)
        should_stop = self.policy.stop_strategy.should_stop(self.number, elapsed)

        self.policy.emit(
            RetryEvent(
                name="after_failure",
                attempt_number=self.number,
                function_name=self.iterator.name,
                error=error,
                state=_state(
                    function_name=self.iterator.name,
                    attempt_number=self.number,
                    started_at=self.iterator.started_at,
                    attempts=self.iterator.attempts,
                    last_error=error,
                    retry_cause="exception",
                    will_retry=should_retry and not should_stop,
                    will_stop=should_stop,
                ),
            )
        )

        if not should_retry or should_stop:
            self.iterator.finished = True
            self.iterator.result = RetryResult(
                attempts=tuple(self.iterator.attempts),
                error=error,
                started_at=self.iterator.started_at,
                ended_at=now(),
                exhausted=should_retry and should_stop,
                retry_cause="exception" if should_retry and should_stop else None,
            )
            self.policy.emit(
                RetryEvent(
                    name="after_giveup",
                    attempt_number=self.number,
                    function_name=self.iterator.name,
                    error=error,
                    state=_state(
                        function_name=self.iterator.name,
                        attempt_number=self.number,
                        started_at=self.iterator.started_at,
                        attempts=self.iterator.attempts,
                        last_error=error,
                        retry_cause="exception",
                        will_stop=True,
                    ),
                )
            )
            return False

        delay = self.policy.delay_strategy.next_delay(self.number)
        self.policy.emit(
            RetryEvent(
                name="before_sleep",
                attempt_number=self.number,
                function_name=self.iterator.name,
                delay=delay,
                error=error,
                state=_state(
                    function_name=self.iterator.name,
                    attempt_number=self.number,
                    started_at=self.iterator.started_at,
                    attempts=self.iterator.attempts,
                    last_error=error,
                    next_delay=delay,
                    retry_cause="exception",
                    will_retry=True,
                ),
            )
        )
        await self.policy.async_sleep(delay)
        return True

    async def _handle_success_or_result(self) -> bool:
        """Handle an async block that did not raise an exception."""
        attempt_ended_at = now()
        value = self._result_value if self._has_result else None

        self.iterator.attempts.append(
            AttemptRecord(
                number=self.number,
                started_at=self.attempt_started_at,
                ended_at=attempt_ended_at,
                value=value,
            )
        )

        should_retry = self._has_result and self.policy.condition.should_retry_result(value)
        elapsed = attempt_ended_at - self.iterator.started_at
        should_stop = self.policy.stop_strategy.should_stop(self.number, elapsed)

        if not should_retry:
            self.iterator.finished = True
            self.iterator.result = RetryResult(
                attempts=tuple(self.iterator.attempts),
                value=value,
                started_at=self.iterator.started_at,
                ended_at=now(),
            )
            self.policy.emit(
                RetryEvent(
                    name="after_success",
                    attempt_number=self.number,
                    function_name=self.iterator.name,
                    value=value,
                    state=_state(
                        function_name=self.iterator.name,
                        attempt_number=self.number,
                        started_at=self.iterator.started_at,
                        attempts=self.iterator.attempts,
                        last_value=value,
                    ),
                )
            )
            return False

        if should_stop:
            self.iterator.finished = True
            self.iterator.result = RetryResult(
                attempts=tuple(self.iterator.attempts),
                value=value,
                started_at=self.iterator.started_at,
                ended_at=now(),
                exhausted=True,
                retry_cause="result",
            )
            self.policy.emit(
                RetryEvent(
                    name="after_giveup",
                    attempt_number=self.number,
                    function_name=self.iterator.name,
                    value=value,
                    state=_state(
                        function_name=self.iterator.name,
                        attempt_number=self.number,
                        started_at=self.iterator.started_at,
                        attempts=self.iterator.attempts,
                        last_value=value,
                        retry_cause="result",
                        will_stop=True,
                    ),
                )
            )
            if self.policy.result_exhausted_behavior == "raise":
                raise RetryExhaustedError(
                    "Retry attempts were exhausted by rejected return values.",
                    result=self.iterator.result,
                )
            return False

        delay = self.policy.delay_strategy.next_delay(self.number)
        self.policy.emit(
            RetryEvent(
                name="before_sleep",
                attempt_number=self.number,
                function_name=self.iterator.name,
                delay=delay,
                value=value,
                state=_state(
                    function_name=self.iterator.name,
                    attempt_number=self.number,
                    started_at=self.iterator.started_at,
                    attempts=self.iterator.attempts,
                    last_value=value,
                    next_delay=delay,
                    retry_cause="result",
                    will_retry=True,
                ),
            )
        )
        await self.policy.async_sleep(delay)
        return False
