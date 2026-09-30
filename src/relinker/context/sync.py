"""Synchronous retry-block context managers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from relinker.context._shared import _BaseRetryAttemptContext, _BaseRetryBlockIterator
from relinker.executors.sync import sleep_before_retry
from relinker.internal.retry_wait import RetryWaitPlan

if TYPE_CHECKING:
    from types import TracebackType


class RetryBlockIterator(_BaseRetryBlockIterator):
    """Synchronous iterator that yields retry attempt context managers."""

    def __iter__(self) -> RetryBlockIterator:
        return self

    def __next__(self) -> RetryAttemptContext:
        if self.finished:
            raise StopIteration
        self._begin_attempt()
        return RetryAttemptContext(self.policy, self)


class RetryAttemptContext(_BaseRetryAttemptContext):
    """Context manager representing one synchronous retry attempt."""

    def __enter__(self) -> RetryAttemptContext:
        self._enter()
        return self

    def __exit__(
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
            sleep_before_retry(self.policy, decision)
            # Suppress the failed attempt's exception so the loop continues.
            return exc is not None
        return self.iterator._finish(decision, exc)
