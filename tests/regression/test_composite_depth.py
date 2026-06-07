"""Regression contracts for deeply composed policies."""

from __future__ import annotations

from relinker import RetryPolicy


def test_large_or_on_chain_decides_and_serializes_without_recursion_error() -> None:
    policy = RetryPolicy().on(ValueError)
    for _ in range(1200):
        policy = policy.or_on(KeyError)

    assert policy.condition.should_retry_exception(KeyError("retry"))
    assert not policy.condition.should_retry_exception(RuntimeError("no retry"))

    data = policy.to_dict()
    assert data["condition"]["type"] == "any"
