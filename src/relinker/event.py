"""
Event objects and event names.

Events are Relinker's lightweight observability mechanism. They allow users to
connect logs, metrics, tracing, or custom debugging without coupling Relinker to
any external dependency.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from typing import Any, Literal, TypeAlias

from relinker.state import RetryState

EventName: TypeAlias = Literal[
    "before_attempt",
    "after_success",
    "after_failure",
    "before_sleep",
    "after_giveup",
]
EventFailureMode: TypeAlias = Literal["propagate", "isolate"]


@dataclass(frozen=True, slots=True)
class RetryEvent:
    """
    Runtime event emitted by Relinker.

    Attributes:
        name: Event name.
        attempt_number: Current attempt number.
        function_name: Name of the wrapped function.
        delay: Delay before next attempt, when applicable.
        value: Returned value, when applicable.
        error: Raised exception, when applicable.
        state: Rich immutable execution state.

    Security note:
        ``value`` and ``error`` are excluded from ``repr()`` because they may
        contain secrets, tokens, or sensitive user data.
    """

    name: EventName
    attempt_number: int
    function_name: str
    delay: float | None = None
    value: Any = field(default=None, repr=False)
    error: BaseException | None = field(default=None, repr=False)
    state: RetryState | None = None
    policy_name: str | None = None


EventHandler: TypeAlias = Callable[[RetryEvent], None]


@dataclass(frozen=True, slots=True)
class EventHandlerRegistration:
    """Immutable internal registration for one event handler."""

    name: EventName
    handler: EventHandler
    failure_mode: EventFailureMode = "propagate"

    def __iter__(self) -> Iterator[object]:
        """Preserve tuple-unpacking compatibility for existing internal helpers."""
        yield self.name
        yield self.handler
