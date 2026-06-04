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

    By default, RetryFlow re-raises the last original exception. This exception is
    available for users who prefer a RetryFlow-specific error object.
    """

    def __init__(self, message: str, *, result: Any | None = None) -> None:
        super().__init__(message)
        self.result = result
