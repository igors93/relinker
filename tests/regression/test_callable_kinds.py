"""Regression contracts for callable kinds that Relinker can safely wrap."""

from __future__ import annotations

import inspect
from functools import partial, wraps
from typing import Any

import pytest

from relinker import InvalidRetryConfigError, RetryBudget, RetryPolicy, retry


def generator_task():
    yield 1
    raise OSError("stream failed")


async def async_generator_task():
    yield 1
    raise OSError("async stream failed")


def test_policy_rejects_generator_function_before_consuming_stream() -> None:
    policy = RetryPolicy().attempts(2).on(OSError)

    with pytest.raises(InvalidRetryConfigError, match="Generator functions are not supported"):
        policy(generator_task)


def test_retry_decorator_rejects_generator_function_before_consuming_stream() -> None:
    with pytest.raises(InvalidRetryConfigError, match="Generator functions are not supported"):
        retry(attempts=2, delay=0, on=(OSError,))(generator_task)


def test_policy_rejects_async_generator_function_before_consuming_stream() -> None:
    policy = RetryPolicy().attempts(2).on(OSError)

    with pytest.raises(
        InvalidRetryConfigError,
        match="Async generator functions are not supported",
    ):
        policy(async_generator_task)


def test_run_rejects_generator_function_before_returning_unprotected_generator() -> None:
    policy = RetryPolicy().attempts(2).on(OSError)

    with pytest.raises(InvalidRetryConfigError, match="Generator functions are not supported"):
        policy.run(generator_task)


def test_run_rejects_async_function_before_starting_execution() -> None:
    events: list[str] = []

    async def async_task() -> str:
        return "ok"

    policy = RetryPolicy().on_before_attempt(lambda event: events.append(event.name))

    with pytest.raises(
        InvalidRetryConfigError,
        match=r"run\(\) does not accept async callables.*run_async",
    ):
        result = policy.run(async_task)
        if inspect.iscoroutine(result):
            result.close()

    assert events == []


def test_run_rejects_async_callable_object() -> None:
    class AsyncCallable:
        async def __call__(self) -> str:
            return "ok"

    with pytest.raises(
        InvalidRetryConfigError,
        match=r"run\(\) does not accept async callables.*run_async",
    ):
        result = RetryPolicy().run(AsyncCallable())
        if inspect.iscoroutine(result):
            result.close()


def test_run_rejects_partial_async_callable_object() -> None:
    class AsyncOperation:
        async def __call__(self, value: int) -> int:
            return value + 1

    operation = partial(AsyncOperation(), 1)

    with pytest.raises(
        InvalidRetryConfigError,
        match=r"run\(\) does not accept async callables.*run_async",
    ):
        result = RetryPolicy().run(operation)
        if inspect.iscoroutine(result):
            result.close()


@pytest.mark.asyncio
async def test_run_async_rejects_non_awaitable_result_without_retrying() -> None:
    calls = 0
    events: list[str] = []
    sleeps: list[float] = []

    def sync_task() -> str:
        nonlocal calls
        calls += 1
        return "ok"

    async def capture_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    policy = (
        RetryPolicy()
        .attempts(5)
        .on(Exception)
        .with_sleep(
            lambda seconds: sleeps.append(seconds),
            async_sleep=capture_sleep,
        )
    )
    for event_name in (
        "before_attempt",
        "after_failure",
        "before_sleep",
        "after_giveup",
    ):
        policy = policy.on_event(event_name, lambda event: events.append(event.name))

    with pytest.raises(
        InvalidRetryConfigError,
        match=r"run_async\(\).*return an awaitable.*run\(\)",
    ):
        await policy.run_async(sync_task)

    assert calls == 1
    assert events == ["before_attempt"]
    assert sleeps == []


@pytest.mark.asyncio
async def test_run_async_non_awaitable_result_bypasses_fallback_and_retry_budget() -> None:
    calls = 0
    budget = RetryBudget(max_retries=2, per=60)

    def sync_task() -> str:
        nonlocal calls
        calls += 1
        return "ok"

    policy = (
        RetryPolicy()
        .attempts(3)
        .on(Exception)
        .fallback_value("fallback")
        .with_retry_budget(budget, key="non-awaitable")
        .for_testing()
    )

    with pytest.raises(InvalidRetryConfigError, match=r"run_async\(\).*awaitable"):
        await policy.run_async(sync_task)

    assert calls == 1
    snapshot = budget.snapshot("non-awaitable")
    assert snapshot.active == 0
    assert snapshot.queued == 0
    assert snapshot.available_now == 2


@pytest.mark.asyncio
async def test_run_async_accepts_sync_factory_returning_coroutine() -> None:
    async def async_task() -> str:
        return "ok"

    def factory():
        return async_task()

    assert await RetryPolicy().run_async(factory) == "ok"


@pytest.mark.asyncio
async def test_run_async_retries_sync_factory_exception_before_awaitable_creation() -> None:
    calls = 0

    async def async_task() -> str:
        return "ok"

    def factory():
        nonlocal calls
        calls += 1
        if calls == 1:
            raise TimeoutError("temporary")
        return async_task()

    result = await RetryPolicy().attempts(2).on(TimeoutError).for_testing().run_async(factory)

    assert result == "ok"
    assert calls == 2


def test_sync_callable_object_executes_as_sync_wrapper() -> None:
    class SyncCallable:
        def __call__(self, value: int) -> int:
            return value + 1

    wrapped = RetryPolicy().attempts(2)(SyncCallable())

    assert not inspect.iscoroutinefunction(wrapped)
    assert wrapped(1) == 2


@pytest.mark.asyncio
async def test_async_callable_object_executes_as_async_wrapper() -> None:
    class AsyncCallable:
        async def __call__(self, value: int) -> int:
            return value + 1

    wrapped = RetryPolicy().attempts(2)(AsyncCallable())

    assert inspect.iscoroutinefunction(wrapped)
    assert await wrapped(1) == 2


@pytest.mark.asyncio
async def test_async_partial_executes_as_async_wrapper() -> None:
    async def add(left: int, right: int) -> int:
        return left + right

    wrapped = RetryPolicy().attempts(2)(partial(add, 1))

    assert inspect.iscoroutinefunction(wrapped)
    assert await wrapped(2) == 3


@pytest.mark.asyncio
async def test_partial_async_callable_object_retries_as_async_wrapper() -> None:
    class AsyncOperation:
        def __init__(self) -> None:
            self.calls = 0

        async def __call__(self, value: int) -> int:
            self.calls += 1
            if self.calls == 1:
                raise OSError("temporary")
            return value + 1

    operation = AsyncOperation()
    wrapped = RetryPolicy().attempts(2).on(OSError).for_testing()(partial(operation, 1))

    assert inspect.iscoroutinefunction(wrapped)
    assert await wrapped() == 2
    assert operation.calls == 2

    snapshot = wrapped.retry_stats.snapshot()
    assert snapshot.calls == 1
    assert snapshot.successes == 1
    assert snapshot.failures == 0
    assert snapshot.total_attempts == 2


def test_partial_sync_callable_object_executes_as_sync_wrapper() -> None:
    class SyncOperation:
        def __call__(self, left: int, right: int) -> int:
            return left + right

    wrapped = RetryPolicy().attempts(2)(partial(SyncOperation(), 1))

    assert not inspect.iscoroutinefunction(wrapped)
    assert wrapped(2) == 3


def test_partial_generator_callable_object_is_rejected() -> None:
    class GeneratorOperation:
        def __call__(self) -> Any:
            yield 1

    with pytest.raises(InvalidRetryConfigError, match="Generator functions are not supported"):
        RetryPolicy().attempts(2)(partial(GeneratorOperation()))


def test_partial_async_generator_callable_object_is_rejected() -> None:
    class AsyncGeneratorOperation:
        async def __call__(self) -> Any:
            yield 1

    with pytest.raises(
        InvalidRetryConfigError,
        match="Async generator functions are not supported",
    ):
        RetryPolicy().attempts(2)(partial(AsyncGeneratorOperation()))


@pytest.mark.asyncio
async def test_nested_partial_async_callable_object_executes_as_async_wrapper() -> None:
    class AsyncOperation:
        async def __call__(self, left: int, right: int) -> int:
            return left + right

    operation = partial(partial(AsyncOperation(), 1), right=2)
    wrapped = RetryPolicy().attempts(2)(operation)

    assert inspect.iscoroutinefunction(wrapped)
    assert await wrapped() == 3


def test_partial_callable_class_is_not_classified_as_async() -> None:
    class CallableClass:
        def __init__(self, value: int) -> None:
            self.value = value

        def __call__(self) -> int:
            return self.value

    wrapped = RetryPolicy().attempts(2)(partial(CallableClass, 3))

    instance = wrapped()
    assert not inspect.iscoroutinefunction(wrapped)
    assert isinstance(instance, CallableClass)
    assert instance() == 3


@pytest.mark.asyncio
async def test_wrapped_async_function_executes_as_async_wrapper() -> None:
    def preserving_decorator(function):
        @wraps(function)
        def wrapper(*args, **kwargs):
            return function(*args, **kwargs)

        return wrapper

    @preserving_decorator
    async def async_task(value: int) -> int:
        return value + 1

    wrapped = RetryPolicy().attempts(2)(async_task)

    assert inspect.iscoroutinefunction(wrapped)
    assert await wrapped(1) == 2


def test_callable_class_is_not_classified_from_inherited_type_call() -> None:
    class CallableClass:
        def __init__(self, value: int) -> None:
            self.value = value

        def __call__(self) -> int:
            return self.value

    wrapped = RetryPolicy().attempts(2)(CallableClass)

    instance = wrapped(3)
    assert isinstance(instance, CallableClass)
    assert instance() == 3
