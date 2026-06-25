"""Regression tests for attempts validation in simulate(), timeline(), and preview()."""

from __future__ import annotations

import pytest

from relinker import InvalidRetryConfigError, RetryPolicy


@pytest.mark.parametrize(
    "invalid_attempts",
    [0, -1, True, False, 1.5, "3", None],
)
def test_simulate_rejects_invalid_attempts(invalid_attempts: object) -> None:
    with pytest.raises(InvalidRetryConfigError):
        RetryPolicy().simulate(attempts=invalid_attempts)  # type: ignore[arg-type]


def test_timeline_rejects_invalid_attempts() -> None:
    with pytest.raises(InvalidRetryConfigError):
        RetryPolicy().timeline(attempts=False)  # type: ignore[arg-type]


def test_preview_rejects_invalid_attempts() -> None:
    with pytest.raises(InvalidRetryConfigError):
        RetryPolicy().preview(attempts="3")  # type: ignore[arg-type]


def test_simulate_accepts_positive_integer_attempts() -> None:
    simulation = RetryPolicy().simulate(attempts=2)

    assert simulation.attempt_count == 2


def test_timeline_accepts_positive_integer_attempts() -> None:
    timeline = RetryPolicy().timeline(attempts=2)

    assert "Attempts simulated" in timeline


def test_preview_accepts_positive_integer_attempts() -> None:
    preview = RetryPolicy().preview(attempts=2)

    assert "Relinker preview" in preview
