"""
RetryFlow public API.

This module exposes the stable imports users should rely on. Internal modules can
change, but these names should remain stable whenever possible.
"""

from __future__ import annotations

from retryflow.context import AsyncRetryAttemptContext, RetryAttemptContext
from retryflow.diagnostics import (
    PolicyHealthReport,
    PolicyWarning,
    RetrySimulation,
    RetrySimulationAttempt,
)
from retryflow.exceptions import (
    InvalidRetryConfigError,
    RetryExhaustedError,
    RetryFlowError,
    TryAgain,
)
from retryflow.http import (
    DEFAULT_RETRYABLE_STATUSES,
    http_retry_policy,
    parse_retry_after,
    retry_after_delay,
    retry_if_status,
    should_retry_http_status,
)
from retryflow.policy import RetryPolicy
from retryflow.presets import background_job, database, fast, network, patient
from retryflow.result import RetryResult
from retryflow.retry import retry
from retryflow.state import RetryState
from retryflow.stats import RetryStats, RetryStatsSnapshot
from retryflow.typing import RetryWrappedFunction

__all__ = [
    "AsyncRetryAttemptContext",
    "DEFAULT_RETRYABLE_STATUSES",
    "InvalidRetryConfigError",
    "PolicyHealthReport",
    "PolicyWarning",
    "RetryAttemptContext",
    "RetryExhaustedError",
    "RetryFlowError",
    "RetryPolicy",
    "RetryResult",
    "RetrySimulation",
    "RetrySimulationAttempt",
    "RetryState",
    "RetryStats",
    "RetryStatsSnapshot",
    "RetryWrappedFunction",
    "TryAgain",
    "background_job",
    "database",
    "fast",
    "http_retry_policy",
    "network",
    "parse_retry_after",
    "patient",
    "retry",
    "retry_after_delay",
    "retry_if_status",
    "should_retry_http_status",
]

__version__ = "0.4.0"
