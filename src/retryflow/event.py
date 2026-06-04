"""
Event objects and event names.

Events are RetryFlow's lightweight observability mechanism. They allow users to
connect logs, metrics, tracing, or custom debugging without coupling RetryFlow to
any external dependency.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal, TypeAlias

from retryflow.state import RetryState

EventName: TypeAlias = Literal[
    "before_attempt",
    "after_success",
    "after_failure",
    "before_sleep",
    "after_giveup",
]


@dataclass(frozen=True, slots=True)
class RetryEvent:
    """
    Runtime event emitted by RetryFlow.

    Attributes:
        name: Event name.
        attempt_number: Current attempt number.
        function_name: Name of the wrapped function.
        delay: Delay before next attempt, when applicable.
        value: Returned value, when applicable.
        error: Raised exception, when applicable.
        state: Rich immutable execution state.
    """

    name: EventName
    attempt_number: int
    function_name: str
    delay: float | None = None
    value: Any = None
    error: BaseException | None = None
    state: RetryState | None = None


EventHandler: TypeAlias = Callable[[RetryEvent], None]
