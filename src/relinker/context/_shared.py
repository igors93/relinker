"""Shared state and helpers for retry-block context managers."""

from __future__ import annotations

import importlib
from collections import deque
from typing import TYPE_CHECKING, Any, cast

from relinker.attempt import AttemptRecord
from relinker.event import RetryEvent
from relinker.internal.exhaustion import finish_exhausted
from relinker.internal.runtime import RetryRuntime
from relinker.result import RetryResult

if TYPE_CHECKING:
    from relinker.policy import RetryPolicy


def _context_now() -> float:
    context = cast(Any, importlib.import_module("relinker.context"))

    return cast(float, context.now())


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
        self._runtime = RetryRuntime(
            function_name=name,
            started_at=_context_now(),
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

    def _begin_attempt(self) -> int:
        """Start and return the next attempt number."""
        return self._runtime.begin_attempt()

    def _apply_exhausted(
        self,
        result: RetryResult[Any],
        current_error: BaseException | None,
    ) -> bool:
        try:
            resolved = finish_exhausted(self.policy, result)
            self.outcome = resolved
            self.has_outcome = True
            return current_error is not None
        except BaseException as exc:
            if current_error is not None and exc is current_error:
                return False
            raise

    def _emit_giveup(
        self,
        *,
        attempt_number: int,
        has_value: bool,
        value: Any = None,
        error: BaseException | None = None,
        retry_cause: str,
    ) -> None:
        self.policy.emit(
            RetryEvent(
                name="after_giveup",
                attempt_number=attempt_number,
                function_name=self.name,
                value=value,
                error=error,
                state=self._runtime.state(
                    last_value=value,
                    last_error=error,
                    has_value=has_value,
                    retry_cause=retry_cause,
                    will_stop=True,
                ),
            )
        )


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

    def _apply_exhausted(
        self,
        result: RetryResult[Any],
        current_error: BaseException | None,
    ) -> bool:
        return self.iterator._apply_exhausted(result, current_error)

    def _giveup(
        self,
        *,
        value: Any = None,
        error: BaseException | None = None,
        retry_cause: str,
    ) -> None:
        self.iterator._emit_giveup(
            attempt_number=self.number,
            value=value,
            error=error,
            has_value=error is None and self._has_result,
            retry_cause=retry_cause,
        )
