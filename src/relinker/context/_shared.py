"""Shared state and helpers for retry-block context managers."""

from __future__ import annotations

from collections import deque
from typing import TYPE_CHECKING, Any

from relinker.attempt import AttemptRecord
from relinker.internal.executor_flow import FinalDecision, RetryFlow
from relinker.internal.exhaustion import finish_exhausted
from relinker.internal.retry_wait import RetryWaitPlan
from relinker.result import RetryResult

if TYPE_CHECKING:
    from relinker.policy import RetryPolicy


class _BaseRetryBlockIterator:
    """Shared state for sync and async retry-block iterators."""

    def __init__(
        self,
        policy: RetryPolicy[Any],
        *,
        name: str = "retry_block",
    ) -> None:
        self.policy = policy
        self.name = name
        self._flow = RetryFlow(policy, function_name=name)
        self.finished = False
        self.result: RetryResult[Any] | None = None
        self.outcome: Any = None
        self.has_outcome = False

    @property
    def started_at(self) -> float:
        return self._flow.runtime.started_at

    @property
    def attempts(self) -> deque[AttemptRecord]:
        return self._flow.runtime.attempts

    @property
    def attempt_number(self) -> int:
        return self._flow.runtime.attempt_number

    def _begin_attempt(self) -> int:
        """Start and return the next attempt number."""
        return self._flow.next_attempt()

    def _finish(self, decision: FinalDecision, current_error: BaseException | None) -> bool:
        """Store a terminal decision; return True when ``current_error`` is suppressed."""
        self.finished = True
        self.result = decision.result
        if decision.kind != "exhaust":
            return False
        try:
            self.outcome = finish_exhausted(self.policy, decision.result)
        except BaseException as exc:
            if current_error is not None and exc is current_error:
                # Let the original exception propagate from the with-block.
                return False
            raise
        self.has_outcome = True
        return current_error is not None


class _BaseRetryAttemptContext:
    """Shared state and helpers for sync and async retry attempt contexts."""

    def __init__(
        self,
        policy: RetryPolicy[Any],
        iterator: _BaseRetryBlockIterator,
    ) -> None:
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

    def _enter(self) -> None:
        flow = self.iterator._flow
        flow.enter_attempt()
        self.attempt_started_at = flow.attempt_started_at

    def _decide(self, error: BaseException | None) -> RetryWaitPlan | FinalDecision | None:
        """Return the decision for this attempt; None lets a BaseException propagate."""
        flow = self.iterator._flow
        if error is not None:
            if not isinstance(error, Exception):
                return None
            return flow.after_exception(error)
        return flow.after_value(self._result_value, has_value=self._has_result)
