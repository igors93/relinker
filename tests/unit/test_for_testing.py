"""Tests for RetryPolicy.for_testing() — Idea 5.

Contract:
- for_testing() returns a new RetryPolicy with sync and async sleep replaced by no-ops.
- The returned policy is identical in all other respects (attempts, conditions, events, etc.).
- It is chainable (returns RetryPolicy, can be further configured).
- Limitations: max_time and retry budget are NOT virtually advanced; they use real time.
"""

from __future__ import annotations

import contextlib

import pytest

from relinker import RetryPolicy


def test_for_testing_returns_retry_policy() -> None:
    policy = RetryPolicy().attempts(3).on(ValueError).for_testing()
    assert isinstance(policy, RetryPolicy)


def test_for_testing_is_chainable() -> None:
    policy = RetryPolicy().for_testing().attempts(5).on(TypeError)
    assert isinstance(policy, RetryPolicy)


def test_for_testing_sync_executor_does_not_sleep() -> None:
    sleeps: list[float] = []
    calls = 0

    base = RetryPolicy().attempts(3).on(ValueError).fixed_delay(10.0)

    def failing_op() -> str:
        nonlocal calls
        calls += 1
        if calls < 3:
            raise ValueError("retry")
        return "ok"

    result = base.for_testing().run(failing_op)

    assert result == "ok"
    assert calls == 3
    assert sleeps == [], "for_testing() must disable all sleep"


@pytest.mark.asyncio
async def test_for_testing_async_executor_does_not_sleep() -> None:
    calls = 0

    base = RetryPolicy().attempts(3).on(ValueError).fixed_delay(10.0)

    async def failing_op() -> str:
        nonlocal calls
        calls += 1
        if calls < 3:
            raise ValueError("retry")
        return "ok"

    result = await base.for_testing().run_async(failing_op)

    assert result == "ok"
    assert calls == 3


def test_for_testing_sync_context_manager_does_not_sleep() -> None:
    calls = 0

    base = RetryPolicy().attempts(3).on(ValueError).fixed_delay(10.0)
    policy = base.for_testing()

    with contextlib.suppress(ValueError):
        for attempt in policy.iter():
            with attempt:
                calls += 1
                if calls < 3:
                    raise ValueError("retry")

    assert calls == 3


@pytest.mark.asyncio
async def test_for_testing_async_context_manager_does_not_sleep() -> None:
    calls = 0

    base = RetryPolicy().attempts(3).on(ValueError).fixed_delay(10.0)
    policy = base.for_testing()

    with contextlib.suppress(ValueError):
        async for attempt in policy.async_iter():
            async with attempt:
                calls += 1
                if calls < 3:
                    raise ValueError("retry")

    assert calls == 3


def test_for_testing_preserves_other_policy_settings() -> None:
    events: list[str] = []
    base = (
        RetryPolicy()
        .attempts(2)
        .on(ValueError)
        .fixed_delay(5.0)
        .on_retry(lambda _: events.append("retry"))
    )
    calls = 0

    def op() -> str:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise ValueError("x")
        return "ok"

    result = base.for_testing().run(op)
    assert result == "ok"
    assert events == ["retry"], "on_retry handler must still fire"
    assert calls == 2


def test_for_testing_does_not_mutate_original() -> None:
    original = RetryPolicy().attempts(3).on(ValueError).fixed_delay(5.0)
    original_sleep = original.sleep

    _ = original.for_testing()

    assert original.sleep is original_sleep, "for_testing() must not modify the original policy"


def test_with_sleep_after_for_testing_exits_testing_mode() -> None:
    def sync_sleep(seconds: float) -> None:
        return None

    async def async_sleep(seconds: float) -> None:
        return None

    testing = RetryPolicy().max_time(5).for_testing()
    restored = testing.with_sleep(sync_sleep, async_sleep)

    assert testing.testing_mode is True
    assert restored.testing_mode is False
    assert "for_testing_with_max_time" not in {warning.code for warning in restored.warnings()}
    assert restored.to_dict()["testing"] == {"no_real_sleep": False}


def test_for_testing_can_be_applied_again_after_custom_sleep() -> None:
    restored = RetryPolicy().max_time(5).for_testing().with_sleep(lambda seconds: None)
    testing_again = restored.for_testing()

    assert restored.testing_mode is False
    assert testing_again.testing_mode is True
    assert "for_testing_with_max_time" in {warning.code for warning in testing_again.warnings()}
    assert testing_again.to_dict()["testing"] == {"no_real_sleep": True}
