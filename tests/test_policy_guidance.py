from __future__ import annotations

from retryflow import RetryPolicy


def test_doctor_reports_risky_tight_loop() -> None:
    report = RetryPolicy().forever().no_delay().doctor()

    assert report.risk_level == "risky"
    assert any(warning.code == "tight_loop_risk" for warning in report.warnings)


def test_explain_is_human_readable() -> None:
    explanation = RetryPolicy().attempts(3).on(TimeoutError).fixed_delay(1).explain()

    assert "try up to 3 times" in explanation
    assert "TimeoutError" in explanation


def test_preview_shows_timeline() -> None:
    preview = RetryPolicy().attempts(3).fixed_delay(1).preview(attempts=3)

    assert "RetryFlow preview" in preview
    assert "Attempt 1" in preview
