"""Regression tests for verified public-policy contract failures."""

from __future__ import annotations

import pytest

from relinker import InvalidRetryConfigError, RetryPolicy


def _raise_runtime_error() -> None:
    """Raise a deterministic retryable error."""
    raise RuntimeError("boom")


def test_explain_supports_max_time_policy() -> None:
    """A valid max_time policy must be explainable without raising AttributeError."""
    explanation = RetryPolicy().max_time(5).explain()

    assert "5s" in explanation
    assert "StopAfterDelay" in explanation


def test_raise_last_configured_after_fallback_takes_precedence() -> None:
    """The last mutually exclusive exhaustion configuration must win."""
    policy = RetryPolicy().attempts(1).fallback_value("safe").raise_last()

    with pytest.raises(RuntimeError, match="boom"):
        policy.run(_raise_runtime_error)


def test_raise_last_configured_after_custom_exception_takes_precedence() -> None:
    """raise_last must clear a previously configured custom exhaustion exception."""
    policy = RetryPolicy().attempts(1).on_exhausted_raise(ValueError("custom")).raise_last()

    with pytest.raises(RuntimeError, match="boom"):
        policy.run(_raise_runtime_error)


def test_fallback_configured_after_raise_last_takes_precedence() -> None:
    """A fallback configured last must remain the final exhaustion behavior."""
    policy = RetryPolicy().attempts(1).raise_last().fallback_value("safe")

    assert policy.run(_raise_runtime_error) == "safe"


def test_custom_exception_configured_after_fallback_takes_precedence() -> None:
    """A custom exception configured last must replace a previous fallback."""
    policy = (
        RetryPolicy().attempts(1).fallback_value("safe").on_exhausted_raise(ValueError("custom"))
    )

    with pytest.raises(ValueError, match="custom"):
        policy.run(_raise_runtime_error)


@pytest.mark.parametrize("exception_type", [SystemExit, KeyboardInterrupt])
def test_on_rejects_base_exceptions_not_caught_by_executors(
    exception_type: type[BaseException],
) -> None:
    """The API must reject exception classes that its executors intentionally never catch."""
    with pytest.raises(InvalidRetryConfigError):
        RetryPolicy().on(exception_type)
