"""
Public retry decorator.

This module provides the easiest entry point for users who do not need to build
a full RetryPolicy manually.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, overload

from retryflow.policy import RetryPolicy
from retryflow.typing import P, T


@overload
def retry(function: Callable[P, T]) -> Callable[P, T]:
    ...


@overload
def retry(
    *,
    attempts: int = 3,
    delay: float = 0.0,
    on: tuple[type[BaseException], ...] = (Exception,),
    return_result: bool = False,
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    ...


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
    policy = RetryPolicy().attempts(attempts).fixed_delay(delay).on(*on)

    if return_result:
        policy = policy.return_result()

    if function is not None:
        return policy(function)

    return policy
