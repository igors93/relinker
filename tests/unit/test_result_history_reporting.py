"""
Regression tests for truthful RetryResult reporting with bounded history.

These tests cover aggregate counters, retained history metadata, serialization,
human-readable stories, and backward-compatible manual construction.
"""

from __future__ import annotations

from relinker import RetryPolicy
from relinker.attempt import AttemptRecord
from relinker.result import RetryResult


def _always_fail() -> None:
    """Raise a deterministic exception for retry tests."""
    raise ValueError("boom")


def test_bounded_history_serialization_reports_true_totals() -> None:
    """Serialized results must separate complete totals from retained history."""
    policy = RetryPolicy().attempts(5).keep_history(2).no_delay().return_result()

    result = policy.run(_always_fail)
    data = result.to_dict()

    assert data["attempt_count"] == 5
    assert data["failed_attempts"] == 5
    assert data["successful_attempts"] == 0
    assert data["retained_attempt_count"] == 2
    assert data["history_truncated"] is True
    assert len(data["attempts"]) == 2


def test_summary_reports_true_totals() -> None:
    """Compact summaries must expose the same truthful aggregate counters."""
    policy = RetryPolicy().attempts(4).keep_history(1).no_delay().return_result()

    result = policy.run(_always_fail)
    summary = result.summary()

    assert summary["attempt_count"] == 4
    assert summary["failed_attempts"] == 4
    assert summary["successful_attempts"] == 0
    assert summary["retained_attempt_count"] == 1
    assert summary["history_truncated"] is True


def test_story_explains_truncated_history() -> None:
    """The human-readable story must explain why not every attempt is listed."""
    policy = RetryPolicy().attempts(5).keep_history(2).no_delay().return_result()

    result = policy.run(_always_fail)

    assert "Attempts: 5" in result.story()
    assert "Retained history: last 2 of 5 attempts" in result.story()


def test_unlimited_history_is_not_reported_as_truncated() -> None:
    """Unlimited history should report every attempt as retained."""
    policy = RetryPolicy().attempts(3).keep_history(None).no_delay().return_result()

    result = policy.run(_always_fail)

    assert result.attempt_count == 3
    assert result.retained_attempt_count == 3
    assert result.history_truncated is False


def test_manual_result_falls_back_to_retained_metrics() -> None:
    """Manual results remain correct when aggregate counters are omitted."""
    attempt = AttemptRecord(
        number=1,
        started_at=0.0,
        ended_at=1.0,
        error=ValueError("boom"),
    )

    result = RetryResult(
        attempts=(attempt,),
        total_attempts=1,
    )

    assert result.failed_attempts == 1
    assert result.successful_attempts == 0


def test_explicit_zero_aggregate_is_preserved() -> None:
    """A provided aggregate value of zero must not be confused with missing data."""
    attempt = AttemptRecord(
        number=1,
        started_at=0.0,
        ended_at=1.0,
        error=ValueError("boom"),
    )

    result = RetryResult(
        attempts=(attempt,),
        total_attempts=1,
        total_failed_attempts=0,
        total_successful_attempts=1,
    )

    assert result.failed_attempts == 0
    assert result.successful_attempts == 1
