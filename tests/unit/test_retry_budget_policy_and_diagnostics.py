from __future__ import annotations

import json
import logging

import pytest

from relinker import InvalidRetryConfigError, RetryBudget, RetryPolicy


def test_policy_budget_builder_is_immutable_and_removable() -> None:
    budget = RetryBudget(max_retries=5, per=60)
    original = RetryPolicy()
    configured = original.with_retry_budget(budget, key="payments")

    assert original.retry_budget is None
    assert configured.retry_budget is budget
    assert configured.retry_budget_key == "payments"
    assert configured.attempts(4).retry_budget is budget
    assert configured.without_retry_budget().retry_budget is None
    assert configured.without_retry_budget().retry_budget_key is None


def test_policy_rejects_invalid_budget_or_key() -> None:
    with pytest.raises(InvalidRetryConfigError):
        RetryPolicy().with_retry_budget(object(), key="api")  # type: ignore[arg-type]
    with pytest.raises(InvalidRetryConfigError):
        RetryPolicy().with_retry_budget(RetryBudget(1, per=1), key="  ")


def test_explain_and_preview_describe_budget_without_simulating_shared_wait() -> None:
    policy = RetryPolicy().with_retry_budget(RetryBudget(20, per=60), key="payments-api")

    explanation = policy.explain()
    preview = policy.preview()

    assert 'share at most 20 retries every 60s under the budget key "payments-api"' in explanation
    assert "Retry budget: RetryBudget" in explanation
    assert "Shared retry-budget waiting is not included" in preview


def test_structured_logging_has_delay_breakdown_without_key(
    caplog: pytest.LogCaptureFixture,
) -> None:
    logger = logging.getLogger("retry-budget-test")
    caplog.set_level(logging.INFO, logger=logger.name)
    budget = RetryBudget(1, per=10)
    calls = 0

    def task() -> str:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise TimeoutError("temporary")
        return "ok"

    policy = (
        RetryPolicy()
        .attempts(2)
        .on(TimeoutError)
        .fixed_delay(2)
        .with_retry_budget(budget, key="private-tenant-key")
        .with_structured_logging(logger=logger)
        .with_sleep(lambda _: None)
    )
    assert policy.run(task) == "ok"

    payload = json.loads(caplog.records[0].message)
    assert payload["policy_delay"] == 2
    assert payload["budget_delay"] == 0
    assert payload["total_delay"] == 2
    assert "private-tenant-key" not in caplog.text


def test_structured_logging_preserves_decimal_policy_delay_without_budget_wait(
    caplog: pytest.LogCaptureFixture,
) -> None:
    logger = logging.getLogger("retry-budget-decimal-delay-test")
    caplog.set_level(logging.INFO, logger=logger.name)
    budget = RetryBudget(1, per=10)
    calls = 0

    def task() -> str:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise TimeoutError("temporary")
        return "ok"

    policy = (
        RetryPolicy()
        .attempts(2)
        .on(TimeoutError)
        .fixed_delay(0.1)
        .with_retry_budget(budget, key="tenant")
        .with_structured_logging(logger=logger)
        .with_sleep(lambda _: None)
    )

    assert policy.run(task) == "ok"

    payload = json.loads(caplog.records[0].message)
    assert payload["policy_delay"] == 0.1
    assert payload["budget_delay"] == 0
    assert payload["total_delay"] == 0.1
