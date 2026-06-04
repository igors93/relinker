"""
Ready-to-use retry presets.

Presets are intentionally small and transparent. They are just RetryPolicy
objects with sensible defaults, so users can keep customizing them.

Examples:
    policy = network()
    policy = network().attempts(10)
    policy = fast(TimeoutError)
"""

from __future__ import annotations

from typing import Any

from retryflow.policy import RetryPolicy

ExceptionTypes = tuple[type[BaseException], ...]


def _exceptions_or_default(
    exception_types: tuple[type[BaseException], ...],
    default: ExceptionTypes,
) -> ExceptionTypes:
    """Return user-provided exception types or a preset default."""
    return exception_types or default


def fast(*exception_types: type[BaseException]) -> RetryPolicy[Any]:
    """
    Return a small, quick retry policy.

    Best for:
        - local operations
        - short-lived transient failures
        - fast tests with real retry behavior

    Default:
        3 attempts, 0.1s fixed delay.
    """
    exceptions = _exceptions_or_default(exception_types, (Exception,))
    return RetryPolicy().attempts(3).on(*exceptions).fixed_delay(0.1)


def network(*exception_types: type[BaseException]) -> RetryPolicy[Any]:
    """
    Return a retry policy for network calls.

    Best for:
        - HTTP clients
        - external APIs
        - temporary connection failures

    Default:
        TimeoutError, ConnectionError, and OSError.
    """
    exceptions = _exceptions_or_default(
        exception_types,
        (TimeoutError, ConnectionError, OSError),
    )
    return (
        RetryPolicy()
        .attempts(5)
        .on(*exceptions)
        .random_exponential_delay(base=0.25, minimum=0.0, maximum=10.0)
    )


def database(*exception_types: type[BaseException]) -> RetryPolicy[Any]:
    """
    Return a retry policy for database-like operations.

    Best for:
        - transient connection drops
        - short lock waits
        - temporary infrastructure hiccups

    Default:
        TimeoutError, ConnectionError, and OSError.
    """
    exceptions = _exceptions_or_default(
        exception_types,
        (TimeoutError, ConnectionError, OSError),
    )
    return (
        RetryPolicy()
        .attempts(4)
        .on(*exceptions)
        .exponential_delay(base=0.1, factor=2.0, maximum=2.0)
        .jitter(maximum=0.2)
    )


def patient(*exception_types: type[BaseException]) -> RetryPolicy[Any]:
    """
    Return a slower retry policy for operations that can wait longer.

    Best for:
        - background synchronization
        - eventual consistency
        - slow external services

    Default:
        TimeoutError, ConnectionError, and OSError.
    """
    exceptions = _exceptions_or_default(
        exception_types,
        (TimeoutError, ConnectionError, OSError),
    )
    return (
        RetryPolicy()
        .attempts(8)
        .on(*exceptions)
        .exponential_delay(base=1.0, factor=2.0, maximum=60.0)
        .jitter(maximum=1.0)
    )


def background_job(*exception_types: type[BaseException]) -> RetryPolicy[Any]:
    """
    Return a retry policy for background jobs.

    Best for:
        - workers
        - queue consumers
        - scheduled jobs

    Default:
        Exception, because background jobs often centralize error handling.
        RetryFlow will still expose a broad_exception warning.
    """
    exceptions = _exceptions_or_default(exception_types, (Exception,))
    return (
        RetryPolicy()
        .attempts(10)
        .on(*exceptions)
        .exponential_delay(base=0.5, factor=2.0, maximum=30.0)
        .jitter(maximum=1.0)
    )


__all__ = [
    "background_job",
    "database",
    "fast",
    "network",
    "patient",
]
