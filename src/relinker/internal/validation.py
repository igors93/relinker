"""Validation helpers for impossible configurations."""

from __future__ import annotations

import math

from relinker.exceptions import InvalidRetryConfigError


def ensure_finite_float(name: str, value: object) -> float:
    """Raise when value is not a finite, non-bool number. Returns float."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise InvalidRetryConfigError(f"{name} must be a number, got {type(value).__name__}")
    resolved = float(value)
    if not math.isfinite(resolved):
        raise InvalidRetryConfigError(f"{name} must be finite, got {value!r}")
    return resolved


def ensure_non_negative(name: str, value: object) -> None:
    """Raise when value is not a finite non-negative number."""
    resolved = ensure_finite_float(name, value)
    if resolved < 0:
        raise InvalidRetryConfigError(f"{name} must be greater than or equal to 0")


def ensure_resolved_delay(value: object) -> float:
    """Raise when a final resolved delay is not safe to pass to sleep."""
    message = "resolved delay must be a finite non-negative number"
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise InvalidRetryConfigError(message)
    resolved = float(value)
    if not math.isfinite(resolved) or resolved < 0:
        raise InvalidRetryConfigError(message)
    return resolved


def ensure_positive(name: str, value: object) -> None:
    """Raise when value is not a finite positive number."""
    resolved = ensure_finite_float(name, value)
    if resolved <= 0:
        raise InvalidRetryConfigError(f"{name} must be greater than 0")


def ensure_positive_int(name: str, value: object) -> None:
    """Raise when value is not a positive integer (booleans rejected)."""
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise InvalidRetryConfigError(f"{name} must be a positive integer, got {value!r}")


def ensure_exception_types(exception_types: tuple[type[BaseException], ...]) -> None:
    """Raise when any configured exception type is invalid."""
    if not exception_types:
        raise InvalidRetryConfigError("at least one exception type is required")

    for exception_type in exception_types:
        if not isinstance(exception_type, type) or not issubclass(exception_type, BaseException):
            raise InvalidRetryConfigError(
                "exception types must be classes derived from BaseException"
            )
        if not issubclass(exception_type, Exception):
            raise InvalidRetryConfigError(
                f"{exception_type.__name__} is a BaseException subclass"
                " that the executor never catches"
            )
