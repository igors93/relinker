"""Regression tests: non-callable targets and callbacks are rejected immediately."""

from __future__ import annotations

from functools import partial

import pytest

from relinker import InvalidRetryConfigError, RetryPolicy
from relinker.internal.callables import ensure_callable, ensure_retryable_callable

# ---------------------------------------------------------------------------
# ensure_callable helper
# ---------------------------------------------------------------------------


def test_ensure_callable_raises_for_int() -> None:
    with pytest.raises(InvalidRetryConfigError, match="must be callable.*int"):
        ensure_callable("myarg", 42)


def test_ensure_callable_raises_for_none() -> None:
    with pytest.raises(InvalidRetryConfigError, match="must be callable.*NoneType"):
        ensure_callable("myarg", None)


def test_ensure_callable_passes_for_function() -> None:
    ensure_callable("fn", lambda: None)


def test_ensure_callable_passes_for_class() -> None:
    class MyClass:
        pass

    ensure_callable("cls", MyClass)


def test_ensure_callable_passes_for_callable_object() -> None:
    class Callee:
        def __call__(self) -> None:
            pass

    ensure_callable("obj", Callee())


# ---------------------------------------------------------------------------
# ensure_retryable_callable raises for non-callables
# ---------------------------------------------------------------------------


def test_ensure_retryable_callable_raises_for_int() -> None:
    with pytest.raises(InvalidRetryConfigError, match="must be callable"):
        ensure_retryable_callable(42)


def test_ensure_retryable_callable_raises_for_string() -> None:
    with pytest.raises(InvalidRetryConfigError, match="must be callable"):
        ensure_retryable_callable("not a function")


def test_ensure_retryable_callable_passes_for_lambda() -> None:
    ensure_retryable_callable(lambda: None)


def test_ensure_retryable_callable_passes_for_partial() -> None:
    def fn(x: int) -> int:
        return x

    ensure_retryable_callable(partial(fn, 1))


def test_ensure_retryable_callable_passes_for_callable_object() -> None:
    class Callee:
        def __call__(self) -> int:
            return 1

    ensure_retryable_callable(Callee())


# ---------------------------------------------------------------------------
# policy.run rejects non-callables before first attempt
# ---------------------------------------------------------------------------


def test_run_non_callable_raises_before_attempt() -> None:
    events: list[str] = []
    policy = RetryPolicy().on_before_attempt(lambda e: events.append("attempt"))

    with pytest.raises(InvalidRetryConfigError, match="must be callable"):
        policy.run(42)  # type: ignore[arg-type]

    assert events == [], "no attempt should have been executed"


@pytest.mark.asyncio
async def test_run_async_non_callable_raises_before_attempt() -> None:
    events: list[str] = []
    policy = RetryPolicy().on_before_attempt(lambda e: events.append("attempt"))

    with pytest.raises(InvalidRetryConfigError, match="must be callable"):
        await policy.run_async(99)  # type: ignore[arg-type]

    assert events == [], "no attempt should have been executed"


# ---------------------------------------------------------------------------
# decorator on non-callable raises immediately
# ---------------------------------------------------------------------------


def test_decorator_on_non_callable_raises_immediately() -> None:
    policy = RetryPolicy()

    with pytest.raises(InvalidRetryConfigError, match="must be callable"):
        policy(42)  # type: ignore[operator]


# ---------------------------------------------------------------------------
# callback builders validate at construction time, not at call time
# ---------------------------------------------------------------------------


def test_retry_if_result_invalid_predicate_raises() -> None:
    with pytest.raises(InvalidRetryConfigError, match="predicate.*must be callable"):
        RetryPolicy().retry_if_result(99)  # type: ignore[arg-type]


def test_retry_if_invalid_callback_raises() -> None:
    with pytest.raises(InvalidRetryConfigError, match="callback.*must be callable"):
        RetryPolicy().retry_if("not callable")  # type: ignore[arg-type]


def test_custom_delay_invalid_callback_raises() -> None:
    with pytest.raises(InvalidRetryConfigError, match="callback.*must be callable"):
        RetryPolicy().custom_delay(None)  # type: ignore[arg-type]


def test_stateful_delay_invalid_callback_raises() -> None:
    with pytest.raises(InvalidRetryConfigError, match="callback.*must be callable"):
        RetryPolicy().stateful_delay(0)  # type: ignore[arg-type]


def test_on_event_invalid_handler_raises() -> None:
    with pytest.raises(InvalidRetryConfigError, match="handler.*must be callable"):
        RetryPolicy().on_event("before_attempt", "not callable")  # type: ignore[arg-type]


def test_with_sleep_invalid_raises() -> None:
    with pytest.raises(InvalidRetryConfigError, match="sleep.*must be callable"):
        RetryPolicy().with_sleep(42)  # type: ignore[arg-type]


def test_with_sleep_invalid_async_raises() -> None:
    with pytest.raises(InvalidRetryConfigError, match="async_sleep.*must be callable"):
        RetryPolicy().with_sleep(lambda _: None, async_sleep=99)  # type: ignore[arg-type]


def test_on_exhausted_return_invalid_callback_raises() -> None:
    with pytest.raises(InvalidRetryConfigError, match="callback.*must be callable"):
        RetryPolicy().on_exhausted_return("not callable")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# valid callables continue to work unchanged
# ---------------------------------------------------------------------------


def test_callable_object_sync_executes() -> None:
    class Work:
        def __call__(self) -> int:
            return 7

    result = RetryPolicy().run(Work())
    assert result == 7


def test_partial_sync_executes() -> None:
    def add(a: int, b: int) -> int:
        return a + b

    result = RetryPolicy().run(partial(add, 3), 4)
    assert result == 7


@pytest.mark.asyncio
async def test_async_callable_object_executes() -> None:
    class AsyncWork:
        async def __call__(self) -> int:
            return 5

    result = await RetryPolicy().run_async(AsyncWork())
    assert result == 5


def test_generator_raises_not_callable_error() -> None:
    def gen() -> None:
        yield

    with pytest.raises(InvalidRetryConfigError, match="Generator"):
        RetryPolicy().run(gen)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_async_generator_raises_not_callable_error() -> None:
    async def agen() -> None:
        yield

    with pytest.raises(InvalidRetryConfigError, match="Async generator"):
        await RetryPolicy().run_async(agen)  # type: ignore[arg-type]
