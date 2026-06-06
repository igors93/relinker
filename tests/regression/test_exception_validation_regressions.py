"""Regression tests for retry exception validation consistency."""

from __future__ import annotations

import pytest

from relinker import InvalidRetryConfigError, RetryPolicy
from relinker.conditions.exception import ExceptionCondition


@pytest.mark.parametrize("exception_type", [SystemExit, KeyboardInterrupt])
def test_or_on_rejects_base_exceptions_not_caught_by_executor(
    exception_type: type[BaseException],
) -> None:
    """or_on() must enforce the same exception contract as on()."""
    with pytest.raises(InvalidRetryConfigError):
        RetryPolicy().or_on(exception_type)


@pytest.mark.parametrize("exception_type", [SystemExit, KeyboardInterrupt])
def test_exception_condition_rejects_base_exceptions_not_caught_by_executor(
    exception_type: type[BaseException],
) -> None:
    """Direct condition construction must not bypass the executor contract."""
    with pytest.raises(InvalidRetryConfigError):
        ExceptionCondition((exception_type,))


def test_on_invalid_non_class_raises_library_configuration_error() -> None:
    """Invalid exception inputs must not leak the built-in issubclass TypeError."""
    with pytest.raises(InvalidRetryConfigError):
        RetryPolicy().on(123)  # type: ignore[arg-type]
