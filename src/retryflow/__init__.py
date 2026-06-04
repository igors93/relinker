"""
RetryFlow public API.

This module exposes the stable imports users should rely on.
Internal modules can change, but these names should remain stable whenever possible.
"""

from __future__ import annotations

from retryflow.context import AsyncRetryAttemptContext, RetryAttemptContext
from retryflow.exceptions import (
    InvalidRetryConfigError,
    RetryExhaustedError,
    RetryFlowError,
)
from retryflow.policy import RetryPolicy
from retryflow.result import RetryResult
from retryflow.retry import retry
from retryflow.state import RetryState
from retryflow.stats import RetryStats, RetryStatsSnapshot

__all__ = [
    "AsyncRetryAttemptContext",
    "InvalidRetryConfigError",
    "RetryAttemptContext",
    "RetryExhaustedError",
    "RetryFlowError",
    "RetryPolicy",
    "RetryResult",
    "RetryState",
    "RetryStats",
    "RetryStatsSnapshot",
    "retry",
]

__version__ = "0.3.0"
