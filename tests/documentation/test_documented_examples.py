"""Executable versions of the primary examples shown in project documentation."""

from __future__ import annotations

from relinker import RetryBudget, RetryPolicy, retry


def test_basic_retry_decorator_example() -> None:
    calls = 0

    @retry(attempts=3, delay=0, on=(TimeoutError,))
    def fetch_data() -> str:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise TimeoutError("temporary")
        return "ready"

    assert fetch_data() == "ready"
    assert calls == 2


def test_fluent_policy_example() -> None:
    calls = 0

    def fetch_data() -> str:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise ConnectionError("temporary")
        return "ready"

    policy = (
        RetryPolicy().attempts(3).on(TimeoutError, ConnectionError).fixed_delay(0).return_result()
    )

    result = policy.run(fetch_data)

    assert result.succeeded is True
    assert result.value == "ready"
    assert result.attempt_count == 2


def test_retry_budget_quick_start_example() -> None:
    calls = 0
    budget = RetryBudget(max_retries=2, per=60)

    def call_payments_api() -> str:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise TimeoutError("temporary")
        return "paid"

    policy = (
        RetryPolicy()
        .attempts(2)
        .on(TimeoutError, ConnectionError)
        .fixed_delay(0)
        .with_retry_budget(budget, key="payments-api")
    )

    assert policy.run(call_payments_api) == "paid"
    assert calls == 2


def test_exhaustion_precedence_example() -> None:
    def fail() -> None:
        raise RuntimeError("boom")

    fallback_last = RetryPolicy().attempts(1).raise_last().fallback_value("safe")
    raise_last = RetryPolicy().attempts(1).fallback_value("safe").raise_last()

    assert fallback_last.run(fail) == "safe"

    try:
        raise_last.run(fail)
    except RuntimeError as error:
        assert str(error) == "boom"
    else:  # pragma: no cover - assertion guard
        raise AssertionError("raise_last() must re-raise the original exception")
