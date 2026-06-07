"""Regression contracts for callable kinds that Relinker can safely wrap."""

from __future__ import annotations

import inspect
from functools import partial, wraps
from typing import Any

import pytest

from relinker import InvalidRetryConfigError, RetryPolicy, retry


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
