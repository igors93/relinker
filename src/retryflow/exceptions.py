"""
Custom exceptions used by RetryFlow.
"""

from __future__ import annotations

from typing import Any


class RetryFlowError(Exception):
    """Base exception for all errors raised by RetryFlow itself."""


class InvalidRetryConfigError(RetryFlowError, ValueError):
    """
    Raised when a retry policy receives an impossible configuration.

    RetryFlow should not block user decisions, but it should reject values that
    cannot make sense, such as negative attempts or negative delays.
    """


class RetryExhaustedError(RetryFlowError):
    """
    Raised when retry attempts are exhausted and the user chooses library-level failure.

    By default, RetryFlow re-raises the last original exception for exception-based
    failures and returns the last value for result-based retries. This exception is
    available for users who prefer a RetryFlow-specific failure object.
    """

    def __init__(self, message: str, *, result: Any | None = None) -> None:
        super().__init__(message)
        self.result = result


class TryAgain(Exception):
    """
    Explicit signal to request another retry attempt from inside a wrapped function.

    Raise TryAgain to unconditionally request another attempt, regardless of which
    exception types the policy is configured to retry. TryAgain still respects the
    stop strategy (attempt limit or elapsed time).

    Example:
        from retryflow import TryAgain

        def task():
            result = call_service()
            if result == "pending":
                raise TryAgain("not ready yet")
            return result
    """
