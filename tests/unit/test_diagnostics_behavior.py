"""Unit tests for policy diagnostics and health-report behavior."""

from __future__ import annotations

import json

from relinker import RetryPolicy


def test_default_policy_reports_implicit_default_warning() -> None:
    codes = {warning.code for warning in RetryPolicy().warnings()}
    assert "implicit_default_policy" in codes


def test_immediate_stop_suppresses_unreachable_retry_warnings() -> None:
    codes = {warning.code for warning in RetryPolicy().attempts(1).warnings()}
    assert "no_delay" not in codes
    assert "broad_exception" not in codes


def test_forever_policy_is_critical_and_risky() -> None:
    report = RetryPolicy().forever().on(TimeoutError).fixed_delay(1).doctor()
    by_code = {warning.code: warning for warning in report.warnings}
    assert by_code["forever"].severity == "critical"
    assert report.has_critical is True
    assert report.risk_level == "risky"


def test_stateful_delay_makes_unavailable_simulation_check_explicit() -> None:
    report = (
        RetryPolicy()
        .attempts(2)
        .on(TimeoutError)
        .stateful_delay(lambda state: float(state.attempt_number))
        .doctor()
    )
    assert report.complete is False
    assert "high_total_sleep" in report.skipped_checks
    assert report.ok is False
    assert report.risk_level in {"warning", "risky"}


def test_narrow_fixed_policy_can_receive_clean_complete_report() -> None:
    report = RetryPolicy().attempts(3).on(TimeoutError).fixed_delay(1).doctor()
    assert report.complete is True
    assert report.warnings == ()
    assert report.ok is True
    assert report.risk_level == "ok"


def test_seeded_random_delay_warning_is_exposed_for_production_policy() -> None:
    codes = {
        warning.code
        for warning in (RetryPolicy().attempts(3).on(TimeoutError).random_delay(seed=7).warnings())
    }
    assert "seeded_random_delay" in codes


def test_testing_mode_suppresses_seeded_random_delay_warning() -> None:
    codes = {
        warning.code
        for warning in (
            RetryPolicy().attempts(3).on(TimeoutError).random_delay(seed=7).for_testing().warnings()
        )
    }
    assert "seeded_random_delay" not in codes


def test_unbounded_history_warning_is_critical_for_forever_policy() -> None:
    warnings = RetryPolicy().forever().on(TimeoutError).fixed_delay(1).keep_history(None).warnings()
    by_code = {warning.code: warning for warning in warnings}
    assert by_code["unbounded_history"].severity == "critical"


def test_result_retry_without_observation_is_reported() -> None:
    codes = {
        warning.code
        for warning in (
            RetryPolicy()
            .attempts(3)
            .retry_if_result(lambda value: value == "waiting")
            .fixed_delay(1)
            .warnings()
        )
    }
    assert "result_retry_without_observation" in codes


def test_silent_fallback_is_reported_without_giveup_observer() -> None:
    codes = {
        warning.code
        for warning in (
            RetryPolicy()
            .attempts(3)
            .on(TimeoutError)
            .fixed_delay(1)
            .fallback_value("safe")
            .warnings()
        )
    }
    assert "silent_fallback" in codes


def test_health_report_json_matches_public_properties() -> None:
    report = RetryPolicy().forever().on(TimeoutError).fixed_delay(1).doctor()
    data = json.loads(report.to_json())
    assert data["ok"] is report.ok
    assert data["risk_level"] == report.risk_level
    assert data["complete"] is report.complete
    assert data["warning_count"] == len(report.warnings)
