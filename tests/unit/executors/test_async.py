import pytest

from retryflow import RetryPolicy


@pytest.mark.asyncio
async def test_async_executor_return_result() -> None:
    async def task() -> str:
        return "ok"

    result = await RetryPolicy().attempts(1).return_result().run_async(task)

    assert result.succeeded
    assert result.value == "ok"
