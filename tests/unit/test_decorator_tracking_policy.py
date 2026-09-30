"""The decorator derives its tracking policy once, not on every call."""

from __future__ import annotations

from typing import Any

import pytest

from relinker import RetryPolicy


def test_tracking_policy_is_built_once_per_decoration(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[int] = []
    original = RetryPolicy.return_result

    def counting_return_result(self: RetryPolicy[Any]) -> RetryPolicy[Any]:
        calls.append(1)
        return original(self)

    monkeypatch.setattr(RetryPolicy, "return_result", counting_return_result)
    policy = RetryPolicy().attempts(2).on(TimeoutError).no_delay()

    @policy
    def task(value: int) -> int:
        return value * 2

    assert [task(value) for value in range(5)] == [0, 2, 4, 6, 8]
    assert len(calls) == 1
    assert task.retry_stats.snapshot().calls == 5
    assert task.retry_policy is policy


async def test_async_tracking_policy_is_built_once_per_decoration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[int] = []
    original = RetryPolicy.return_result

    def counting_return_result(self: RetryPolicy[Any]) -> RetryPolicy[Any]:
        calls.append(1)
        return original(self)

    monkeypatch.setattr(RetryPolicy, "return_result", counting_return_result)

    @RetryPolicy().attempts(2).no_delay()
    async def task() -> str:
        return "ok"

    for _ in range(3):
        assert await task() == "ok"
    assert len(calls) == 1
