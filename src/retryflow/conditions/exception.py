"""Retry condition based on exception types."""

from __future__ import annotations

from dataclasses import dataclass

from retryflow.internal.validation import ensure_exception_types


@dataclass(frozen=True, slots=True)
class ExceptionCondition:
    """Retries when the raised exception matches one of the configured types."""

    exception_types: tuple[type[BaseException], ...] = (Exception,)

    def __post_init__(self) -> None:
        ensure_exception_types(self.exception_types)

    def should_retry_exception(self, error: BaseException) -> bool:
        """Return True when the error matches the configured exception types."""
        return isinstance(error, self.exception_types)

    def should_retry_result(self, value: object) -> bool:
        """Exception-based conditions do not retry successful return values."""
        return False
