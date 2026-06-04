"""Custom retry condition."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class CustomCondition:
    """
    Fully custom retry condition.

    The callback receives either an error or a value. Exactly one of them will
    be non-None for each decision.
    """

    callback: Callable[[BaseException | None, Any], bool]

    def should_retry_exception(self, error: BaseException) -> bool:
        """Return True when the callback says the exception should be retried."""
        return bool(self.callback(error, None))

    def should_retry_result(self, value: Any) -> bool:
        """Return True when the callback says the value should be retried."""
        return bool(self.callback(None, value))
