"""
RetryFlow public API.

This module exposes the stable imports users should rely on.
Internal modules can change, but these names should remain stable whenever possible.
"""

from __future__ import annotations

from retryflow.context import AsyncRetryAttemptContext, RetryAttemptContext
from retryflow.diagnostics import PolicyWarning, RetrySimulation, RetrySimulationAttempt
from retryflow.exceptions import (
    InvalidRetryConfigError,
    RetryExhaustedError,
    RetryFlowError,
)
from retryflow.policy import RetryPolicy
from retryflow.presets import background_job, database, fast, network, patient
from retryflow.result import RetryResult
from retryflow.retry import retry
from retryflow.state import RetryState
from retryflow.stats import RetryStats, RetryStatsSnapshot

__all__ = [
    "AsyncRetryAttemptContext",
    "InvalidRetryConfigError",
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
    "background_job",
    "database",
    "fast",
    "network",
    "patient",
    "retry",
]

__version__ = "0.4.0"
