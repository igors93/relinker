"""Shared mutable runtime bookkeeping for retry executions."""

from __future__ import annotations

from collections import deque
from typing import Any

from relinker.attempt import AttemptRecord
from relinker.internal.executor_helpers import build_state, normalize_retry_cause
from relinker.result import RetryResult
from relinker.state import RetryState


class RetryRuntime:
    """Track attempts, aggregate counters, state snapshots, and final results."""

    def __init__(
        self,
        *,
        function_name: str,
        started_at: float,
        history_limit: int | None,
    ) -> None:
        self.function_name = function_name
        self.started_at = started_at
        self.attempts: deque[AttemptRecord] = deque(maxlen=history_limit)
        self.attempt_number = 0
        self.failed_count = 0
        self.success_count = 0

    def begin_attempt(self) -> int:
        """Start and return the next one-based attempt number."""
        self.attempt_number += 1
        return self.attempt_number

    def record_success(
        self,
        *,
        started_at: float,
        ended_at: float,
        value: Any = None,
        has_value: bool = True,
    ) -> AttemptRecord:
        record = AttemptRecord(
            number=self.attempt_number,
            started_at=started_at,
            ended_at=ended_at,
            value=value,
            has_value=has_value,
        )
        self.attempts.append(record)
        self.success_count += 1
        return record

    def record_failure(
        self,
        *,
        started_at: float,
        ended_at: float,
        error: BaseException,
    ) -> AttemptRecord:
        record = AttemptRecord(
            number=self.attempt_number,
            started_at=started_at,
            ended_at=ended_at,
            error=error,
        )
        self.attempts.append(record)
        self.failed_count += 1
        return record

    def state(
        self,
        *,
        last_value: Any = None,
        last_error: BaseException | None = None,
        has_value: bool = False,
        next_delay: float | None = None,
        retry_cause: str | None = None,
        will_retry: bool = False,
        will_stop: bool = False,
        policy_delay: float | None = None,
        budget_delay: float | None = None,
    ) -> RetryState:
        return build_state(
            function_name=self.function_name,
            attempt_number=self.attempt_number,
            started_at=self.started_at,
            attempts=self.attempts,
            last_value=last_value,
            last_error=last_error,
            has_value=has_value,
            next_delay=next_delay,
            retry_cause=retry_cause,
            will_retry=will_retry,
            will_stop=will_stop,
            policy_delay=policy_delay,
            budget_delay=budget_delay,
        )

    def result(
        self,
        *,
        ended_at: float,
        value: Any = None,
        error: BaseException | None = None,
        exhausted: bool = False,
        retry_cause: str | None = None,
    ) -> RetryResult[Any]:
        return RetryResult(
            attempts=tuple(self.attempts),
            value=value,
            error=error,
            started_at=self.started_at,
            ended_at=ended_at,
            exhausted=exhausted,
            retry_cause=normalize_retry_cause(retry_cause),
            total_attempts=self.attempt_number,
            total_failed_attempts=self.failed_count,
            total_successful_attempts=self.success_count,
        )
