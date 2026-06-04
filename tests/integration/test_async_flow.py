import pytest

from retryflow import RetryPolicy


@pytest.mark.asyncio
async def test_async_flow() -> None:
    async def task() -> str:
        return "ok"

    value = await RetryPolicy().attempts(1).run_async(task)

    assert value == "ok"
