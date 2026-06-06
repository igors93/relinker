"""Regression test for async callable objects used as decorated tasks."""

from __future__ import annotations

import pytest

from relinker import RetryPolicy


class AsyncCallable:
    """Async callable that succeeds only on the third invocation."""

    def __init__(self) -> None:
        self.calls = 0

    async def __call__(self) -> str:
        self.calls += 1
        if self.calls < 3:
            raise RuntimeError("temporary")
        return "ok"


@pytest.mark.asyncio
async def test_decorator_retries_async_callable_object() -> None:
    """Objects with async __call__ must use the asynchronous retry executor."""
    task = AsyncCallable()
    wrapped = RetryPolicy().attempts(3).on(RuntimeError).no_delay()(task)

    result = await wrapped()

    assert result == "ok"
    assert task.calls == 3
