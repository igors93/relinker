import pytest

from relinker import RetryPolicy


@pytest.mark.asyncio
async def test_async_context_manager_retries_exception() -> None:
    calls = {"count": 0}

    policy = RetryPolicy().attempts(3).on(RuntimeError)

    async for attempt in policy.async_iter(name="async_test_block"):
        async with attempt:
            calls["count"] += 1
            if calls["count"] < 2:
                raise RuntimeError("temporary")

    assert calls["count"] == 2


@pytest.mark.asyncio
async def test_async_context_manager_retries_result() -> None:
    values = iter([None, "ok"])

    policy = RetryPolicy().attempts(3).retry_if_result(lambda value: value is None)

    async for attempt in policy.async_iter(name="async_result_block"):
        async with attempt:
            value = next(values)
            attempt.set_result(value)

    assert value == "ok"
