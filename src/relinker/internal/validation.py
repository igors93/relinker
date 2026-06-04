"""Validation helpers for impossible configurations."""

from __future__ import annotations

from relinker.exceptions import InvalidRetryConfigError


def ensure_non_negative(name: str, value: float) -> None:
    """Raise when value is negative."""
    if value < 0:
        raise InvalidRetryConfigError(f"{name} must be greater than or equal to 0")


def ensure_positive(name: str, value: float) -> None:
    """Raise when value is not positive."""
    if value <= 0:
        raise InvalidRetryConfigError(f"{name} must be greater than 0")


def ensure_positive_int(name: str, value: int) -> None:
    """Raise when value is not a positive integer."""
    if not isinstance(value, int) or value <= 0:
        raise InvalidRetryConfigError(f"{name} must be a positive integer")


def ensure_exception_types(exception_types: tuple[type[BaseException], ...]) -> None:
    """Raise when any configured exception type is invalid."""
    if not exception_types:
        raise InvalidRetryConfigError("at least one exception type is required")

    for exception_type in exception_types:
        if not isinstance(exception_type, type) or not issubclass(exception_type, BaseException):
            raise InvalidRetryConfigError(
                "exception types must be classes derived from BaseException"
            )
