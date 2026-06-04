"""
Shared typing utilities for Relinker.

Keeping type helpers in one module avoids duplication and makes the public code
easier to read.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any, ParamSpec, Protocol, TypeAlias, TypeVar, runtime_checkable

if TYPE_CHECKING:
    from relinker.policy import RetryPolicy
    from relinker.stats import RetryStats

P = ParamSpec("P")
T = TypeVar("T")

SyncCallable: TypeAlias = Callable[P, T]
AsyncCallable: TypeAlias = Callable[P, Awaitable[T]]
AnyCallable: TypeAlias = Callable[..., Any]

ExceptionTypes: TypeAlias = tuple[type[BaseException], ...]


@runtime_checkable
class RetryWrappedFunction(Protocol):
    """
    Protocol describing a function decorated by Relinker.

    Decorated functions gain three extra attributes that Relinker attaches
    at decoration time. This Protocol lets type checkers and IDE tooling
    understand those attributes.

    Example:
        @policy
        def task() -> str: ...

        task.retry_stats.snapshot()
        task.retry_policy.explain()
        strict_task = task.with_policy(policy.attempts(10))
    """

    retry_stats: RetryStats
    retry_policy: RetryPolicy[Any]

    def with_policy(self, policy: RetryPolicy[Any]) -> RetryWrappedFunction:
        """Return a new wrapped version of the same function with a different policy."""
        ...

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        """Call the wrapped function."""
        ...
