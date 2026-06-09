"""Unit tests for immutable policy derivation and structured configuration."""

from __future__ import annotations

import json

from relinker import RetryBudget, RetryPolicy


def test_attempts_builder_does_not_mutate_original_policy() -> None:
    original = RetryPolicy()
    derived = original.attempts(7)
    assert original.to_dict()["stop"] == {"type": "attempts", "maximum": 3}
    assert derived.to_dict()["stop"] == {"type": "attempts", "maximum": 7}


def test_delay_builder_does_not_mutate_original_policy() -> None:
    original = RetryPolicy()
    derived = original.fixed_delay(2)
    assert original.to_dict()["delay"] == {"type": "fixed", "seconds": 0}
    assert derived.to_dict()["delay"] == {"type": "fixed", "seconds": 2}


def test_condition_builder_does_not_mutate_original_policy() -> None:
    original = RetryPolicy()
    derived = original.on(TimeoutError)
    original_condition = original.to_dict()["condition"]
    derived_condition = derived.to_dict()["condition"]
    assert original_condition["exceptions"] == ["builtins.Exception"]  # type: ignore[index]
    assert derived_condition["exceptions"] == ["builtins.TimeoutError"]  # type: ignore[index]


def test_named_builder_does_not_mutate_original_policy() -> None:
    original = RetryPolicy()
    derived = original.named("api")
    assert original.to_dict()["name"] is None
    assert derived.to_dict()["name"] == "api"


def test_retry_budget_can_be_removed_without_mutating_budgeted_policy() -> None:
    budget = RetryBudget(max_retries=2, per=10)
    budgeted = RetryPolicy().with_retry_budget(budget, key="api")
    plain = budgeted.without_retry_budget()
    assert budgeted.to_dict()["retry_budget"]["enabled"] is True  # type: ignore[index]
    assert plain.to_dict()["retry_budget"] == {"enabled": False}


def test_policy_to_dict_is_json_serializable() -> None:
    policy = (
        RetryPolicy()
        .named("payments")
        .attempts(4)
        .on(TimeoutError, ConnectionError)
        .exponential_delay(base=0.5, maximum=5)
        .keep_history(20)
    )
    encoded = json.dumps(policy.to_dict())
    assert "payments" in encoded
    assert "TimeoutError" in encoded


def test_for_testing_is_visible_in_structured_policy_view() -> None:
    original = RetryPolicy()
    testing = original.for_testing()
    assert original.to_dict()["testing"] == {"no_real_sleep": False}
    assert testing.to_dict()["testing"] == {"no_real_sleep": True}


def test_custom_sleep_after_for_testing_clears_testing_metadata() -> None:
    policy = RetryPolicy().for_testing().with_sleep(lambda _: None)
    assert policy.to_dict()["testing"] == {"no_real_sleep": False}
