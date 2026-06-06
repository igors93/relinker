"""Context-manager support for retrying inline blocks."""

from __future__ import annotations

from collections import deque
from dataclasses import replace as _dc_replace
from typing import TYPE_CHECKING, Any

from relinker.attempt import AttemptRecord
from relinker.event import RetryEvent
from relinker.exceptions import TryAgain
from relinker.internal.clock import now
from relinker.internal.exhaustion import finish_exhausted, should_stop_before_sleep
from relinker.internal.retry_wait import plan_retry_wait, release_retry_wait
from relinker.internal.runtime import RetryRuntime
from relinker.result import RetryResult

if TYPE_CHECKING:
    from types import TracebackType

    from relinker.policy import RetryPolicy


class RetryBlockIterator:
    """Synchronous iterator that yields retry attempt context managers."""

    def __init__(self, policy: RetryPolicy[Any], *, name: str = "retry_block") -> None:
        self.policy = policy
        self.name = name
        self._runtime = RetryRuntime(
            function_name=name,
            started_at=now(),
            history_limit=policy.history_limit,
        )
        self.finished = False
        self.result: RetryResult[Any] | None = None
        self.outcome: Any = None
        self.has_outcome = False

    @property
    def started_at(self) -> float:
        return self._runtime.started_at

    @property
    def attempts(self) -> deque[AttemptRecord]:
        return self._runtime.attempts

    @property
    def attempt_number(self) -> int:
        return self._runtime.attempt_number

    def __iter__(self) -> RetryBlockIterator:
        return self

    def __next__(self) -> RetryAttemptContext:
        if self.finished:
            raise StopIteration
        self._runtime.begin_attempt()
        return RetryAttemptContext(self.policy, self)


class RetryAttemptContext:
    """Context manager representing one synchronous retry attempt."""

    def __init__(self, policy: RetryPolicy[Any], iterator: RetryBlockIterator) -> None:
        self.policy = policy
        self.iterator = iterator
        self.attempt_started_at = 0.0
        self._has_result = False
        self._result_value: Any = None

    @property
    def number(self) -> int:
        return self.iterator.attempt_number

    def set_result(self, value: Any) -> Any:
        self._has_result = True
        self._result_value = value
        return value

    def _apply_exhausted(
        self,
        result: RetryResult[Any],
        current_error: BaseException | None,
    ) -> bool:
        try:
            resolved = finish_exhausted(self.policy, result)
            self.iterator.outcome = resolved
            self.iterator.has_outcome = True
            return current_error is not None
        except BaseException as exc:
            if current_error is not None and exc is current_error:
                return False
            raise

    def __enter__(self) -> RetryAttemptContext:
        self.attempt_started_at = now()
        self.policy.emit(
            RetryEvent(
                name="before_attempt",
                attempt_number=self.number,
                function_name=self.iterator.name,
                state=self.iterator._runtime.state(),
            )
        )
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool:
        del exc_type, traceback
        if exc is not None:
            return self._handle_exception(exc)
        return self._handle_success_or_result()

    def _giveup(
        self,
        *,
        value: Any = None,
        error: BaseException | None = None,
        retry_cause: str,
    ) -> None:
        self.policy.emit(
            RetryEvent(
                name="after_giveup",
                attempt_number=self.number,
                function_name=self.iterator.name,
                value=value,
                error=error,
                state=self.iterator._runtime.state(
                    last_value=value,
                    last_error=error,
                    has_value=error is None and self._has_result,
                    retry_cause=retry_cause,
                    will_stop=True,
                ),
            )
        )

    def _handle_exception(self, error: BaseException) -> bool:
        if not isinstance(error, Exception):
            return False
        ended_at = now()
        self.iterator._runtime.record_failure(
            started_at=self.attempt_started_at,
            ended_at=ended_at,
            error=error,
        )
        elapsed = ended_at - self.iterator.started_at
        should_retry = isinstance(error, TryAgain) or self.policy.condition.should_retry_exception(
            error
        )
        should_stop = self.policy.stop_strategy.should_stop(self.number, elapsed)
        self.policy.emit(
            RetryEvent(
                name="after_failure",
                attempt_number=self.number,
                function_name=self.iterator.name,
                error=error,
                state=self.iterator._runtime.state(
                    last_error=error,
                    retry_cause="exception",
                    will_retry=should_retry and not should_stop,
                    will_stop=should_stop,
                ),
            )
        )

        if not should_retry:
            self.iterator.finished = True
            self.iterator.result = self.iterator._runtime.result(ended_at=now(), error=error)
            self._giveup(error=error, retry_cause="exception")
            return False

        if should_stop:
            self.iterator.finished = True
            result = self.iterator._runtime.result(
                ended_at=now(),
                error=error,
                exhausted=True,
                retry_cause="exception",
            )
            self.iterator.result = result
            self._giveup(error=error, retry_cause="exception")
            return self._apply_exhausted(result, error)

        pre_sleep_state = self.iterator._runtime.state(
            last_error=error,
            retry_cause="exception",
            will_retry=True,
        )
        plan = plan_retry_wait(self.policy, self.number, pre_sleep_state)
        if should_stop_before_sleep(
            self.policy.stop_strategy, self.number, elapsed, plan.total_delay
        ):
            release_retry_wait(plan)
            self.iterator.finished = True
            result = self.iterator._runtime.result(
                ended_at=now(),
                error=error,
                exhausted=True,
                retry_cause="exception",
            )
            self.iterator.result = result
            self._giveup(error=error, retry_cause="exception")
            return self._apply_exhausted(result, error)

        self.policy.emit(
            RetryEvent(
                name="before_sleep",
                attempt_number=self.number,
                function_name=self.iterator.name,
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
            self.policy.sleep(plan.total_delay)
        except BaseException:
            release_retry_wait(plan)
            raise
        return True

    def _handle_success_or_result(self) -> bool:
        ended_at = now()
        value = self._result_value if self._has_result else None
        self.iterator._runtime.record_success(
            started_at=self.attempt_started_at,
            ended_at=ended_at,
            value=value,
            has_value=self._has_result,
        )
        should_retry = self._has_result and self.policy.condition.should_retry_result(value)
        elapsed = ended_at - self.iterator.started_at
        should_stop = self.policy.stop_strategy.should_stop(self.number, elapsed)

        if not should_retry:
            self.iterator.finished = True
            self.iterator.result = self.iterator._runtime.result(ended_at=now(), value=value)
            self.policy.emit(
                RetryEvent(
                    name="after_success",
                    attempt_number=self.number,
                    function_name=self.iterator.name,
                    value=value,
                    state=self.iterator._runtime.state(
                        last_value=value,
                        has_value=self._has_result,
                    ),
                )
            )
            return False

        if should_stop:
            self.iterator.finished = True
            result = self.iterator._runtime.result(
                ended_at=now(),
                value=value,
                exhausted=True,
                retry_cause="result",
            )
            self.iterator.result = result
            self._giveup(value=value, retry_cause="result")
            return self._apply_exhausted(result, None)

        pre_sleep_state = self.iterator._runtime.state(
            last_value=value,
            has_value=self._has_result,
            retry_cause="result",
            will_retry=True,
        )
        plan = plan_retry_wait(self.policy, self.number, pre_sleep_state)
        if should_stop_before_sleep(
            self.policy.stop_strategy, self.number, elapsed, plan.total_delay
        ):
            release_retry_wait(plan)
            self.iterator.finished = True
            result = self.iterator._runtime.result(
                ended_at=now(),
                value=value,
                exhausted=True,
                retry_cause="result",
            )
            self.iterator.result = result
            self._giveup(value=value, retry_cause="result")
            return self._apply_exhausted(result, None)

        self.policy.emit(
            RetryEvent(
                name="before_sleep",
                attempt_number=self.number,
                function_name=self.iterator.name,
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
            self.policy.sleep(plan.total_delay)
        except BaseException:
            release_retry_wait(plan)
            raise
        return False


class AsyncRetryBlockIterator:
    """Asynchronous iterator that yields retry attempt context managers."""

    def __init__(self, policy: RetryPolicy[Any], *, name: str = "retry_block") -> None:
        self.policy = policy
        self.name = name
        self._runtime = RetryRuntime(
            function_name=name,
            started_at=now(),
            history_limit=policy.history_limit,
        )
        self.finished = False
        self.result: RetryResult[Any] | None = None
        self.outcome: Any = None
        self.has_outcome = False

    @property
    def started_at(self) -> float:
        return self._runtime.started_at

    @property
    def attempts(self) -> deque[AttemptRecord]:
        return self._runtime.attempts

    @property
    def attempt_number(self) -> int:
        return self._runtime.attempt_number

    def __aiter__(self) -> AsyncRetryBlockIterator:
        return self

    async def __anext__(self) -> AsyncRetryAttemptContext:
        if self.finished:
            raise StopAsyncIteration
        self._runtime.begin_attempt()
        return AsyncRetryAttemptContext(self.policy, self)


class AsyncRetryAttemptContext:
    """Async context manager representing one retry attempt."""

    def __init__(self, policy: RetryPolicy[Any], iterator: AsyncRetryBlockIterator) -> None:
        self.policy = policy
        self.iterator = iterator
        self.attempt_started_at = 0.0
        self._has_result = False
        self._result_value: Any = None

    @property
    def number(self) -> int:
        return self.iterator.attempt_number

    def set_result(self, value: Any) -> Any:
        self._has_result = True
        self._result_value = value
        return value

    def _apply_exhausted(
        self,
        result: RetryResult[Any],
        current_error: BaseException | None,
    ) -> bool:
        try:
            resolved = finish_exhausted(self.policy, result)
            self.iterator.outcome = resolved
            self.iterator.has_outcome = True
            return current_error is not None
        except BaseException as exc:
            if current_error is not None and exc is current_error:
                return False
            raise

    async def __aenter__(self) -> AsyncRetryAttemptContext:
        self.attempt_started_at = now()
        self.policy.emit(
            RetryEvent(
                name="before_attempt",
                attempt_number=self.number,
                function_name=self.iterator.name,
                state=self.iterator._runtime.state(),
            )
        )
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool:
        del exc_type, traceback
        if exc is not None:
            return await self._handle_exception(exc)
        return await self._handle_success_or_result()

    def _giveup(
        self,
        *,
        value: Any = None,
        error: BaseException | None = None,
        retry_cause: str,
    ) -> None:
        self.policy.emit(
            RetryEvent(
                name="after_giveup",
                attempt_number=self.number,
                function_name=self.iterator.name,
                value=value,
                error=error,
                state=self.iterator._runtime.state(
                    last_value=value,
                    last_error=error,
                    has_value=error is None and self._has_result,
                    retry_cause=retry_cause,
                    will_stop=True,
                ),
            )
        )

    async def _handle_exception(self, error: BaseException) -> bool:
        if not isinstance(error, Exception):
            return False
        ended_at = now()
        self.iterator._runtime.record_failure(
            started_at=self.attempt_started_at,
            ended_at=ended_at,
            error=error,
        )
        elapsed = ended_at - self.iterator.started_at
        should_retry = isinstance(error, TryAgain) or self.policy.condition.should_retry_exception(
            error
        )
        should_stop = self.policy.stop_strategy.should_stop(self.number, elapsed)
        self.policy.emit(
            RetryEvent(
                name="after_failure",
                attempt_number=self.number,
                function_name=self.iterator.name,
                error=error,
                state=self.iterator._runtime.state(
                    last_error=error,
                    retry_cause="exception",
                    will_retry=should_retry and not should_stop,
                    will_stop=should_stop,
                ),
            )
        )

        if not should_retry:
            self.iterator.finished = True
            self.iterator.result = self.iterator._runtime.result(ended_at=now(), error=error)
            self._giveup(error=error, retry_cause="exception")
            return False

        if should_stop:
            self.iterator.finished = True
            result = self.iterator._runtime.result(
                ended_at=now(),
                error=error,
                exhausted=True,
                retry_cause="exception",
            )
            self.iterator.result = result
            self._giveup(error=error, retry_cause="exception")
            return self._apply_exhausted(result, error)

        pre_sleep_state = self.iterator._runtime.state(
            last_error=error,
            retry_cause="exception",
            will_retry=True,
        )
        plan = plan_retry_wait(self.policy, self.number, pre_sleep_state)
        if should_stop_before_sleep(
            self.policy.stop_strategy, self.number, elapsed, plan.total_delay
        ):
            release_retry_wait(plan)
            self.iterator.finished = True
            result = self.iterator._runtime.result(
                ended_at=now(),
                error=error,
                exhausted=True,
                retry_cause="exception",
            )
            self.iterator.result = result
            self._giveup(error=error, retry_cause="exception")
            return self._apply_exhausted(result, error)

        self.policy.emit(
            RetryEvent(
                name="before_sleep",
                attempt_number=self.number,
                function_name=self.iterator.name,
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
            await self.policy.async_sleep(plan.total_delay)
        except BaseException:
            release_retry_wait(plan)
            raise
        return True

    async def _handle_success_or_result(self) -> bool:
        ended_at = now()
        value = self._result_value if self._has_result else None
        self.iterator._runtime.record_success(
            started_at=self.attempt_started_at,
            ended_at=ended_at,
            value=value,
            has_value=self._has_result,
        )
        should_retry = self._has_result and self.policy.condition.should_retry_result(value)
        elapsed = ended_at - self.iterator.started_at
        should_stop = self.policy.stop_strategy.should_stop(self.number, elapsed)

        if not should_retry:
            self.iterator.finished = True
            self.iterator.result = self.iterator._runtime.result(ended_at=now(), value=value)
            self.policy.emit(
                RetryEvent(
                    name="after_success",
                    attempt_number=self.number,
                    function_name=self.iterator.name,
                    value=value,
                    state=self.iterator._runtime.state(
                        last_value=value,
                        has_value=self._has_result,
                    ),
                )
            )
            return False

        if should_stop:
            self.iterator.finished = True
            result = self.iterator._runtime.result(
                ended_at=now(),
                value=value,
                exhausted=True,
                retry_cause="result",
            )
            self.iterator.result = result
            self._giveup(value=value, retry_cause="result")
            return self._apply_exhausted(result, None)

        pre_sleep_state = self.iterator._runtime.state(
            last_value=value,
            has_value=self._has_result,
            retry_cause="result",
            will_retry=True,
        )
        plan = plan_retry_wait(self.policy, self.number, pre_sleep_state)
        if should_stop_before_sleep(
            self.policy.stop_strategy, self.number, elapsed, plan.total_delay
        ):
            release_retry_wait(plan)
            self.iterator.finished = True
            result = self.iterator._runtime.result(
                ended_at=now(),
                value=value,
                exhausted=True,
                retry_cause="result",
            )
            self.iterator.result = result
            self._giveup(value=value, retry_cause="result")
            return self._apply_exhausted(result, None)

        self.policy.emit(
            RetryEvent(
                name="before_sleep",
                attempt_number=self.number,
                function_name=self.iterator.name,
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
            await self.policy.async_sleep(plan.total_delay)
        except BaseException:
            release_retry_wait(plan)
            raise
        return False
