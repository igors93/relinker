"""
Shared helpers for sync/async executors and context managers.

Centralises the three functions that would otherwise be duplicated verbatim
in execute_sync, execute_async, and the context manager module.
"""

from __future__ import annotations

from collections import deque
from typing import TYPE_CHECKING, Any

from relinker.internal.clock import now

if TYPE_CHECKING:
    from collections.abc import Callable

    from relinker.attempt import AttemptRecord
    from relinker.state import RetryCause, RetryState


def function_name(function: Callable[..., Any]) -> str:
    """Return a readable function name for events and debug output."""
    return getattr(function, "__name__", function.__class__.__name__)


def normalize_retry_cause(retry_cause: str | None) -> RetryCause | None:
    """Return a RetryCause literal accepted by type checkers."""
    if retry_cause == "exception":
        return "exception"
    if retry_cause == "result":
        return "result"
    return None


def build_state(
    *,
    function_name: str,
    attempt_number: int,
    started_at: float,
    attempts: deque[AttemptRecord],
    last_value: Any = None,
    last_error: BaseException | None = None,
    has_value: bool = False,
    next_delay: float | None = None,
    retry_cause: str | None = None,
    will_retry: bool = False,
    will_stop: bool = False,
) -> RetryState:
    """Build an immutable state snapshot for retry events."""
    from relinker.state import RetryState

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
    )
