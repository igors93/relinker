"""Tests for the RetryWrappedFunction Protocol."""

from __future__ import annotations

from typing import Any

from relinker import RetryPolicy, RetryWrappedFunction


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


def test_async_decorated_function_satisfies_protocol() -> None:
    @RetryPolicy().attempts(3)
    async def async_task() -> str:
        return "ok"

    assert isinstance(async_task, RetryWrappedFunction)


def test_async_decorated_function_has_retry_stats() -> None:
    @RetryPolicy().attempts(3)
    async def async_task() -> str:
        return "ok"

    assert hasattr(async_task, "retry_stats")
    assert hasattr(async_task, "retry_policy")


def test_with_policy_result_satisfies_protocol() -> None:
    @RetryPolicy().attempts(3)
    def task() -> str:
        return "ok"

    new_task = task.with_policy(RetryPolicy().attempts(5))  # type: ignore[attr-defined]
    assert isinstance(new_task, RetryWrappedFunction)


def test_decorated_function_preserves_name_and_doc() -> None:
    @RetryPolicy().attempts(3)
    def my_function() -> str:
        """My function docstring."""
        return "ok"

    assert my_function.__name__ == "my_function"
    assert my_function.__doc__ == "My function docstring."


def test_async_decorated_function_preserves_name() -> None:
    @RetryPolicy().attempts(3)
    async def my_async_function() -> str:
        """Async function docstring."""
        return "ok"

    assert my_async_function.__name__ == "my_async_function"
