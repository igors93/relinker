"""Base retry condition interface."""

from __future__ import annotations

from typing import Any, Protocol


class RetryCondition(Protocol):
    """
    Protocol implemented by retry conditions.

    A condition can decide based on an exception, a returned value, or both.
    """

    def should_retry_exception(self, error: BaseException) -> bool:
        """Return True when this exception should be retried."""

    def should_retry_result(self, value: Any) -> bool:
        """Return True when this returned value should be retried."""
