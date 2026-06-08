"""Tests for the new warning codes added in the richer diagnostics improvement."""

from __future__ import annotations

import pytest

from relinker import RetryPolicy, network


def test_warning_many_attempts() -> None:
    policy = RetryPolicy().attempts(11)
    codes = {w.code for w in policy.warnings()}
    assert "many_attempts" in codes


def test_warning_implicit_default_policy() -> None:
    policy = RetryPolicy()
    warnings = policy.warnings()
    codes = {warning.code for warning in warnings}

    assert "implicit_default_policy" in codes
    warning = next(warning for warning in warnings if warning.code == "implicit_default_policy")
    assert "all Exception subclasses" in warning.message
    assert warning.hint is not None
    assert "Specify exception types" in warning.hint


def test_warning_implicit_default_policy_is_reported_by_doctor() -> None:
    report = RetryPolicy().doctor()

    assert "implicit_default_policy" in {warning.code for warning in report.warnings}
    assert report.ok is False


def test_no_implicit_default_warning_for_explicit_exception_and_delay() -> None:
    policy = RetryPolicy().attempts(3).on(TimeoutError).fixed_delay(0.1)

    assert "implicit_default_policy" not in {warning.code for warning in policy.warnings()}


def test_no_implicit_default_warning_for_network_preset() -> None:
    assert "implicit_default_policy" not in {warning.code for warning in network().warnings()}


def test_implicit_default_warning_does_not_change_execution() -> None:
    calls = 0
    policy = RetryPolicy().for_testing()

    def operation() -> str:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise ValueError("temporary")
        return "ok"

    assert "implicit_default_policy" in {warning.code for warning in policy.warnings()}
    assert policy.run(operation) == "ok"
    assert calls == 2


def test_warning_many_attempts_exactly_10_does_not_warn() -> None:
    policy = RetryPolicy().attempts(10)
    codes = {w.code for w in policy.warnings()}
    assert "many_attempts" not in codes


def test_warning_high_total_sleep() -> None:
    # exponential with no cap: 1+2+4+8+...512 for 10 attempts > 300s
    policy = RetryPolicy().attempts(10).exponential_delay(base=1, factor=3)
    codes = {w.code for w in policy.warnings()}
    assert "high_total_sleep" in codes


def test_warning_high_total_sleep_not_fired_for_short_policies() -> None:
    # small fixed delay: 0.5 * 5 = 2.5s — nowhere near 300s
    policy = RetryPolicy().attempts(5).fixed_delay(0.5)
    codes = {w.code for w in policy.warnings()}
    assert "high_total_sleep" not in codes


def test_warning_high_total_sleep_not_fired_for_forever() -> None:
    # forever policies already get the 'forever' warning — skip high_total_sleep
    policy = RetryPolicy().forever().exponential_delay(base=100)
    codes = {w.code for w in policy.warnings()}
    assert "high_total_sleep" not in codes
    assert "forever" in codes


def test_warning_result_retry_without_observation() -> None:
    policy = RetryPolicy().attempts(3).retry_if_result(lambda v: v is None)
    codes = {w.code for w in policy.warnings()}
    assert "result_retry_without_observation" in codes


def test_no_warning_result_retry_with_return_result() -> None:
    policy = RetryPolicy().attempts(3).retry_if_result(lambda v: v is None).return_result()
    codes = {w.code for w in policy.warnings()}
    assert "result_retry_without_observation" not in codes


def test_no_warning_result_retry_with_fallback() -> None:
    policy = (
        RetryPolicy().attempts(3).retry_if_result(lambda v: v is None).fallback(lambda _: "default")
    )
    codes = {w.code for w in policy.warnings()}
    assert "result_retry_without_observation" not in codes


def test_no_warning_result_retry_with_raise_on_exhausted() -> None:
    policy = (
        RetryPolicy().attempts(3).retry_if_result(lambda v: v is None).raise_on_result_exhausted()
    )
    codes = {w.code for w in policy.warnings()}
    assert "result_retry_without_observation" not in codes


def test_warning_background_broad_exception_many_attempts() -> None:
    policy = RetryPolicy().attempts(10).on(Exception)
    codes = {w.code for w in policy.warnings()}
    assert "background_broad_exception" in codes
    assert "broad_exception" in codes


def test_warning_background_broad_exception_forever() -> None:
    policy = RetryPolicy().forever().on(Exception)
    codes = {w.code for w in policy.warnings()}
    assert "background_broad_exception" in codes


def test_no_background_broad_exception_for_specific_types() -> None:
    policy = RetryPolicy().attempts(10).on(TimeoutError)
    codes = {w.code for w in policy.warnings()}
    assert "background_broad_exception" not in codes


def test_no_background_broad_exception_for_few_attempts() -> None:
    policy = RetryPolicy().attempts(5).on(Exception)
    codes = {w.code for w in policy.warnings()}
    assert "background_broad_exception" not in codes


def test_warning_codes_have_message_and_optional_hint() -> None:
    policy = RetryPolicy().forever().no_delay().on(Exception)
    for warning in policy.warnings():
        assert isinstance(warning.code, str)
        assert len(warning.code) > 0
        assert isinstance(warning.message, str)
        assert warning.hint is None or isinstance(warning.hint, str)


def test_existing_warning_codes_still_present() -> None:
    policy = RetryPolicy().forever().on(Exception).no_delay()
    codes = {w.code for w in policy.warnings()}
    assert "forever" in codes
    assert "no_delay" in codes
    assert "broad_exception" in codes


def test_return_result_replaces_custom_exhaustion_behavior() -> None:
    policy = RetryPolicy().attempts(3).on_exhausted_raise(RuntimeError).return_result()

    codes = {warning.code for warning in policy.warnings()}

    assert policy.should_return_result is True
    assert policy.should_raise_last is False
    assert policy.exhausted_callback is None
    assert policy.exhausted_exception_factory is None
    assert "return_result_precedence" not in codes


# --- warnings() robustness tests ---


def test_warnings_never_raises_for_default_policy() -> None:
    """warnings() must not raise for any valid policy."""
    policy = RetryPolicy()
    warnings = policy.warnings()
    assert isinstance(warnings, tuple)


def test_warnings_never_raises_for_complex_policy() -> None:
    policy = (
        RetryPolicy()
        .attempts(5)
        .on(TimeoutError, ConnectionError)
        .exponential_delay(base=0.5, maximum=30)
        .jitter(maximum=0.5)
        .return_result()
        .with_logging()
    )
    warnings = policy.warnings()
    assert isinstance(warnings, tuple)


def test_warnings_never_raises_for_forever_policy() -> None:
    policy = RetryPolicy().forever().on(Exception).no_delay()
    warnings = policy.warnings()
    assert isinstance(warnings, tuple)
    assert len(warnings) > 0


def test_warnings_returns_tuple_of_policy_warnings() -> None:
    from relinker import PolicyWarning

    policy = RetryPolicy().forever().on(Exception)
    for w in policy.warnings():
        assert isinstance(w, PolicyWarning)
        assert isinstance(w.code, str)
        assert isinstance(w.message, str)


# --- simulate() validation tests ---


def test_simulate_raises_for_zero_attempts() -> None:
    from relinker import InvalidRetryConfigError

    policy = RetryPolicy().attempts(3)
    with pytest.raises(InvalidRetryConfigError):
        policy.simulate(attempts=0)


def test_simulate_raises_for_negative_attempts() -> None:
    from relinker import InvalidRetryConfigError

    policy = RetryPolicy().attempts(3)
    with pytest.raises(InvalidRetryConfigError):
        policy.simulate(attempts=-1)


def test_simulate_does_not_sleep() -> None:
    """simulate() must never sleep — it is pure computation."""
    import time

    policy = RetryPolicy().attempts(10).fixed_delay(100)  # 100s delays
    start = time.monotonic()
    sim = policy.simulate(attempts=10)
    elapsed = time.monotonic() - start

    # Should complete essentially instantly
    assert elapsed < 1.0
    assert sim.total_sleep == 900.0  # 9 delays of 100s (last attempt has no delay)


def test_simulate_is_deterministic_for_fixed_delay() -> None:
    policy = RetryPolicy().attempts(5).fixed_delay(2)
    sim1 = policy.simulate(attempts=5)
    sim2 = policy.simulate(attempts=5)
    assert sim1.total_sleep == sim2.total_sleep
    assert sim1.attempt_count == sim2.attempt_count


# --- explain() tests ---


def test_explain_returns_non_empty_string() -> None:
    policy = RetryPolicy().attempts(3)
    text = policy.explain()
    assert isinstance(text, str)
    assert len(text) > 0


def test_explain_includes_warnings() -> None:
    policy = RetryPolicy().forever().on(Exception).no_delay()
    text = policy.explain()
    assert "Warnings" in text
    assert "forever" in text


def test_explain_no_warnings_section_for_clean_policy() -> None:
    policy = RetryPolicy().attempts(3).on(TimeoutError).fixed_delay(1)
    text = policy.explain()
    assert "Warnings" not in text


# --- timeline() tests ---


def test_timeline_returns_string() -> None:
    policy = RetryPolicy().attempts(3).fixed_delay(1)
    text = policy.timeline(attempts=3)
    assert isinstance(text, str)
    assert "Relinker simulation" in text


def test_timeline_matches_simulate_describe() -> None:
    policy = RetryPolicy().attempts(3).fixed_delay(1)
    assert policy.timeline(attempts=3) == policy.simulate(attempts=3).describe()
