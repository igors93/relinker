"""Helpers shared by executors and retry-block context managers."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from relinker.attempt import AttemptRecord
from relinker.internal.clock import now
from relinker.state import RetryCause, RetryState


def normalize_retry_cause(retry_cause: str | None) -> RetryCause | None:
    """Return a RetryCause literal value accepted by type checkers."""
    if retry_cause == "exception":
        return "exception"
    if retry_cause == "result":
        return "result"
    return None


def function_name(function: object) -> str:
    """Return a readable name for events and diagnostics."""
    return getattr(function, "__name__", function.__class__.__name__)


def build_state(
    *,
    function_name: str,
    attempt_number: int,
    started_at: float,
    attempts: Iterable[AttemptRecord],
    last_value: Any = None,
    last_error: BaseException | None = None,
    has_value: bool = False,
    next_delay: float | None = None,
    retry_cause: str | None = None,
    will_retry: bool = False,
    will_stop: bool = False,
    policy_delay: float | None = None,
    budget_delay: float | None = None,
    policy_name: str | None = None,
    total_attempts: int = 0,
    total_failed_attempts: int | None = None,
    total_successful_attempts: int | None = None,
) -> RetryState:
    """Build an immutable runtime state snapshot."""
    return RetryState(
        function_name=function_name,
        attempt_number=attempt_number,
        started_at=started_at,
        elapsed=now() - started_at,
        attempts=tuple(attempts),
        last_value=last_value,
        last_error=last_error,
        has_value=has_value,
        next_delay=next_delay,
        retry_cause=normalize_retry_cause(retry_cause),
        will_retry=will_retry,
        will_stop=will_stop,
        policy_delay=policy_delay,
        budget_delay=budget_delay,
        policy_name=policy_name,
        total_attempts=total_attempts,
        total_failed_attempts=total_failed_attempts,
        total_successful_attempts=total_successful_attempts,
    )
