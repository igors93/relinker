import pytest

from __future__ import annotations

from relinker import RetryBudget, RetryPolicy
from relinker.conditions.composite import AnyCondition
from relinker.conditions.exception import ExceptionCondition
from relinker.delays.fixed import FixedDelay


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


def test_composed_forever_and_attempts_warns_as_infinite_retry() -> None:
    policy = RetryPolicy().forever().and_stop_after_attempts(3).no_delay()
    codes = _codes(policy)

    assert "forever" in codes
    assert "tight_loop_risk" in codes
    assert "missing_retry_budget" in codes


def test_composed_forever_or_max_time_does_not_warn_as_infinite_retry() -> None:
    policy = RetryPolicy().forever().or_stop_after_time(10).no_delay()
    codes = _codes(policy)

    assert "forever" not in codes
    assert "tight_loop_risk" not in codes


def test_broad_exception_inside_any_condition_warns() -> None:
    policy = RetryPolicy().on(TimeoutError).or_on(Exception)

    assert "broad_exception" in _codes(policy)


def test_broad_exception_inside_all_condition_with_restriction_does_not_warn() -> None:
    policy = RetryPolicy().all_conditions(
        ExceptionCondition((Exception,)),
        ExceptionCondition((TimeoutError,)),
    )
    codes = _codes(policy)

    assert "broad_exception" not in codes
    assert "background_broad_exception" not in codes


def test_nested_condition_composition_warns_once_in_stable_order() -> None:
    nested = AnyCondition(
        (
            ExceptionCondition((TimeoutError,)),
            AnyCondition(
                (
                    ExceptionCondition((Exception,)),
                    ExceptionCondition((ConnectionError,)),
                )
            ),
        )
    )
    policy = RetryPolicy().forever().any_condition(nested).no_delay()

    codes = _codes(policy)

    assert codes == [
        "forever",
        "no_delay",
        "tight_loop_risk",
        "broad_exception",
        "missing_retry_budget",
        "background_broad_exception",
    ]
    assert len(codes) == len(set(codes))


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


def test_composed_zero_delay_warns_as_no_delay() -> None:
    policy = RetryPolicy().forever().no_delay().add_delay(FixedDelay(0))

    codes = _codes(policy)

    assert "no_delay" in codes
    assert "tight_loop_risk" in codes


def test_composed_delay_with_positive_child_is_not_no_delay() -> None:
    policy = RetryPolicy().forever().no_delay().add_delay(FixedDelay(1))

    codes = _codes(policy)

    assert "no_delay" not in codes
    assert "tight_loop_risk" not in codes

@pytest.mark.parametrize(
    "policy",
    [
        RetryPolicy().forever().linear_delay(start=0, step=0),
        RetryPolicy().forever().linear_delay(start=5, step=2, maximum=0),
        RetryPolicy().forever().exponential_delay(base=0),
        RetryPolicy().forever().exponential_delay(base=1, maximum=0),
        RetryPolicy().forever().chain_delay([0, 0, 0]),
        RetryPolicy().forever().random_delay(minimum=0, maximum=0),
        RetryPolicy()
        .forever()
        .random_exponential_delay(base=0, minimum=0),
        RetryPolicy()
        .forever()
        .random_exponential_delay(base=1, minimum=0, maximum=0),
    ],
)
def test_known_always_zero_delays_warn(
    policy: RetryPolicy[object],
) -> None:
    codes = _codes(policy)

    assert "no_delay" in codes
    assert "tight_loop_risk" in codes


@pytest.mark.parametrize(
    "policy",
    [
        RetryPolicy().forever().linear_delay(start=0, step=1),
        RetryPolicy().forever().exponential_delay(base=1),
        RetryPolicy().forever().chain_delay([0, 1, 0]),
        RetryPolicy().forever().random_delay(minimum=0, maximum=1),
        RetryPolicy()
        .forever()
        .random_exponential_delay(base=1, minimum=0),
    ],
)
def test_delays_that_can_be_positive_are_not_reported_as_no_delay(
    policy: RetryPolicy[object],
) -> None:
    codes = _codes(policy)

    assert "no_delay" not in codes
    assert "tight_loop_risk" not in codes