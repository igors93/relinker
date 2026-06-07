"""Regression contracts for callable kinds that Relinker can safely wrap."""

from __future__ import annotations

import inspect
from functools import partial, wraps

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

    wrapped = RetryPolicy[int]().attempts(2)(SyncCallable())

    assert not inspect.iscoroutinefunction(wrapped)
    assert wrapped(1) == 2


@pytest.mark.asyncio
async def test_async_callable_object_executes_as_async_wrapper() -> None:
    class AsyncCallable:
        async def __call__(self, value: int) -> int:
            return value + 1

    wrapped = RetryPolicy[int]().attempts(2)(AsyncCallable())

    assert inspect.iscoroutinefunction(wrapped)
    assert await wrapped(1) == 2


@pytest.mark.asyncio
async def test_async_partial_executes_as_async_wrapper() -> None:
    async def add(left: int, right: int) -> int:
        return left + right

    wrapped = RetryPolicy[int]().attempts(2)(partial(add, 1))

    assert inspect.iscoroutinefunction(wrapped)
    assert await wrapped(2) == 3


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

    wrapped = RetryPolicy[int]().attempts(2)(async_task)

    assert inspect.iscoroutinefunction(wrapped)
    assert await wrapped(1) == 2


def test_callable_class_is_not_classified_from_inherited_type_call() -> None:
    class CallableClass:
        def __init__(self, value: int) -> None:
            self.value = value

        def __call__(self) -> int:
            return self.value

    wrapped = RetryPolicy[CallableClass]().attempts(2)(CallableClass)

    instance = wrapped(3)
    assert isinstance(instance, CallableClass)
    assert instance() == 3
