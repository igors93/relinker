from __future__ import annotations

from relinker import RetryBudget, RetryPolicy


def _codes(policy: RetryPolicy[object]) -> list[str]:
    return [warning.code for warning in policy.warnings()]


def test_missing_jitter_warns_for_many_deterministic_delayed_attempts() -> None:
    policy = RetryPolicy().attempts(12).on(TimeoutError).exponential_delay(base=1)

    assert "missing_jitter" in _codes(policy)


def test_missing_jitter_does_not_warn_for_low_attempt_count_or_random_delay() -> None:
    low_attempts = RetryPolicy().attempts(4).on(TimeoutError).exponential_delay(base=1)
    jittered = RetryPolicy().attempts(12).on(TimeoutError).exponential_delay(base=1).jitter()

    assert "missing_jitter" not in _codes(low_attempts)
    assert "missing_jitter" not in _codes(jittered)


def test_missing_retry_budget_warns_for_many_attempts_without_budget() -> None:
    policy = RetryPolicy().attempts(12).on(TimeoutError).fixed_delay(1)

    assert "missing_retry_budget" in _codes(policy)


def test_missing_retry_budget_does_not_warn_when_budget_is_configured() -> None:
    budgeted = (
        RetryPolicy()
        .attempts(12)
        .on(TimeoutError)
        .fixed_delay(1)
        .with_retry_budget(RetryBudget(max_retries=10, per=60), key="api")
    )

    assert "missing_retry_budget" not in _codes(budgeted)


def test_silent_fallback_warns_without_giveup_observer_logging_or_result() -> None:
    policy = RetryPolicy().attempts(2).on(TimeoutError).fallback_value("cached")

    assert "silent_fallback" in _codes(policy)


def test_silent_fallback_does_not_warn_when_giveup_is_observed_or_logged() -> None:
    observed = (
        RetryPolicy()
        .attempts(2)
        .on(TimeoutError)
        .fallback_value("cached")
        .on_giveup(lambda event: None)
    )
    logged = RetryPolicy().attempts(2).on(TimeoutError).fallback_value("cached").with_logging()

    assert "silent_fallback" not in _codes(observed)
    assert "silent_fallback" not in _codes(logged)


def test_infinite_retry_with_budget_warns_about_duration() -> None:
    policy = (
        RetryPolicy()
        .forever()
        .on(TimeoutError)
        .fixed_delay(1)
        .with_retry_budget(RetryBudget(max_retries=10, per=60), key="api")
    )

    assert "infinite_retry_with_budget" in _codes(policy)


def test_infinite_retry_with_budget_does_not_warn_for_bounded_policy() -> None:
    policy = (
        RetryPolicy()
        .attempts(12)
        .on(TimeoutError)
        .fixed_delay(1)
        .with_retry_budget(RetryBudget(max_retries=10, per=60), key="api")
    )

    assert "infinite_retry_with_budget" not in _codes(policy)


def test_for_testing_with_max_time_warns_only_when_testing_mode_is_explicit() -> None:
    production = RetryPolicy().max_time(5).on(TimeoutError).fixed_delay(1)
    testing = production.for_testing()

    assert "for_testing_with_max_time" not in _codes(production)
    assert "for_testing_with_max_time" in _codes(testing)


def test_new_warnings_have_deterministic_order_and_doctor_matches_warnings() -> None:
    policy = RetryPolicy().attempts(12).on(TimeoutError).fixed_delay(1).fallback_value("cached")

    codes = _codes(policy)
    assert codes == sorted(codes, key=codes.index)
    assert codes.count("missing_jitter") == 1
    assert codes.count("missing_retry_budget") == 1
    assert codes.count("silent_fallback") == 1

    report = policy.doctor()
    assert [warning.code for warning in report.warnings] == codes
    assert report.ok is False
    assert report.risk_level == "warning"
