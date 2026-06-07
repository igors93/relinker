"""
Public retry decorator.

This module provides the easiest entry point for users who do not need to build
a full RetryPolicy manually.
"""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import Any, Literal, Protocol, overload

from relinker.policy import RetryPolicy
from relinker.result import RetryResult
from relinker.typing import P, RetryWrappedFunction, T


class _RawRetryDecorator(Protocol):
    def __call__(self, function: Callable[P, T]) -> RetryWrappedFunction[P, T]: ...


class _ReturnResultRetryDecorator(Protocol):
    @overload
    def __call__(  # type: ignore[overload-overlap]
        self,
        function: Callable[P, Coroutine[Any, Any, T]],
    ) -> RetryWrappedFunction[P, Coroutine[Any, Any, RetryResult[T]]]: ...

    @overload
    def __call__(self, function: Callable[P, T]) -> RetryWrappedFunction[P, RetryResult[T]]: ...


class _DynamicRetryDecorator(Protocol):
    @overload
    def __call__(
        self,
        function: Callable[P, Coroutine[Any, Any, T]],
    ) -> RetryWrappedFunction[P, Coroutine[Any, Any, T | RetryResult[T]]]: ...

    @overload
    def __call__(self, function: Callable[P, T]) -> RetryWrappedFunction[P, T | RetryResult[T]]: ...


@overload
def retry(function: Callable[P, T]) -> RetryWrappedFunction[P, T]: ...


@overload
def retry(
    *,
    attempts: int = 3,
    delay: float = 0.0,
    on: tuple[type[BaseException], ...] = (Exception,),
    return_result: Literal[False] = False,
) -> _RawRetryDecorator: ...


@overload
def retry(  # type: ignore[overload-overlap]
    *,
    attempts: int = 3,
    delay: float = 0.0,
    on: tuple[type[BaseException], ...] = (Exception,),
    return_result: Literal[True],
) -> _ReturnResultRetryDecorator: ...


@overload
def retry(
    *,
    attempts: int = 3,
    delay: float = 0.0,
    on: tuple[type[BaseException], ...] = (Exception,),
    return_result: bool,
) -> _DynamicRetryDecorator: ...


def retry(
    function: Callable[..., Any] | None = None,
    *,
    attempts: int = 3,
    delay: float = 0.0,
    on: tuple[type[BaseException], ...] = (Exception,),
    return_result: bool = False,
) -> Any:
    """
    Retry decorator with a simple API.

    It supports both styles:

        @retry
        def task(): ...

        @retry(attempts=5, delay=1, on=(TimeoutError,))
        def task(): ...
    """
    policy: RetryPolicy[Any] = RetryPolicy().attempts(attempts).fixed_delay(delay).on(*on)

    if return_result:
        policy = policy.return_result()

    if function is not None:
        return policy(function)

    return policy
