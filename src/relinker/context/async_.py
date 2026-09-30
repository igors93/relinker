"""Asynchronous retry-block context managers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from relinker.context._shared import _BaseRetryAttemptContext, _BaseRetryBlockIterator
from relinker.executors.async_ import async_sleep_before_retry
from relinker.internal.retry_wait import RetryWaitPlan

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
        self._enter()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool:
        del exc_type, traceback
        decision = self._decide(exc)
        if decision is None:
            return False
        if isinstance(decision, RetryWaitPlan):
            await async_sleep_before_retry(self.policy, decision)
            # Suppress the failed attempt's exception so the loop continues.
            return exc is not None
        return self.iterator._finish(decision, exc)
