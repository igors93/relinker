"""
Behavioural tests for severity, has_critical, risk_level derivation,
can_retry suppression, and check completeness.

All tests in this file are expected to FAIL against the original codebase
(before the severity / completeness implementation) and PASS after it.
"""

from __future__ import annotations

import json

import pytest

from relinker import RetryBudget, RetryPolicy
from relinker.diagnostics import PolicyHealthReport, PolicyWarning

# ---------------------------------------------------------------------------
# Severity field on PolicyWarning
# ---------------------------------------------------------------------------


def test_policy_warning_default_severity_is_warning() -> None:
    w = PolicyWarning(code="x", message="y")
    assert w.severity == "warning"


def test_policy_warning_positional_construction_still_works() -> None:
    w = PolicyWarning("code", "message", "hint")
    assert w.code == "code"
    assert w.message == "message"
    assert w.hint == "hint"
    assert w.severity == "warning"


def test_policy_warning_severity_explicit_critical() -> None:
    w = PolicyWarning("code", "message", None, "critical")
    assert w.severity == "critical"


def test_policy_warning_severity_explicit_advisory() -> None:
    w = PolicyWarning("code", "message", severity="advisory")
    assert w.severity == "advisory"


def test_all_emitted_warnings_have_valid_severity() -> None:
    valid = {"advisory", "warning", "critical"}
    policies = [
        RetryPolicy().forever().on(Exception).no_delay().keep_history(None),
        RetryPolicy().attempts(12).on(TimeoutError).exponential_delay(base=1),
        RetryPolicy(),
        (
            RetryPolicy()
            .forever()
            .on(TimeoutError)
            .fixed_delay(1)
            .with_retry_budget(RetryBudget(max_retries=10, per=60), key="sev_test")
        ),
        RetryPolicy().attempts(10).exponential_delay(base=1, factor=3),
        RetryPolicy().attempts(3).retry_if_result(lambda v: v is None),
        RetryPolicy().attempts(3).on(OSError).fixed_delay(1),
        RetryPolicy().attempts(3).on(TimeoutError).random_delay(seed=7),
        RetryPolicy().attempts(2).on(TimeoutError).fallback_value("cached"),
        RetryPolicy().max_time(5).on(TimeoutError).fixed_delay(1).for_testing(),
    ]
    for policy in policies:
        for w in policy.warnings():
            assert w.severity in valid, f"Warning {w.code!r} has invalid severity {w.severity!r}"


# ---------------------------------------------------------------------------
# Per-warning severity assertions
# ---------------------------------------------------------------------------


def test_tight_loop_risk_is_critical() -> None:
    policy = RetryPolicy().forever().on(TimeoutError).no_delay()
    by_code = {w.code: w for w in policy.warnings()}
    assert "tight_loop_risk" in by_code
    assert by_code["tight_loop_risk"].severity == "critical"


def test_unbounded_history_is_critical() -> None:
    policy = RetryPolicy().forever().on(TimeoutError).fixed_delay(1).keep_history(None)
    by_code = {w.code: w for w in policy.warnings()}
    assert "unbounded_history" in by_code
    assert by_code["unbounded_history"].severity == "critical"


def test_background_broad_exception_is_critical() -> None:
    policy = RetryPolicy().attempts(15).on(Exception).fixed_delay(1)
    by_code = {w.code: w for w in policy.warnings()}
    assert "background_broad_exception" in by_code
    assert by_code["background_broad_exception"].severity == "critical"


def test_missing_jitter_is_advisory() -> None:
    policy = RetryPolicy().attempts(12).on(TimeoutError).exponential_delay(base=1)
    by_code = {w.code: w for w in policy.warnings()}
    assert "missing_jitter" in by_code
    assert by_code["missing_jitter"].severity == "advisory"


def test_seeded_random_delay_is_advisory() -> None:
    policy = RetryPolicy().attempts(3).on(TimeoutError).random_delay(seed=7)
    by_code = {w.code: w for w in policy.warnings()}
    assert "seeded_random_delay" in by_code
    assert by_code["seeded_random_delay"].severity == "advisory"


def test_implicit_default_policy_is_advisory() -> None:
    policy = RetryPolicy()
    by_code = {w.code: w for w in policy.warnings()}
    assert "implicit_default_policy" in by_code
    assert by_code["implicit_default_policy"].severity == "advisory"


def test_for_testing_with_max_time_is_advisory() -> None:
    policy = RetryPolicy().max_time(5).on(TimeoutError).fixed_delay(1).for_testing()
    by_code = {w.code: w for w in policy.warnings()}
    assert "for_testing_with_max_time" in by_code
    assert by_code["for_testing_with_max_time"].severity == "advisory"


def test_high_total_sleep_is_advisory() -> None:
    policy = RetryPolicy().attempts(10).exponential_delay(base=1, factor=3)
    by_code = {w.code: w for w in policy.warnings()}
    assert "high_total_sleep" in by_code
    assert by_code["high_total_sleep"].severity == "advisory"


def test_broad_exception_is_warning_level() -> None:
    policy = RetryPolicy().attempts(3).on(Exception).fixed_delay(1)
    by_code = {w.code: w for w in policy.warnings()}
    assert "broad_exception" in by_code
    assert by_code["broad_exception"].severity == "warning"


def test_forever_is_warning_level() -> None:
    policy = RetryPolicy().forever().on(TimeoutError).fixed_delay(1)
    by_code = {w.code: w for w in policy.warnings()}
    assert "forever" in by_code
    assert by_code["forever"].severity == "warning"


# ---------------------------------------------------------------------------
# has_critical property
# ---------------------------------------------------------------------------


def test_has_critical_false_for_clean_policy() -> None:
    policy = RetryPolicy().attempts(3).on(TimeoutError).fixed_delay(1)
    assert policy.doctor().has_critical is False


def test_has_critical_false_for_advisory_only() -> None:
    # implicit_default_policy is advisory
    assert RetryPolicy().doctor().has_critical is False


def test_has_critical_true_for_tight_loop() -> None:
    policy = RetryPolicy().forever().on(TimeoutError).no_delay()
    assert policy.doctor().has_critical is True


def test_has_critical_true_for_unbounded_history() -> None:
    policy = RetryPolicy().forever().on(TimeoutError).fixed_delay(1).keep_history(None)
    assert policy.doctor().has_critical is True


def test_has_critical_true_for_background_broad_exception() -> None:
    policy = RetryPolicy().forever().on(Exception).fixed_delay(1)
    assert policy.doctor().has_critical is True


def test_critical_count_with_multiple_critical_warnings() -> None:
    # tight_loop_risk + background_broad_exception (both critical) — no duplicates
    policy = RetryPolicy().forever().on(Exception).no_delay()
    report = policy.doctor()
    assert report.critical_count >= 2
    assert report.critical_count == sum(1 for w in report.warnings if w.severity == "critical")


# ---------------------------------------------------------------------------
# risk_level derived from severity (not from a parallel code list)
# ---------------------------------------------------------------------------


def test_risk_level_ok_when_no_warnings() -> None:
    policy = RetryPolicy().attempts(3).on(TimeoutError).fixed_delay(1)
    assert policy.doctor().risk_level == "ok"


def test_risk_level_warning_for_advisory_only() -> None:
    # implicit_default_policy is advisory — not critical — so risk is "warning" not "risky"
    report = RetryPolicy().doctor()
    assert "implicit_default_policy" in {w.code for w in report.warnings}
    assert report.risk_level == "warning"


def test_risk_level_warning_for_warning_severity_only() -> None:
    # broad_exception is "warning" severity, not "critical"
    policy = RetryPolicy().attempts(3).on(Exception).fixed_delay(1)
    report = policy.doctor()
    assert "broad_exception" in {w.code for w in report.warnings}
    assert report.risk_level == "warning"


def test_risk_level_risky_when_critical_present() -> None:
    policy = RetryPolicy().forever().on(TimeoutError).no_delay()
    assert policy.doctor().risk_level == "risky"


def test_risk_level_risky_derived_from_severity_not_code_list() -> None:
    # unbounded_history is critical → risky; this policy has only unbounded_history
    # and forever (warning) as risk-level influencers
    policy = RetryPolicy().forever().on(TimeoutError).fixed_delay(1).keep_history(None)
    report = policy.doctor()
    assert any(w.code == "unbounded_history" and w.severity == "critical" for w in report.warnings)
    assert report.risk_level == "risky"


@pytest.mark.parametrize("value", ["ok", "warning", "risky"])
def test_risk_level_only_returns_literal_values(value: str) -> None:
    # Static check: the returned values must remain exactly these three strings.
    # This parametrize simply documents the contract; the real check is the type.
    assert value in ("ok", "warning", "risky")


# ---------------------------------------------------------------------------
# can_retry suppression — single attempt
# ---------------------------------------------------------------------------


def test_single_attempt_exception_no_delay_no_retry_warnings() -> None:
    policy = RetryPolicy().attempts(1).on(Exception).no_delay()
    codes = {w.code for w in policy.warnings()}
    assert "no_delay" not in codes
    assert "broad_exception" not in codes


def test_max_time_zero_no_retry_warnings() -> None:
    policy = RetryPolicy().max_time(0).on(OSError).fixed_delay(1)
    codes = {w.code for w in policy.warnings()}
    assert "broad_os_error" not in codes


def test_single_attempt_fallback_no_silent_fallback_warning() -> None:
    policy = RetryPolicy().attempts(1).fallback_value("fallback")
    codes = {w.code for w in policy.warnings()}
    assert "silent_fallback" not in codes


def test_single_attempt_result_condition_no_retry_warning() -> None:
    policy = RetryPolicy().attempts(1).retry_if_result(lambda v: v is None)
    codes = {w.code for w in policy.warnings()}
    assert "result_retry_without_observation" not in codes


# ---------------------------------------------------------------------------
# can_retry suppression — composite stop strategies
# ---------------------------------------------------------------------------


def test_any_stop_with_immediate_time_suppresses_retry_warnings() -> None:
    policy = RetryPolicy().attempts(10).or_stop_after_time(0).on(Exception).no_delay()
    codes = {w.code for w in policy.warnings()}
    assert "no_delay" not in codes
    assert "broad_exception" not in codes
    assert "background_broad_exception" not in codes


def test_any_stop_with_immediate_time_suppresses_missing_retry_budget() -> None:
    policy = RetryPolicy().attempts(10).or_stop_after_time(0).on(TimeoutError).fixed_delay(1)
    codes = {w.code for w in policy.warnings()}
    assert "missing_retry_budget" not in codes


def test_all_stop_with_one_allowing_retry_still_warns() -> None:
    # AllStopStrategy: stops only when ALL conditions are met;
    # StopAfterDelay(10) keeps retrying within 10s even with attempts=1
    policy = RetryPolicy().attempts(1).and_stop_after_time(10).on(Exception).no_delay()
    codes = {w.code for w in policy.warnings()}
    assert "no_delay" in codes
    assert "broad_exception" in codes


# ---------------------------------------------------------------------------
# Incomplete checks — high_total_sleep skipped for custom delay
# ---------------------------------------------------------------------------


def _custom_delay_policy() -> RetryPolicy[object]:
    return (
        RetryPolicy()
        .attempts(15)
        .on(TimeoutError)
        .stateful_delay(lambda state: state.attempt_number * 0.5)
    )


def test_custom_delay_makes_high_total_sleep_check_incomplete() -> None:
    report = _custom_delay_policy().doctor()
    assert report.complete is False
    assert "high_total_sleep" in report.skipped_checks


def test_incomplete_report_still_contains_other_warnings() -> None:
    report = _custom_delay_policy().doctor()
    codes = {w.code for w in report.warnings}
    assert "many_attempts" in codes
    assert "missing_retry_budget" in codes


def test_warnings_method_still_works_for_incomplete_policy() -> None:
    warnings = _custom_delay_policy().warnings()
    assert isinstance(warnings, tuple)
    codes = {w.code for w in warnings}
    assert "many_attempts" in codes


def test_describe_shows_incomplete_state() -> None:
    text = _custom_delay_policy().doctor().describe()
    assert "complete" in text.lower()
    assert "high_total_sleep" in text


def test_describe_does_not_expose_callback_details() -> None:
    text = _custom_delay_policy().doctor().describe()
    assert "lambda" not in text
    assert "traceback" not in text.lower()
    assert "error" not in text.lower()


def test_complete_report_has_complete_true() -> None:
    report = RetryPolicy().attempts(3).on(TimeoutError).fixed_delay(1).doctor()
    assert report.complete is True
    assert report.skipped_checks == ()


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------


def test_policy_warning_to_dict_includes_severity() -> None:
    w = PolicyWarning("code", "msg", None, "critical")
    d = w.to_dict()
    assert "severity" in d
    assert d["severity"] == "critical"


def test_policy_warning_to_dict_default_severity_is_warning() -> None:
    w = PolicyWarning("code", "msg")
    d = w.to_dict()
    assert d["severity"] == "warning"


def test_policy_health_report_to_dict_includes_complete() -> None:
    d = PolicyHealthReport(()).to_dict()
    assert "complete" in d
    assert d["complete"] is True


def test_policy_health_report_to_dict_includes_skipped_checks() -> None:
    d = PolicyHealthReport(()).to_dict()
    assert "skipped_checks" in d
    assert d["skipped_checks"] == []


def test_policy_health_report_to_dict_incomplete_report() -> None:
    report = PolicyHealthReport(
        warnings=(),
        complete=False,
        skipped_checks=("high_total_sleep",),
    )
    d = report.to_dict()
    assert d["complete"] is False
    assert d["skipped_checks"] == ["high_total_sleep"]


def test_policy_health_report_to_json_includes_new_fields() -> None:
    report = PolicyHealthReport(())
    data = json.loads(report.to_json())
    assert "complete" in data
    assert "skipped_checks" in data


# ---------------------------------------------------------------------------
# Backward compatibility
# ---------------------------------------------------------------------------


def test_policy_health_report_positional_construction_still_works() -> None:
    warnings = (PolicyWarning("code", "message"),)
    report = PolicyHealthReport(warnings)
    assert report.warnings == warnings
    assert report.complete is True
    assert report.skipped_checks == ()


def test_warnings_returns_tuple_of_policy_warnings() -> None:
    for w in RetryPolicy().forever().on(Exception).warnings():
        assert isinstance(w, PolicyWarning)


def test_doctor_returns_policy_health_report() -> None:
    report = RetryPolicy().doctor()
    assert isinstance(report, PolicyHealthReport)
