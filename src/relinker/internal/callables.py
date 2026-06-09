"""Internal callable-kind validation helpers."""

from __future__ import annotations

import inspect
from collections.abc import Awaitable
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


def ensure_sync_retryable_callable(function: Any) -> None:
    """Reject callable kinds that cannot run through the synchronous entrypoint."""
    ensure_retryable_callable(function)
    if is_async_callable(function):
        raise InvalidRetryConfigError(
            "run() does not accept async callables; use await policy.run_async(...) instead"
        )


def ensure_awaitable_result(value: object) -> Awaitable[Any]:
    """Return an awaitable result or reject an invalid async execution contract."""
    if not inspect.isawaitable(value):
        raise InvalidRetryConfigError(
            "run_async() requires the callable to return an awaitable; "
            "use policy.run() for synchronous callables"
        )
    return value
