"""Asynchronous retry-block context managers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from relinker.context._shared import (
    _BaseRetryAttemptContext,
    _BaseRetryBlockIterator,
    _context_now,
)
from relinker.event import RetryEvent
from relinker.exceptions import TryAgain
from relinker.internal.executor_flow import state_with_wait_plan
from relinker.internal.exhaustion import should_stop_before_sleep
from relinker.internal.retry_wait import plan_retry_wait, release_retry_wait

if TYPE_CHECKING:
    from types import TracebackType


class AsyncRetryBlockIterator(_BaseRetryBlockIterator):
    """Asynchronous iterator that yields retry attempt context managers."""

    def __aiter__(self) -> AsyncRetryBlockIterator:
        return self

    async def __anext__(self) -> AsyncRetryAttemptContext:
        if self.finished:
            raise StopAsyncIteration
        self._begin_attempt()
        return AsyncRetryAttemptContext(self.policy, self)


class AsyncRetryAttemptContext(_BaseRetryAttemptContext):
    """Async context manager representing one retry attempt."""

    async def __aenter__(self) -> AsyncRetryAttemptContext:
        self.attempt_started_at = _context_now()
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

    async def _handle_exception(self, error: BaseException) -> bool:
        if not isinstance(error, Exception):
            return False
        ended_at = _context_now()
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
            self.iterator.result = self.iterator._runtime.result(
                ended_at=_context_now(), error=error
            )
            self._giveup(
                error=error,
                retry_cause="exception",
                will_stop=False,
            )
            return False

        if should_stop:
            self.iterator.finished = True
            result = self.iterator._runtime.result(
                ended_at=_context_now(),
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
            self.policy.stop_strategy,
            self.number,
            _context_now() - self.iterator.started_at,
            plan.total_delay,
        ):
            release_retry_wait(plan)
            self.iterator.finished = True
            result = self.iterator._runtime.result(
                ended_at=_context_now(),
                error=error,
                exhausted=True,
                retry_cause="exception",
            )
            self.iterator.result = result
            self._giveup(error=error, retry_cause="exception")
            return self._apply_exhausted(result, error)

        try:
            self.policy.emit(
                RetryEvent(
                    name="before_sleep",
                    attempt_number=self.number,
                    function_name=self.iterator.name,
                    delay=plan.total_delay,
                    error=error,
                    state=state_with_wait_plan(pre_sleep_state, plan),
                )
            )
        except BaseException:
            release_retry_wait(plan)
            raise

        if should_stop_before_sleep(
            self.policy.stop_strategy,
            self.number,
            _context_now() - self.iterator.started_at,
            plan.total_delay,
        ):
            release_retry_wait(plan)
            self.iterator.finished = True
            result = self.iterator._runtime.result(
                ended_at=_context_now(),
                error=error,
                exhausted=True,
                retry_cause="exception",
            )
            self.iterator.result = result
            self._giveup(error=error, retry_cause="exception")
            return self._apply_exhausted(result, error)

        try:
            await self.policy.async_sleep(plan.total_delay)
        except BaseException:
            release_retry_wait(plan)
            raise
        return True

    async def _handle_success_or_result(self) -> bool:
        ended_at = _context_now()
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
            self.iterator.result = self.iterator._runtime.result(
                ended_at=_context_now(), value=value
            )
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
                ended_at=_context_now(),
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
            self.policy.stop_strategy,
            self.number,
            _context_now() - self.iterator.started_at,
            plan.total_delay,
        ):
            release_retry_wait(plan)
            self.iterator.finished = True
            result = self.iterator._runtime.result(
                ended_at=_context_now(),
                value=value,
                exhausted=True,
                retry_cause="result",
            )
            self.iterator.result = result
            self._giveup(value=value, retry_cause="result")
            return self._apply_exhausted(result, None)

        try:
            self.policy.emit(
                RetryEvent(
                    name="before_sleep",
                    attempt_number=self.number,
                    function_name=self.iterator.name,
                    delay=plan.total_delay,
                    value=value,
                    state=state_with_wait_plan(pre_sleep_state, plan),
                )
            )
        except BaseException:
            release_retry_wait(plan)
            raise

        if should_stop_before_sleep(
            self.policy.stop_strategy,
            self.number,
            _context_now() - self.iterator.started_at,
            plan.total_delay,
        ):
            release_retry_wait(plan)
            self.iterator.finished = True
            result = self.iterator._runtime.result(
                ended_at=_context_now(),
                value=value,
                exhausted=True,
                retry_cause="result",
            )
            self.iterator.result = result
            self._giveup(value=value, retry_cause="result")
            return self._apply_exhausted(result, None)

        try:
            await self.policy.async_sleep(plan.total_delay)
        except BaseException:
            release_retry_wait(plan)
            raise
        return False
