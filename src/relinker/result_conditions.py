"""Small helpers for result-based retry predicates."""

from __future__ import annotations

from collections.abc import Callable, Sized
from typing import TypeVar

T = TypeVar("T")

__all__ = [
    "retry_if_empty",
    "retry_if_false",
    "retry_if_none",
    "retry_if_value",
]


def retry_if_none() -> Callable[[object], bool]:
    """Return a predicate that retries only when the result is None."""

    def predicate(value: object) -> bool:
        return value is None

    return predicate


def retry_if_false() -> Callable[[object], bool]:
    """Return a predicate that retries only when the result is exactly False."""

    def predicate(value: object) -> bool:
        return value is False

    return predicate


def retry_if_empty() -> Callable[[object], bool]:
    """Return a predicate that retries values whose length is zero."""

    def predicate(value: object) -> bool:
        return isinstance(value, Sized) and len(value) == 0

    return predicate


def retry_if_value(expected: T) -> Callable[[object], bool]:
    """Return a predicate that retries when the result equals ``expected``."""

    def predicate(value: object) -> bool:
        return value == expected

    return predicate
