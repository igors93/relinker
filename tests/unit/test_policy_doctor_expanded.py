from __future__ import annotations

import pytest

from relinker import RetryBudget, RetryPolicy
from relinker.conditions.composite import AnyCondition
from relinker.conditions.exception import ExceptionCondition
from relinker.delays.composite import AdditiveDelay
from relinker.delays.fixed import FixedDelay
from relinker.delays.random_delay import RandomDelay


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
        RetryPolicy().forever().random_exponential_delay(base=0, minimum=0),
        RetryPolicy().forever().random_exponential_delay(base=1, minimum=0, maximum=0),
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
        RetryPolicy().forever().random_exponential_delay(base=1, minimum=0),
    ],
)
def test_delays_that_can_be_positive_are_not_reported_as_no_delay(
    policy: RetryPolicy[object],
) -> None:
    codes = _codes(policy)

    assert "no_delay" not in codes
    assert "tight_loop_risk" not in codes


def test_os_error_scope_warns_without_changing_doctor_severity() -> None:
    policy = RetryPolicy().attempts(3).on(OSError).fixed_delay(1)

    warnings = policy.warnings()
    warning = next(item for item in warnings if item.code == "broad_os_error")

    assert "non-transport" in warning.message
    assert warning.hint is not None
    assert "documented transient exceptions" in warning.hint
    assert policy.doctor().warnings == warnings
    assert policy.doctor().risk_level == "warning"


def test_specific_os_error_related_types_do_not_trigger_broad_warning() -> None:
    class TransientSocketError(OSError):
        pass

    policy = RetryPolicy().on(TimeoutError, ConnectionError, TransientSocketError)

    assert "broad_os_error" not in _codes(policy)


def test_broad_exception_suppresses_redundant_os_error_warning() -> None:
    policy = RetryPolicy().on(Exception, OSError)
    codes = _codes(policy)

    assert "broad_exception" in codes
    assert "broad_os_error" not in codes


def test_os_error_inside_any_condition_warns() -> None:
    policy = RetryPolicy().on(TimeoutError).or_on(OSError)

    assert "broad_os_error" in _codes(policy)


def test_os_error_inside_all_condition_with_restriction_does_not_warn() -> None:
    policy = RetryPolicy().all_conditions(
        ExceptionCondition((OSError,)),
        ExceptionCondition((TimeoutError,)),
    )

    assert "broad_os_error" not in _codes(policy)


def test_os_error_inside_all_condition_with_broad_supertype_warns() -> None:
    policy = RetryPolicy().all_conditions(
        ExceptionCondition((Exception,)),
        ExceptionCondition((OSError,)),
    )

    assert "broad_os_error" in _codes(policy)


def test_os_error_warning_has_stable_order_without_duplicates() -> None:
    policy = RetryPolicy().forever().on(OSError).no_delay()

    codes = _codes(policy)

    assert codes == [
        "forever",
        "no_delay",
        "tight_loop_risk",
        "broad_os_error",
        "missing_retry_budget",
    ]
    assert len(codes) == len(set(codes))
    assert [warning.code for warning in policy.doctor().warnings] == codes


def test_seeded_jitter_warns_about_cross_execution_determinism() -> None:
    policy = RetryPolicy().attempts(5).on(TimeoutError).fixed_delay(1).jitter(maximum=0.5, seed=7)

    warning = next(item for item in policy.warnings() if item.code == "seeded_random_delay")

    assert "same per-attempt delays" in warning.message
    assert warning.hint is not None
    assert "seed=None" in warning.hint
    assert policy.doctor().risk_level == "warning"


def test_seeded_random_delay_warns() -> None:
    policy = RetryPolicy().attempts(3).on(TimeoutError).random_delay(minimum=0, maximum=1, seed=7)

    assert "seeded_random_delay" in _codes(policy)


def test_seeded_random_exponential_delay_warns() -> None:
    policy = (
        RetryPolicy()
        .attempts(3)
        .on(TimeoutError)
        .random_exponential_delay(base=1, maximum=10, seed=7)
    )

    assert "seeded_random_delay" in _codes(policy)


@pytest.mark.parametrize(
    "policy",
    [
        RetryPolicy().attempts(3).on(TimeoutError).random_delay(),
        RetryPolicy().attempts(3).on(TimeoutError).random_exponential_delay(),
        RetryPolicy().attempts(3).on(TimeoutError).fixed_delay(1).jitter(),
    ],
)
def test_unseeded_random_delays_do_not_warn(policy: RetryPolicy[object]) -> None:
    assert "seeded_random_delay" not in _codes(policy)


def test_testing_mode_suppresses_seeded_random_delay_warning() -> None:
    production = RetryPolicy().attempts(3).on(TimeoutError).random_delay(seed=7)
    testing = production.for_testing()

    assert "seeded_random_delay" in _codes(production)
    assert "seeded_random_delay" not in _codes(testing)


def test_fixed_random_delay_range_does_not_warn() -> None:
    policy = RetryPolicy().attempts(3).on(TimeoutError).random_delay(minimum=1, maximum=1, seed=7)

    assert "seeded_random_delay" not in _codes(policy)


@pytest.mark.parametrize(
    "policy",
    [
        RetryPolicy()
        .attempts(3)
        .on(TimeoutError)
        .random_exponential_delay(base=0, minimum=5, seed=7),
        RetryPolicy()
        .attempts(3)
        .on(TimeoutError)
        .random_exponential_delay(base=1, minimum=5, maximum=5, seed=7),
    ],
)
def test_degenerate_random_exponential_delay_does_not_warn(
    policy: RetryPolicy[object],
) -> None:
    assert "seeded_random_delay" not in _codes(policy)


def test_unseeded_random_component_prevents_seeded_warning() -> None:
    delay = AdditiveDelay(
        (
            RandomDelay(minimum=0, maximum=1, seed=7),
            RandomDelay(minimum=0, maximum=1),
        )
    )
    policy = RetryPolicy().attempts(3).on(TimeoutError).add_delay(delay)

    assert "seeded_random_delay" not in _codes(policy)


def test_nested_seeded_random_component_is_detected() -> None:
    nested = AdditiveDelay(
        (
            FixedDelay(1),
            AdditiveDelay((RandomDelay(minimum=0, maximum=1, seed=7),)),
        )
    )
    policy = RetryPolicy().attempts(3).on(TimeoutError).add_delay(nested)

    assert "seeded_random_delay" in _codes(policy)


def test_single_attempt_policy_does_not_warn_about_seeded_random_delay() -> None:
    policy = RetryPolicy().attempts(1).on(TimeoutError).jitter(seed=7)

    assert "seeded_random_delay" not in _codes(policy)


def test_fixed_jitter_range_is_not_treated_as_effective_randomness() -> None:
    policy = (
        RetryPolicy()
        .attempts(10)
        .on(TimeoutError)
        .fixed_delay(2)
        .jitter(minimum=0.5, maximum=0.5, seed=7)
    )

    codes = _codes(policy)

    assert "missing_jitter" in codes
    assert "seeded_random_delay" not in codes


def test_seeded_random_warning_has_stable_order_without_duplicate_jitter_warning() -> None:
    policy = RetryPolicy().attempts(10).on(TimeoutError).fixed_delay(2).jitter(seed=7)

    codes = _codes(policy)

    assert "missing_jitter" not in codes
    assert codes.count("seeded_random_delay") == 1
    assert codes.index("seeded_random_delay") < codes.index("missing_retry_budget")


def test_seeded_random_delay_does_not_warn_when_max_time_prevents_retry() -> None:
    policy = RetryPolicy().max_time(0).on(TimeoutError).random_delay(seed=7)

    assert "seeded_random_delay" not in _codes(policy)


def test_seeded_random_delay_does_not_warn_when_any_stop_prevents_retry() -> None:
    policy = RetryPolicy().attempts(10).or_stop_after_time(0).on(TimeoutError).jitter(seed=7)

    assert "seeded_random_delay" not in _codes(policy)


def test_seeded_random_delay_does_not_warn_when_all_stops_prevent_retry() -> None:
    policy = RetryPolicy().attempts(1).and_stop_after_time(0).on(TimeoutError).jitter(seed=7)

    assert "seeded_random_delay" not in _codes(policy)


def test_seeded_random_delay_warns_when_all_stop_still_allows_retry() -> None:
    policy = RetryPolicy().attempts(1).and_stop_after_time(10).on(TimeoutError).jitter(seed=7)

    assert "seeded_random_delay" in _codes(policy)


def test_forever_with_unlimited_history_warns() -> None:
    policy = RetryPolicy().forever().on(TimeoutError).fixed_delay(1).keep_history(None)

    warnings = policy.warnings()
    warning = next(item for item in warnings if item.code == "unbounded_history")

    assert "every attempt record" in warning.message
    assert warning.hint is not None
    assert "keep_history(n)" in warning.hint
    assert policy.doctor().warnings == warnings
    assert policy.doctor().risk_level == "risky"
    assert policy.to_dict()["history_limit"] is None


def test_forever_with_default_or_explicit_history_limit_does_not_warn() -> None:
    default_limit = RetryPolicy().forever().on(TimeoutError).fixed_delay(1)
    explicit_limit = default_limit.keep_history(100)

    assert default_limit.history_limit == 1000
    assert "unbounded_history" not in _codes(default_limit)
    assert "unbounded_history" not in _codes(explicit_limit)


@pytest.mark.parametrize(
    "policy",
    [
        RetryPolicy().attempts(100).on(TimeoutError).keep_history(None),
        RetryPolicy().max_time(60).on(TimeoutError).keep_history(None),
        RetryPolicy().forever().or_stop_after_attempts(5).on(TimeoutError).keep_history(None),
    ],
)
def test_bounded_policy_with_unlimited_history_does_not_warn(
    policy: RetryPolicy[object],
) -> None:
    assert "unbounded_history" not in _codes(policy)


def test_effectively_infinite_composition_with_unlimited_history_warns() -> None:
    policy = RetryPolicy().forever().and_stop_after_attempts(5).on(TimeoutError).keep_history(None)

    assert "unbounded_history" in _codes(policy)


def test_unbounded_history_warning_has_stable_order_without_duplicates() -> None:
    policy = RetryPolicy().forever().on(TimeoutError).no_delay().keep_history(None)

    codes = _codes(policy)

    assert codes == [
        "forever",
        "no_delay",
        "tight_loop_risk",
        "unbounded_history",
        "missing_retry_budget",
    ]
    assert len(codes) == len(set(codes))
    assert [warning.code for warning in policy.doctor().warnings] == codes
