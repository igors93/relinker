"""Validation helpers for impossible configurations."""

from __future__ import annotations

import math

from relinker.exceptions import InvalidRetryConfigError

# Single operational ceiling for every delay value that reaches a sleeper.
#
# Rationale:
#   time.sleep() and asyncio.sleep() use _PyTime_t (signed int64, nanoseconds)
#   internally. Values above ~9.22e9 s raise OverflowError on all supported
#   platforms (Python 3.10-3.14, Linux/macOS/Windows).  sys.float_info.max / 2
#   is far outside this range.  86 400 s (1 day) is a generous and practical
#   ceiling for any retry backoff.  Callers needing a higher ceiling must set
#   the value explicitly; if a platform ever needs a different cap, this is the
#   single place to change it.
MAX_SLEEP_SECONDS: float = 86_400.0


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


def ensure_safe_delay(name: str, value: object) -> float:
    """Raise when an explicitly configured delay value exceeds the operational ceiling."""
    resolved = ensure_finite_float(name, value)
    if resolved < 0:
        raise InvalidRetryConfigError(f"{name} must be greater than or equal to 0")
    if resolved > MAX_SLEEP_SECONDS:
        raise InvalidRetryConfigError(
            f"{name} must be at most {MAX_SLEEP_SECONDS} seconds"
            f" (got {resolved}); use a smaller value or a different strategy"
        )
    return resolved


def ensure_resolved_delay(value: object) -> float:
    """Raise when a final resolved delay is not safe to pass to sleep."""
    message = (
        f"resolved delay must be a finite non-negative number"
        f" not exceeding {MAX_SLEEP_SECONDS} seconds"
    )
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise InvalidRetryConfigError(message)
    resolved = float(value)
    if not math.isfinite(resolved) or resolved < 0 or resolved > MAX_SLEEP_SECONDS:
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
