"""Tests for the new warning codes added in the richer diagnostics improvement."""

from __future__ import annotations

from retryflow import RetryPolicy


def test_warning_many_attempts() -> None:
    policy = RetryPolicy().attempts(11)
    codes = {w.code for w in policy.warnings()}
    assert "many_attempts" in codes


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


def test_return_result_precedence_warning_still_works() -> None:
    # Calling .on_exhausted_raise() first, then .return_result() keeps both flags set,
    # which triggers the return_result_precedence warning.
    policy = RetryPolicy().attempts(3).on_exhausted_raise(RuntimeError).return_result()
    codes = {w.code for w in policy.warnings()}
    assert "return_result_precedence" in codes
