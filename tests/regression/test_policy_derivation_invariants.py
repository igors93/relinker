"""Regression contracts for immutable policy derivation."""

from __future__ import annotations

from collections.abc import Callable

from relinker import RetryBudget, RetryPolicy
from relinker.event import RetryEvent


def _sync_sleep(_: float) -> None:
    pass


async def _async_sleep(_: float) -> None:
    pass


def _handler(_: RetryEvent) -> None:
    pass


def _fallback(_: object) -> str:
    return "fallback"


def _base_policy() -> RetryPolicy[str]:
    policy: RetryPolicy[str] = (
        RetryPolicy()
        .named("api")
        .keep_history(7)
        .with_retry_budget(RetryBudget(max_retries=2, per=10), key="api")
        .with_sleep(_sync_sleep, _async_sleep)
        .on_before_attempt(_handler)
        .fallback(_fallback)
    )
    return policy


def _assert_preserved(base: RetryPolicy[str], derived: RetryPolicy[str]) -> None:
    assert derived.name == base.name
    assert derived.history_limit == base.history_limit
    assert derived.retry_budget is base.retry_budget
    assert derived.retry_budget_key == base.retry_budget_key
    assert derived.sleep is base.sleep
    assert derived.async_sleep is base.async_sleep
    assert derived.event_handlers == base.event_handlers
    assert derived.exhausted_callback is base.exhausted_callback


def test_non_exhaustion_builders_preserve_unrelated_policy_state() -> None:
    builders: tuple[Callable[[RetryPolicy[str]], RetryPolicy[str]], ...] = (
        lambda policy: policy.attempts(5),
        lambda policy: policy.max_time(30),
        lambda policy: policy.fixed_delay(1),
        lambda policy: policy.exponential_delay(base=1, factor=2, maximum=10),
        lambda policy: policy.jitter(maximum=0.1, seed=1),
        lambda policy: policy.on(TimeoutError),
        lambda policy: policy.retry_if_result(lambda value: value == "retry"),
    )

    for builder in builders:
        base = _base_policy()
        derived = builder(base)

        assert derived is not base
        _assert_preserved(base, derived)
        _assert_preserved(base, base)
