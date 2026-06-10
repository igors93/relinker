"""Custom retry condition."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from relinker.conditions.base import ConditionMixin
from relinker.internal.callables import ensure_callable


@dataclass(frozen=True, slots=True)
class CustomCondition(ConditionMixin):
    """
    Fully custom retry condition.

    The callback receives (error, value). For exception decisions, error is the
    raised exception and value is None. For result decisions, error is None and
    value contains the returned value — which may itself be None when the
    function returned None.
    """

    callback: Callable[[BaseException | None, Any], bool]

    def __post_init__(self) -> None:
        ensure_callable("callback", self.callback)

    def should_retry_exception(self, error: BaseException) -> bool:
        """Return True when the callback says the exception should be retried."""
        return bool(self.callback(error, None))

    def should_retry_result(self, value: Any) -> bool:
        """Return True when the callback says the value should be retried."""
        return bool(self.callback(None, value))
