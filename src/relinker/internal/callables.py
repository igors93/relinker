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


def ensure_callable(name: str, value: Any) -> None:
    """Raise when value is not callable."""
    if not callable(value):
        raise InvalidRetryConfigError(f"{name} must be callable, got {type(value).__name__}")


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
        raise InvalidRetryConfigError(f"function must be callable, got {type(target).__name__}")

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


def ensure_sync_sleeper(sleep: Any) -> None:
    """Raise when sleep is not valid for the synchronous execution path.

    Accepts: sync callables (functions, methods, partials, callable objects).
    Rejects: coroutine functions, async callable objects (they create unawaited
    coroutines in the sync executor).
    """
    if not callable(sleep):
        raise InvalidRetryConfigError(f"sleep must be callable, got {type(sleep).__name__}")
    if is_async_callable(sleep):
        raise InvalidRetryConfigError(
            "sync sleep must not be an async callable; "
            "pass an async sleep function as the second argument to with_sleep()"
        )


def _try_bind(sig: inspect.Signature, *args: Any) -> bool:
    """Return True if sig.bind(*args) succeeds without raising TypeError."""
    try:
        sig.bind(*args)
        return True
    except TypeError:
        return False


def _exception_class_call_mode(exception_type: type[BaseException], message: str) -> str:
    """Return 'message', 'no-arg', or raise InvalidRetryConfigError.

    Only checks the signature; does NOT call the constructor.
    For built-ins without inspectable signatures, returns 'unknown' as a
    best-effort (caller must try both).
    """
    try:
        sig = inspect.signature(exception_type)
    except (ValueError, TypeError):
        return "unknown"

    if _try_bind(sig, message):
        return "message"
    if _try_bind(sig):
        return "no-arg"
    raise InvalidRetryConfigError(
        f"{exception_type.__name__} cannot be instantiated with a message or no "
        "arguments; use on_exhausted_raise(factory) instead"
    )


def validate_exception_class(exception_type: type[BaseException], message: str) -> None:
    """Raise InvalidRetryConfigError early if the class cannot accept message or no args.

    Only performs signature inspection — does NOT call the constructor.
    This provides early feedback at policy-construction time.
    """
    _exception_class_call_mode(exception_type, message)


def instantiate_exception_class(exception_type: type[BaseException], message: str) -> BaseException:
    """Instantiate an exception class with appropriate argument passing.

    Strategy:
    1. If the class accepts a positional message, construct with ``message``.
    2. If the class accepts zero arguments, construct with no arguments.
    3. Otherwise raise InvalidRetryConfigError directing the user to use a factory.

    Does not catch TypeError raised from inside the constructor body — that is a
    programming error in the exception class, not a signature mismatch.
    """
    mode = _exception_class_call_mode(exception_type, message)

    if mode == "message":
        instance = exception_type(message)
    elif mode == "no-arg":
        instance = exception_type()
    else:
        # mode == "unknown" — built-in without inspectable signature; try message first
        try:
            instance = exception_type(message)
        except TypeError:
            try:
                instance = exception_type()
            except TypeError:
                raise InvalidRetryConfigError(
                    f"{exception_type.__name__} cannot be instantiated with a message or no "
                    "arguments; use on_exhausted_raise(factory) instead"
                ) from None

    if not isinstance(instance, BaseException):
        raise InvalidRetryConfigError(f"{exception_type.__name__} did not return a BaseException")
    return instance


def ensure_awaitable_sleep_result(result: Any, seconds: float) -> Awaitable[Any]:
    """Return ``result`` if it is awaitable, or raise InvalidRetryConfigError.

    Called at runtime after invoking the async sleeper to catch sync functions
    that return non-awaitables (e.g. None or a number) before the 'await'
    expression, which would otherwise raise a bare TypeError.

    When ``result`` is a coroutine that was created but will never be awaited
    (a programming error), close it to suppress the RuntimeWarning.
    """
    if inspect.isawaitable(result):
        return result

    # If somehow a coroutine was created but is not awaitable (impossible in practice,
    # but be defensive), close it to avoid the RuntimeWarning.
    if inspect.iscoroutine(result):
        result.close()

    raise InvalidRetryConfigError(
        f"async_sleep must return an awaitable, got {type(result).__name__}; "
        "use an async function or a function that returns a coroutine/future"
    )
