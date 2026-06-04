"""Tests for the RetryWrappedFunction Protocol."""

from __future__ import annotations

from typing import Any

from retryflow import RetryPolicy, RetryWrappedFunction


def test_decorated_function_satisfies_protocol() -> None:
    @RetryPolicy().attempts(3)
    def task() -> str:
        return "ok"

    assert isinstance(task, RetryWrappedFunction)


def test_decorated_function_has_retry_stats() -> None:
    @RetryPolicy().attempts(3)
    def task() -> str:
        return "ok"

    assert hasattr(task, "retry_stats")
    task()
    snap = task.retry_stats.snapshot()  # type: ignore[attr-defined]
    assert snap.calls == 1


def test_decorated_function_has_retry_policy() -> None:
    policy = RetryPolicy().attempts(5)

    @policy
    def task() -> str:
        return "ok"

    assert hasattr(task, "retry_policy")
    assert task.retry_policy is policy  # type: ignore[attr-defined]


def test_decorated_function_with_policy() -> None:
    @RetryPolicy().attempts(3)
    def task() -> str:
        return "ok"

    new_policy = RetryPolicy().attempts(10)
    new_task = task.with_policy(new_policy)  # type: ignore[attr-defined]

    assert hasattr(new_task, "retry_policy")
    assert new_task.retry_policy is new_policy  # type: ignore[attr-defined]


def test_retry_wrapped_function_runtime_checkable() -> None:
    plain_fn: Any = lambda: None  # noqa: E731
    assert not isinstance(plain_fn, RetryWrappedFunction)

    @RetryPolicy()
    def wrapped() -> str:
        return "ok"

    assert isinstance(wrapped, RetryWrappedFunction)
