"""
Shared typing utilities for RetryFlow.

Keeping type helpers in one module avoids duplication and makes the public code
easier to read.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, ParamSpec, TypeAlias, TypeVar

P = ParamSpec("P")
T = TypeVar("T")

SyncCallable: TypeAlias = Callable[P, T]
AsyncCallable: TypeAlias = Callable[P, Awaitable[T]]
AnyCallable: TypeAlias = Callable[..., Any]

ExceptionTypes: TypeAlias = tuple[type[BaseException], ...]
