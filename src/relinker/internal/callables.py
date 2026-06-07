"""Internal callable-kind validation helpers."""

from __future__ import annotations

import inspect
from functools import partial
from typing import Any

from relinker.exceptions import InvalidRetryConfigError


def _unwrap_partial(function: Any) -> Any:
    current = inspect.unwrap(function)
    while isinstance(current, partial):
        current = inspect.unwrap(current.func)
    return current


def is_async_callable(function: Any) -> bool:
    """Return True when calling ``function`` produces an awaitable contract."""
    target = _unwrap_partial(function)
    if inspect.isclass(target):
        return False

    if inspect.iscoroutinefunction(target):
        return True

    if not callable(target):
        return False

    call = type(target).__call__
    return inspect.iscoroutinefunction(_unwrap_partial(call))


def ensure_retryable_callable(function: Any) -> None:
    """Reject callable kinds that Relinker cannot retry safely."""
    target = _unwrap_partial(function)
    if inspect.isgeneratorfunction(target):
        raise InvalidRetryConfigError(
            "Generator functions are not supported; use a factory that returns a fresh "
            "generator inside a retried function."
        )
    if inspect.isasyncgenfunction(target):
        raise InvalidRetryConfigError(
            "Async generator functions are not supported; use a factory that returns a fresh "
            "async generator inside a retried function."
        )

    if inspect.isclass(target):
        return

    if not callable(target):
        return

    call = type(target).__call__
    call_target = _unwrap_partial(call)
    if inspect.isgeneratorfunction(call_target):
        raise InvalidRetryConfigError(
            "Generator functions are not supported; use a factory that returns a fresh "
            "generator inside a retried function."
        )
    if inspect.isasyncgenfunction(call_target):
        raise InvalidRetryConfigError(
            "Async generator functions are not supported; use a factory that returns a fresh "
            "async generator inside a retried function."
        )
